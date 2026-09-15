#!/usr/bin/env python3
"""Insert a picture or a rendered diagram fragment into an unpacked slide (Stage 4).

    python inject_slide_xml.py picture unpacked/ ppt/slides/slide7.xml \\
        --image training/<run>/assets/fsd-img-014.png --bbox 0.6,1.8,8.5,4.5 \\
        --alt "Approval screen"

    python inject_slide_xml.py diagram unpacked/ ppt/slides/slide9.xml \\
        --fragment training/<run>/diagrams/approval-flow.xml

These are the two operations too fiddly to repeat by hand across dozens of slides, per
the pptx skill's own unzip -> edit ppt/slides/slideN.xml -> rezip workflow — this script
does the editing step for these two block kinds only; everything else in that workflow
(add_slide.py, clean.py, the zip/validate commands) stays exactly as the pptx skill
documents it. Run this **after** all structural work (add_slide.py, slide reordering,
deletions) is done, per that skill's own ordering rule.

**A picture insert always writes three things together — media part, slide relationship,
and the `<p:pic>` reference — or the deck is corrupt.** This script writes all three or
none: it fails before touching the slide XML if the media copy or the relationship can't
be written.

The image is aspect-fit into `--bbox` (a placeholder's geometry from template_profile.json,
or any target rectangle), centered, never stretched — matching the pptx skill's own "never
distort" rule for template art.

A diagram fragment (from render_diagram.py) is imported whole via `dom.importNode` and its
shape ids renumbered above the slide's current maximum, so multiple diagrams — or a diagram
alongside slide content duplicated by add_slide.py — never collide.

Depends on `defusedxml` (falls back to stdlib `xml.dom.minidom` with a warning if absent —
the pptx skill's own warning about ElementTree *round-tripping* OOXML is about
xml.etree.ElementTree specifically; this script only ever uses minidom, in-place, and never
touches namespace prefixes it didn't write itself).
"""

import argparse
import re
import shutil
import struct
import sys
from pathlib import Path

try:
    import defusedxml.minidom as minidom
except ImportError:
    import xml.dom.minidom as minidom
    print("warning: defusedxml not installed — using stdlib xml.dom.minidom instead", file=sys.stderr)

EMU_PER_INCH = 914400
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
IMAGE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"

CONTENT_TYPE_BY_EXT = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "gif": "image/gif", "bmp": "image/bmp", "emf": "image/x-emf", "wmf": "image/x-wmf",
}


def _emu(inches):
    return int(round(inches * EMU_PER_INCH))


def image_pixel_size(data):
    """Minimal re-implementation of extract_assets.py's dimension sniff — kept local
    so inject_slide_xml.py has no dependency on that script."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        return w, h
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
                return w, h
            i += 2 + seg_len
        return None
    if data[:6] in (b"GIF87a", b"GIF89a"):
        w, h = struct.unpack("<HH", data[6:10])
        return w, h
    if data[:2] == b"BM":
        w, h = struct.unpack("<ii", data[18:26])
        return w, abs(h)
    return None


def fit_extent(bbox, img_w_px, img_h_px):
    """Aspect-fit img into bbox=(x,y,w,h) in inches, centered. Returns (x,y,w,h) in inches."""
    bx, by, bw, bh = bbox
    if not img_w_px or not img_h_px:
        return bbox
    img_aspect = img_w_px / img_h_px
    box_aspect = bw / bh
    if img_aspect > box_aspect:
        w = bw
        h = bw / img_aspect
    else:
        h = bh
        w = bh * img_aspect
    x = bx + (bw - w) / 2
    y = by + (bh - h) / 2
    return (x, y, w, h)


# ---------------------------------------------------------------------------
# shared plumbing: ids, rels, content types
# ---------------------------------------------------------------------------

def load_slide_dom(slide_path):
    return minidom.parse(str(slide_path))


def find_sptree(dom):
    trees = dom.getElementsByTagName("p:spTree")
    if not trees:
        sys.exit(f"no <p:spTree> found — is this a valid slide XML?")
    return trees[0]


def max_shape_id(dom):
    max_id = 1
    for el in dom.getElementsByTagName("p:cNvPr"):
        try:
            max_id = max(max_id, int(el.getAttribute("id")))
        except (ValueError, TypeError):
            continue
    return max_id


def rels_path_for(slide_path):
    slide_path = Path(slide_path)
    return slide_path.parent / "_rels" / (slide_path.name + ".rels")


def load_or_init_rels(rels_file):
    if rels_file.is_file():
        return minidom.parse(str(rels_file))
    dom = minidom.Document()
    root = dom.createElementNS(REL_NS, "Relationships")
    root.setAttribute("xmlns", REL_NS)
    dom.appendChild(root)
    return dom


def next_rid(rels_dom):
    max_n = 0
    for el in rels_dom.getElementsByTagName("Relationship"):
        m = re.match(r"rId(\d+)$", el.getAttribute("Id") or "")
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"rId{max_n + 1}"

def add_relationship(rels_dom, rel_type, target):
    root = rels_dom.documentElement
    rid = next_rid(rels_dom)
    rel = rels_dom.createElement("Relationship")
    rel.setAttribute("Id", rid)
    rel.setAttribute("Type", rel_type)
    rel.setAttribute("Target", target)
    root.appendChild(rel)
    return rid


def ensure_content_type(unpacked_dir, ext, content_type):
    ct_path = Path(unpacked_dir) / "[Content_Types].xml"
    dom = minidom.parse(str(ct_path))
    for el in dom.getElementsByTagName("Default"):
        if el.getAttribute("Extension").lower() == ext.lower():
            dom.unlink()
            return
    root = dom.documentElement
    default = dom.createElement("Default")
    default.setAttribute("Extension", ext)
    default.setAttribute("ContentType", content_type)
    root.appendChild(default)
    ct_path.write_text(dom.toxml(encoding="UTF-8").decode("utf-8"), encoding="utf-8")
    dom.unlink()


def next_media_filename(unpacked_dir, ext):
    media_dir = Path(unpacked_dir) / "ppt" / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    max_n = 0
    for f in media_dir.glob("image*"):
        m = re.match(r"image(\d+)\.", f.name)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"image{max_n + 1}.{ext}"


# ---------------------------------------------------------------------------
# picture insertion
# ---------------------------------------------------------------------------

def insert_picture(unpacked_dir, slide_rel_path, image_path, bbox, alt_text=None, name=None):
    unpacked_dir = Path(unpacked_dir)
    slide_path = unpacked_dir / slide_rel_path
    image_path = Path(image_path)
    if not slide_path.is_file():
        sys.exit(f"slide not found: {slide_path}")
    if not image_path.is_file():
        sys.exit(f"image not found: {image_path}")

    data = image_path.read_bytes()
    ext = image_path.suffix.lstrip(".").lower()
    content_type = CONTENT_TYPE_BY_EXT.get(ext)
    if not content_type:
        sys.exit(f"unrecognized image extension '.{ext}' — supported: {sorted(CONTENT_TYPE_BY_EXT)}")

    dims = image_pixel_size(data)
    fitted = fit_extent(bbox, *dims) if dims else bbox

    # 1. media part
    media_name = next_media_filename(unpacked_dir, ext)
    media_dest = unpacked_dir / "ppt" / "media" / media_name
    media_dest.write_bytes(data)

    # 2. content type (idempotent) + relationship
    ensure_content_type(unpacked_dir, ext, content_type)
    rels_file = rels_path_for(slide_path)
    rels_dom = load_or_init_rels(rels_file)
    rid = add_relationship(rels_dom, IMAGE_REL_TYPE, f"../media/{media_name}")
    rels_file.parent.mkdir(parents=True, exist_ok=True)
    rels_file.write_text(rels_dom.toxml(encoding="UTF-8").decode("utf-8"), encoding="utf-8")
    rels_dom.unlink()

    # 3. <p:pic> in the slide's spTree
    dom = load_slide_dom(slide_path)
    sptree = find_sptree(dom)
    shape_id = max_shape_id(dom) + 1
    shape_name = name or f"Picture {shape_id}"
    alt = (alt_text or "").replace("&", "&amp;").replace('"', "&quot;")

    x, y, w, h = fitted
    pic_xml = f'''<p:pic xmlns:p="{P_NS}" xmlns:a="{A_NS}" xmlns:r="{R_NS}">
  <p:nvPicPr>
    <p:cNvPr id="{shape_id}" name="{shape_name}" descr="{alt}"/>
    <p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr>
    <p:nvPr/>
  </p:nvPicPr>
  <p:blipFill>
    <a:blip r:embed="{rid}"/>
    <a:stretch><a:fillRect/></a:stretch>
  </p:blipFill>
  <p:spPr>
    <a:xfrm><a:off x="{_emu(x)}" y="{_emu(y)}"/><a:ext cx="{_emu(w)}" cy="{_emu(h)}"/></a:xfrm>
    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
  </p:spPr>
</p:pic>'''
    pic_dom = minidom.parseString(pic_xml)
    imported = dom.importNode(pic_dom.documentElement, deep=True)
    sptree.appendChild(imported)
    pic_dom.unlink()

    slide_path.write_text(dom.toxml(encoding="UTF-8").decode("utf-8"), encoding="utf-8")
    dom.unlink()

    print(f"inserted picture {media_name} -> {slide_rel_path} as shape {shape_id} "
          f"at {x:.2f},{y:.2f} {w:.2f}x{h:.2f}in (rel {rid})")
    return shape_id


# ---------------------------------------------------------------------------
# diagram fragment insertion
# ---------------------------------------------------------------------------

def _renumber_ids(fragment_root, start_id):
    next_id = [start_id]
    for el in fragment_root.getElementsByTagName("p:cNvPr"):
        el.setAttribute("id", str(next_id[0]))
        next_id[0] += 1
    return next_id[0]


def insert_diagram(unpacked_dir, slide_rel_path, fragment_path):
    unpacked_dir = Path(unpacked_dir)
    slide_path = unpacked_dir / slide_rel_path
    fragment_path = Path(fragment_path)
    if not slide_path.is_file():
        sys.exit(f"slide not found: {slide_path}")
    if not fragment_path.is_file():
        sys.exit(f"diagram fragment not found: {fragment_path}")

    dom = load_slide_dom(slide_path)
    sptree = find_sptree(dom)
    start_id = max_shape_id(dom) + 1

    fragment_dom = minidom.parse(str(fragment_path))
    fragment_root = fragment_dom.documentElement
    if fragment_root.tagName != "p:grpSp":
        sys.exit(f"{fragment_path} is not a <p:grpSp> fragment (got <{fragment_root.tagName}>) "
                  f"— was it produced by render_diagram.py?")

    imported = dom.importNode(fragment_root, deep=True)
    end_id = _renumber_ids(imported, start_id)
    sptree.appendChild(imported)
    fragment_dom.unlink()

    slide_path.write_text(dom.toxml(encoding="UTF-8").decode("utf-8"), encoding="utf-8")
    dom.unlink()

    print(f"inserted diagram {fragment_path.name} -> {slide_rel_path}, "
          f"shape ids {start_id}-{end_id - 1}")
    return start_id


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    p_pic = sub.add_parser("picture", help="Insert an image as a p:pic, aspect-fit into --bbox")
    p_pic.add_argument("unpacked_dir", type=Path)
    p_pic.add_argument("slide", help="Slide part path relative to unpacked_dir, e.g. ppt/slides/slide7.xml")
    p_pic.add_argument("--image", required=True, type=Path)
    p_pic.add_argument("--bbox", required=True, help="x_in,y_in,w_in,h_in — the target placeholder's geometry")
    p_pic.add_argument("--alt", default=None, help="Alt text / caption for accessibility")
    p_pic.add_argument("--name", default=None)

    p_diag = sub.add_parser("diagram", help="Import a render_diagram.py fragment into the slide")
    p_diag.add_argument("unpacked_dir", type=Path)
    p_diag.add_argument("slide", help="Slide part path relative to unpacked_dir")
    p_diag.add_argument("--fragment", required=True, type=Path)

    args = ap.parse_args()

    if args.command == "picture":
        bbox = tuple(float(v) for v in args.bbox.split(","))
        if len(bbox) != 4:
            sys.exit("--bbox must be x_in,y_in,w_in,h_in")
        insert_picture(args.unpacked_dir, args.slide, args.image, bbox, alt_text=args.alt, name=args.name)
    elif args.command == "diagram":
        insert_diagram(args.unpacked_dir, args.slide, args.fragment)
    return 0


if __name__ == "__main__":
    sys.exit(main())
