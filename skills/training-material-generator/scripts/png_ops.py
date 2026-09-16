#!/usr/bin/env python3
"""Stdlib-only PNG pixel operations: redact and crop+upscale (Stage 3/4 annotation support).

    python png_ops.py redact fsd-img-014.png -o fsd-img-014-r1.png --rect 0.05,0.05,0.22,0.04
    python png_ops.py crop   fsd-img-014.png -o fsd-img-014-zoom1.png --rect 0.40,0.20,0.10,0.08 --scale 3

Exists because two of the four annotation types cannot be done as a vector overlay:

  * **redact** — a shape drawn over sensitive data in `render_annotation.py` hides it on
    screen but leaves the original pixels in the file underneath, unzippable by anyone who
    opens the .pptx as a zip. This script destroys the pixels themselves, in a *new* asset
    file — it never mutates the source screenshot in place, so the un-redacted original is
    never silently lost, and `build_training_deck.py` hard-fails a `redact` annotation whose
    block still points at the un-flattened asset.
  * **zoom** — a magnified inset of a small UI element (a Fiori tile, a toolbar icon) is an
    actual crop and upscale of pixels; a vector frame alone cannot make something bigger.

`--rect` is `u,v,du,dv` — the same normalised 0-1-of-the-image fractions used throughout
`deck_plan.json`'s `annotations[]`, so a rect authored for `render_annotation.py` is reused
here unchanged.

**Scope, by design, not by oversight:**

  * Only 8-bit, non-interlaced PNG, colour type 2 (RGB) or 6 (RGBA). Palette, greyscale,
    16-bit and interlaced input are rejected with a message naming the fix, never silently
    mishandled.
  * JPEG input is transcoded to PNG first via LibreOffice (`soffice --convert-to png`) —
    this container has no Pillow/libjpeg binding and no ImageMagick, but does have
    LibreOffice. If `soffice` is unavailable this fails and says to re-save as PNG by hand.
  * Upscaling is nearest-neighbour, not interpolated — smoothing would blur crisp UI text
    and field borders, which is the opposite of what a zoom inset is for.

Depends only on `zlib` and `struct` — same technique as
`tests/fixtures/make_docx_fixture.py`'s hand-encoded PNG fixtures ("no Pillow"). No new
dependency; `tests/run_tests.py`'s stdlib-only AST scan stays green.
"""

import argparse
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
REDACT_FILL = (0x11, 0x11, 0x11)  # dark, deliberately not black — reads as "masked", not "broken"


class PngOpsError(Exception):
    """Malformed input, an unsupported PNG variant, or a rect that doesn't fit the image.
    Caught by build_training_deck.py and reported per-block, same convention as
    render_diagram.py's DiagramSpecError/DiagramOverflowError."""


# ---------------------------------------------------------------------------
# PNG decode
# ---------------------------------------------------------------------------

def _read_chunks(data):
    if data[:8] != PNG_SIGNATURE:
        raise PngOpsError("not a PNG file (bad signature)")
    i = 8
    while i < len(data):
        if i + 8 > len(data):
            raise PngOpsError("truncated PNG (chunk header cut off)")
        length = struct.unpack(">I", data[i:i + 4])[0]
        ctype = data[i + 4:i + 8]
        cdata = data[i + 8:i + 8 + length]
        i += 12 + length
        yield ctype, cdata
        if ctype == b"IEND":
            return


def decode_png(data):
    """Returns (width, height, bpp, rows) where rows is a list of `height` bytes objects,
    each `width * bpp` bytes of unfiltered RGB/RGBA pixel data, row-major top-to-bottom."""
    ihdr = None
    idat = bytearray()
    for ctype, cdata in _read_chunks(data):
        if ctype == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", cdata)
        elif ctype == b"IDAT":
            idat += cdata
    if ihdr is None:
        raise PngOpsError("no IHDR chunk found")

    width, height, depth, color_type, compression, filter_method, interlace = ihdr
    if depth != 8:
        raise PngOpsError(f"only 8-bit PNG is supported (this file is {depth}-bit) — "
                           f"re-save as 8-bit RGB or RGBA")
    if color_type not in (2, 6):
        names = {0: "greyscale", 3: "palette/indexed", 4: "greyscale+alpha"}
        raise PngOpsError(f"only RGB or RGBA PNG is supported (this file is "
                           f"{names.get(color_type, f'colour type {color_type}')}) — "
                           f"re-save as RGB or RGBA")
    if interlace != 0:
        raise PngOpsError("interlaced (Adam7) PNG is not supported — re-save as non-interlaced")

    bpp = 3 if color_type == 2 else 4
    raw = zlib.decompress(bytes(idat))
    stride = width * bpp
    rows = []
    prev = bytearray(stride)
    pos = 0
    for _ in range(height):
        if pos >= len(raw):
            raise PngOpsError("truncated pixel data — fewer scanlines than IHDR claims")
        filt = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if filt == 0:
            pass
        elif filt == 1:  # Sub
            for x in range(bpp, stride):
                line[x] = (line[x] + line[x - bpp]) & 0xFF
        elif filt == 2:  # Up
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 0xFF
        elif filt == 3:  # Average
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0
                b = prev[x]
                line[x] = (line[x] + (a + b) // 2) & 0xFF
        elif filt == 4:  # Paeth
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0
                b = prev[x]
                c = prev[x - bpp] if x >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 0xFF
        else:
            raise PngOpsError(f"unknown PNG filter type {filt}")
        rows.append(bytes(line))
        prev = line
    return width, height, bpp, rows


# ---------------------------------------------------------------------------
# PNG encode
# ---------------------------------------------------------------------------

def _chunk(ctype, cdata):
    return (struct.pack(">I", len(cdata)) + ctype + cdata
            + struct.pack(">I", zlib.crc32(ctype + cdata) & 0xFFFFFFFF))


def encode_png(width, height, bpp, rows):
    """Encodes with filter type 0 (None) throughout — simplest correct encoder; this
    script never needs the compression ratio a Paeth-filtered write buys, only a
    lossless round-trip."""
    color_type = 2 if bpp == 3 else 6
    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    raw = bytearray()
    for row in rows:
        raw.append(0)
        raw += row
    idat = zlib.compress(bytes(raw), 9)
    return PNG_SIGNATURE + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


# ---------------------------------------------------------------------------
# Rect -> pixel bounds
# ---------------------------------------------------------------------------

def rect_to_px(rect, width, height, label="rect"):
    u, v, du, dv = rect
    if not (0 <= u <= 1 and 0 <= v <= 1 and du > 0 and dv > 0 and u + du <= 1.0001 and v + dv <= 1.0001):
        raise PngOpsError(f"{label} {rect} is out of 0-1 bounds or extends past the image edge")
    x0 = max(0, int(round(u * width)))
    y0 = max(0, int(round(v * height)))
    x1 = min(width, max(x0 + 1, int(round((u + du) * width))))
    y1 = min(height, max(y0 + 1, int(round((v + dv) * height))))
    return x0, y0, x1, y1


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def redact(data, rect):
    """Destroys every pixel inside `rect` (normalised u,v,du,dv), returns new PNG bytes.
    Pixels outside the rect are untouched. The source bytes passed in are never modified —
    caller writes the result to a new file."""
    width, height, bpp, rows = decode_png(data)
    x0, y0, x1, y1 = rect_to_px(rect, width, height, label="redact rect")
    fill_px = bytes(REDACT_FILL) + (b"\xff" if bpp == 4 else b"")
    out_rows = list(rows)
    for y in range(y0, y1):
        row = bytearray(out_rows[y])
        row[x0 * bpp:x1 * bpp] = fill_px * (x1 - x0)
        out_rows[y] = bytes(row)
    return encode_png(width, height, bpp, out_rows)


def crop_scale(data, rect, scale):
    """Crops `rect` (normalised u,v,du,dv) and upscales it `scale`x with nearest-neighbour,
    returns new PNG bytes for a zoom-inset asset."""
    if scale < 1:
        raise PngOpsError(f"--scale must be >= 1 (got {scale})")
    width, height, bpp, rows = decode_png(data)
    x0, y0, x1, y1 = rect_to_px(rect, width, height, label="zoom rect")
    cropped = [row[x0 * bpp:x1 * bpp] for row in rows[y0:y1]]
    out_rows = []
    for row in cropped:
        pixels = [row[i * bpp:(i + 1) * bpp] for i in range((x1 - x0))]
        scaled_line = b"".join(p * scale for p in pixels)
        out_rows.extend([scaled_line] * scale)
    return encode_png((x1 - x0) * scale, (y1 - y0) * scale, bpp, out_rows)


def transcode_jpeg_to_png(jpeg_path):
    """Uses LibreOffice to convert a JPEG to PNG (no Pillow/libjpeg binding in this
    container). Raises PngOpsError naming the fallback if soffice is unavailable."""
    soffice = shutil.which("soffice")
    if not soffice:
        raise PngOpsError(
            f"{jpeg_path} is a JPEG and 'soffice' (LibreOffice) is not on PATH to "
            f"transcode it — re-save the screenshot as PNG and re-run"
        )
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [soffice, "--headless", "--convert-to", "png", "--outdir", tmp, str(jpeg_path)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise PngOpsError(f"soffice failed to transcode {jpeg_path}: {result.stderr.strip()}")
        out_png = Path(tmp) / (Path(jpeg_path).stem + ".png")
        if not out_png.is_file():
            raise PngOpsError(f"soffice did not produce {out_png} for {jpeg_path}")
        return out_png.read_bytes()


def load_as_png(image_path):
    """Reads image_path, transcoding JPEG to PNG first if needed. Returns raw PNG bytes."""
    image_path = Path(image_path)
    data = image_path.read_bytes()
    if data[:8] == PNG_SIGNATURE:
        return data
    if data[:2] == b"\xff\xd8":
        return transcode_jpeg_to_png(image_path)
    raise PngOpsError(f"{image_path}: not PNG or JPEG (unrecognized signature)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_rect(s):
    parts = tuple(float(v) for v in s.split(","))
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("--rect must be u,v,du,dv (four 0-1 floats)")
    return parts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    p_redact = sub.add_parser("redact", help="Destroy pixels inside --rect, write a new asset")
    p_redact.add_argument("image", type=Path)
    p_redact.add_argument("--rect", required=True, type=_parse_rect, help="u,v,du,dv normalised 0-1")
    p_redact.add_argument("-o", "--out", required=True, type=Path)

    p_crop = sub.add_parser("crop", help="Crop --rect and upscale --scale x (nearest-neighbour), write a new asset")
    p_crop.add_argument("image", type=Path)
    p_crop.add_argument("--rect", required=True, type=_parse_rect, help="u,v,du,dv normalised 0-1")
    p_crop.add_argument("--scale", type=int, default=3)
    p_crop.add_argument("-o", "--out", required=True, type=Path)

    args = ap.parse_args()

    try:
        png_data = load_as_png(args.image)
        if args.command == "redact":
            out_data = redact(png_data, args.rect)
        else:
            out_data = crop_scale(png_data, args.rect, args.scale)
    except PngOpsError as exc:
        sys.exit(str(exc))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(out_data)
    print(f"{args.command}: {args.image} -> {args.out} ({len(out_data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
