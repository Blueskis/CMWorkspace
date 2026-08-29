#!/usr/bin/env python3
"""Extract images with their anchoring context (Stage 0).

    python extract_assets.py training/<run>/inputs/ --assets training/<run>/assets \\
        -o training/<run>/asset_index.json

A bare folder of PNGs is useless to Stage 3 — what a slide planner needs is "this is
the screenshot that follows the approval-steps procedure, captioned Figure 7". So each
asset records the section it fell under (matching source_map.json's section_id, via the
same heading-stack walker map_source.py uses — see lib/section_walk.py), the nearest
heading, a caption candidate pulled from the paragraph that follows it (FSD captions
typically follow the image, not precede it), and any alt text the source document set.

Three input formats:

  * .docx — walks word/document.xml in document order for <a:blip r:embed>, resolves
    through word/_rels/document.xml.rels, pulls bytes from word/media/.
  * .pptx (as a *source* document) — ppt/media/, keyed by slide order via each slide's
    own rels.
  * .pdf — shells out to `pdfimages -all -p <pdf> <prefix>` (the pdf skill's own
    toolchain). If that binary is missing, prints the exact command and exits non-zero
    rather than guessing — there is no stdlib fallback for PDF image extraction.

Noise filtering removes the client's letterhead so it doesn't repeat across half the
deck: an asset repeating more than twice across the document set, or under 20px in
either dimension, is dropped outright and reported, not silently kept. Assets that
survive but are still small or extreme-aspect are kept with a `quality` flag instead —
that's a judgement call for Stage 3, not this script.

**Never crops, upscales, or recomposes an image.** Flag it (`quality: [low_res, ...]`)
and let the practitioner decide.

Stdlib only.
"""

import argparse
import json
import re
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from section_walk import (  # noqa: E402
    PNS, WNS, HeadingStack, docx_heading_from_paragraph, docx_paragraph_text,
)

HARD_DROP_REPEAT = 2       # repeat_count > this many times -> dropped as letterhead/logo
HARD_DROP_MIN_PX = 20      # either dimension below this -> dropped as a bullet/rule icon
LOW_RES_MAX_PX = 400       # largest dimension below this -> quality: low_res
TINY_MAX_PX = 150          # largest dimension below this (but kept) -> quality: tiny
WIDE_ASPECT = 3.0          # aspect beyond this (or its inverse) -> quality: very_wide


def image_dimensions(data):
    """(width_px, height_px, format) from raw bytes, or (0, 0, 'other') if unrecognized."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        return w, h, "png"
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h, "jpeg"
            i += 2 + seg_len
        return 0, 0, "jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        w, h = struct.unpack("<HH", data[6:10])
        return w, h, "gif"
    if data[:2] == b"BM":
        w, h = struct.unpack("<ii", data[18:26])
        return w, abs(h), "bmp"
    if data[:4] == b"\x01\x00\x00\x00" and len(data) > 40:
        return 0, 0, "wmf"
    if data[:4] == b"\x20\x45\x4d\x46" or data[40:44] == b" EMF":
        return 0, 0, "emf"
    if data[:5] == b"<?xml" or data[:4] == b"<svg":
        return 0, 0, "svg"
    return 0, 0, "other"


def guess_role(width_px, height_px, fmt, repeat_count):
    if fmt in ("svg", "emf", "wmf"):
        return "diagram-image"
    max_dim = max(width_px, height_px)
    if max_dim and max_dim < TINY_MAX_PX:
        return "icon" if repeat_count > 1 else "decorative"
    if repeat_count > 1 and width_px and height_px and width_px < 300 and height_px < 300:
        return "logo"
    return "screenshot"


def quality_flags(width_px, height_px):
    flags = []
    max_dim = max(width_px, height_px)
    if 0 < max_dim < TINY_MAX_PX:
        flags.append("tiny")
    elif 0 < max_dim < LOW_RES_MAX_PX:
        flags.append("low_res")
    if width_px and height_px:
        aspect = width_px / height_px
        if aspect > WIDE_ASPECT or aspect < (1 / WIDE_ASPECT):
            flags.append("very_wide")
    return flags


# ---------------------------------------------------------------------------
# .docx
# ---------------------------------------------------------------------------

def extract_docx_assets(path, document_id, assets_dir):
    import xml.etree.ElementTree as ET

    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
        rels_path = "word/_rels/document.xml.rels"
        rels = {}
        if rels_path in zf.namelist():
            rroot = ET.fromstring(zf.read(rels_path))
            for rel in rroot:
                rels[rel.get("Id")] = rel.get("Target")

        body = root.find("w:body", WNS)
        if body is None:
            sys.exit(f"{path}: no <w:body> found — is this a valid .docx?")

        headings = HeadingStack(document_id)
        raw = []  # entries pending resolution to media bytes

        children = list(body)
        for i, child in enumerate(children):
            tag = child.tag.split("}", 1)[-1]
            if tag != "p":
                continue
            heading = docx_heading_from_paragraph(child)
            if heading:
                level, title, clause = heading
                headings.open_heading(level, title, clause_number=clause)
                continue
            for blip in child.findall(".//a:blip", WNS):
                embed_ns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
                rid = blip.get(embed_ns)
                target = rels.get(rid)
                if not target:
                    continue
                docPr = child.find(".//wp:docPr", {
                    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
                })
                alt = None
                if docPr is not None:
                    alt = docPr.get("descr") or docPr.get("name")
                caption = None
                for nxt in children[i + 1:]:
                    if nxt.tag.split("}", 1)[-1] != "p":
                        break
                    ctext = docx_paragraph_text(nxt)
                    if ctext:
                        caption = ctext
                    break
                raw.append({
                    "target": target,
                    "alt_text": alt,
                    "section_id": headings.current_section_id,
                    "nearest_heading": headings.current_title,
                    "caption_candidate": caption,
                })

        member_prefix = "word/"
        assets = []
        for entry in raw:
            member = member_prefix + entry["target"].lstrip("/")
            if member not in zf.namelist():
                print(f"  warning: media part missing: {member}", file=sys.stderr)
                continue
            data = zf.read(member)
            assets.append((data, entry))

    return _finish(assets, document_id, assets_dir, ext_hint=lambda t: Path(t["target"]).suffix.lstrip("."))


# ---------------------------------------------------------------------------
# .pptx (as a source document)
# ---------------------------------------------------------------------------

def extract_pptx_assets(path, document_id, assets_dir):
    import xml.etree.ElementTree as ET

    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        slide_names = sorted(
            (n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)),
            key=lambda n: int(re.search(r"\d+", Path(n).stem).group()),
        )
        raw = []
        for i, name in enumerate(slide_names, start=1):
            slide_root = ET.fromstring(zf.read(name))
            title = None
            for sp in slide_root.iterfind(".//p:sp", PNS):
                ph = sp.find(".//p:nvSpPr/p:nvPr/p:ph", PNS)
                if ph is not None and ph.get("type") in ("title", "ctrTitle"):
                    title = "".join(t.text or "" for t in sp.iterfind(".//a:t", PNS)).strip()
                    break
            title = title or f"Slide {i}"
            section_id = f"{document_id}#slide{i}"

            rels_name = f"ppt/slides/_rels/slide{i}.xml.rels"
            rels = {}
            if rels_name in names:
                rroot = ET.fromstring(zf.read(rels_name))
                for rel in rroot:
                    if "image" in rel.get("Type", ""):
                        rels[rel.get("Id")] = rel.get("Target")

            for pic in slide_root.iterfind(".//p:pic", PNS):
                blip = pic.find(".//a:blip", PNS)
                if blip is None:
                    continue
                embed_ns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
                rid = blip.get(embed_ns)
                target = rels.get(rid)
                if not target:
                    continue
                nv = pic.find(".//p:nvPicPr/p:cNvPr", PNS)
                alt = nv.get("descr") or nv.get("name") if nv is not None else None
                raw.append({
                    "target": target,
                    "alt_text": alt,
                    "section_id": section_id,
                    "nearest_heading": title,
                    "caption_candidate": None,
                    "slide_dir": f"ppt/slides/",
                })

        assets = []
        for entry in raw:
            target = entry["target"]
            member = target if target.startswith("ppt/") else "ppt/slides/" + target
            member = re.sub(r"^ppt/slides/\.\./", "ppt/", member)
            if member not in names:
                print(f"  warning: media part missing: {member}", file=sys.stderr)
                continue
            assets.append((zf.read(member), entry))

    return _finish(assets, document_id, assets_dir, ext_hint=lambda t: Path(t["target"]).suffix.lstrip("."))


# ---------------------------------------------------------------------------
# .pdf
# ---------------------------------------------------------------------------

def extract_pdf_assets(path, document_id, assets_dir):
    if not shutil.which("pdfimages"):
        sys.exit(
            f"{path}: 'pdfimages' not found. Install poppler, or run the pdf skill's "
            f"own extraction and point this script at the resulting image files "
            f"directly (not supported yet — extract via:\n"
            f"  pdfimages -all -p {path} {assets_dir}/{document_id}-img\n"
            f"then wire the results in by hand)."
        )
    assets_dir.mkdir(parents=True, exist_ok=True)
    prefix = str(assets_dir / f"{document_id}-raw")
    result = subprocess.run(
        ["pdfimages", "-all", "-p", str(path), prefix],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        sys.exit(f"pdfimages failed on {path}:\n{result.stderr}")

    raw_files = sorted(Path(assets_dir).glob(f"{document_id}-raw-*"))
    assets = []
    for f in raw_files:
        m = re.search(r"-(\d+)-\d+\.\w+$", f.name)
        page = int(m.group(1)) if m else None
        entry = {
            "target": f.name,
            "alt_text": None,
            "section_id": None,
            "nearest_heading": None,
            "caption_candidate": None,
            "page": page,
        }
        assets.append((f.read_bytes(), entry))
        f.unlink()  # replaced by the canonical asset_id-named file in _finish()

    return _finish(assets, document_id, assets_dir, ext_hint=lambda t: Path(t["target"]).suffix.lstrip("."))


# ---------------------------------------------------------------------------
# shared: dimension-check, noise-filter, write out, build index entries
# ---------------------------------------------------------------------------

def _finish(assets, document_id, assets_dir, ext_hint):
    """assets: list of (raw_bytes, entry_dict). Writes survivors to assets_dir and
    returns asset_index entries, having applied the repeat-count / min-size drop."""
    assets_dir.mkdir(parents=True, exist_ok=True)

    # Content-based repeat counting (exact byte match), independent of role/format.
    counts = {}
    for data, _ in assets:
        counts[data] = counts.get(data, 0) + 1

    kept, dropped = [], 0
    for i, (data, entry) in enumerate(assets):
        w, h, fmt = image_dimensions(data)
        repeat_count = counts[data]
        is_vector = fmt in ("svg", "emf", "wmf")
        if not is_vector and (0 < w < HARD_DROP_MIN_PX or 0 < h < HARD_DROP_MIN_PX):
            dropped += 1
            continue
        if repeat_count > HARD_DROP_REPEAT:
            dropped += 1
            continue
        kept.append((i, data, entry, w, h, fmt, repeat_count))

    out = []
    for order, (orig_i, data, entry, w, h, fmt, repeat_count) in enumerate(kept, start=1):
        asset_id = f"{document_id}-img-{order:03d}"
        out_ext = fmt if fmt != "other" else (ext_hint(entry) or "bin")
        out_file = assets_dir / f"{asset_id}.{out_ext}"
        out_file.write_bytes(data)
        record = {
            "asset_id": asset_id,
            "document_id": document_id,
            "file": str(out_file),
            "format": fmt,
            "width_px": w,
            "height_px": h,
            "doc_order_index": order,
            "section_id": entry.get("section_id"),
            "nearest_heading": entry.get("nearest_heading"),
            "caption_candidate": entry.get("caption_candidate"),
            "alt_text": entry.get("alt_text"),
            "repeat_count": repeat_count,
            "role": guess_role(w, h, fmt, repeat_count),
            "quality": quality_flags(w, h),
        }
        if w and h:
            record["aspect"] = round(w / h, 4)
        out.append(record)

    return out, dropped


PARSERS = {".docx": extract_docx_assets, ".pptx": extract_pptx_assets, ".pdf": extract_pdf_assets}


def discover_inputs(paths):
    files = []
    for p in paths:
        if p.is_dir():
            for ext in PARSERS:
                files.extend(sorted(p.glob(f"*{ext}")))
        elif p.suffix.lower() in PARSERS:
            files.append(p)
    return files


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "doc"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", type=Path, help="Input files and/or a directory containing them")
    ap.add_argument("--assets", type=Path, required=True, help="Directory to write extracted image files into")
    ap.add_argument("-o", "--out", type=Path, default=Path("asset_index.json"))
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    files = discover_inputs(args.inputs)
    if not files:
        sys.exit("no .docx/.pptx/.pdf inputs found")

    all_assets, total_dropped = [], 0
    used_ids = set()
    for f in files:
        base = slugify(f.stem)
        document_id = base
        n = 2
        while document_id in used_ids:
            document_id = f"{base}-{n}"
            n += 1
        used_ids.add(document_id)

        print(f"extracting images from {f} as {document_id}")
        parser = PARSERS[f.suffix.lower()]
        assets, dropped = parser(f, document_id, args.assets)
        all_assets.extend(assets)
        total_dropped += dropped

    run_id = args.run_id or slugify(files[0].stem)
    index = {"run_id": run_id, "assets": all_assets}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(index, indent=2), encoding="utf-8")

    by_role = {}
    for a in all_assets:
        by_role[a["role"]] = by_role.get(a["role"], 0) + 1
    print(f"\n{len(all_assets)} asset(s) kept, {total_dropped} dropped as noise "
          f"(repeated letterhead or under {HARD_DROP_MIN_PX}px) -> {args.out}")
    for role, n in sorted(by_role.items()):
        print(f"  {role:<16} {n}")
    screenshot_n = by_role.get("screenshot", 0)
    if screenshot_n:
        print(f"\n{screenshot_n} screenshot(s) — each needs placing or an entry in "
              f"qa_report.md's unused_assets, or Stage 5 will flag it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
