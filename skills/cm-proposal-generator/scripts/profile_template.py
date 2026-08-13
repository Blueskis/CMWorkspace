#!/usr/bin/env python3
"""Profile a proposal template: what layouts exist and what each one can hold.

    python profile_template.py proposal-assets/templates/firm.potx        -o profile.json
    python profile_template.py proposal-assets/templates/html-generic/    -o profile.json

Two template kinds, one output schema:

  * **.potx/.pptx** — reads ppt/slideLayouts/*.xml for layouts and placeholders.
  * **a directory** — an HTML template; reads layouts.html for <template data-layout>
    blocks and their {{placeholder}} tokens.

Stage 3 needs to know which layouts are available before planning slides, and Stage 5
needs each layout's placeholder inventory to fill it. Because both kinds emit the same
profile, build_deck.py validates a proposal plan identically against either — only the
renderer downstream differs.

Profiling an HTML template is also what keeps its profile honest: the placeholder list is
derived from layouts.html itself, so editing a layout can't silently drift from the
profile a plan is checked against.

Stdlib only. A .pptx/.potx is a ZIP of XML, and reading it needs no dependencies. Note the
pptx skill's warning about ElementTree *writing* OOXML; this script only reads, never
round-trips, so that hazard doesn't apply here.

Pair with the pptx skill's `scripts/thumbnail.py` for the visual side of a .potx: this
tells you what a layout contains, the thumbnail grid tells you what it looks like.
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
TEMPLATE_BLOCK_RE = re.compile(
    r'<template\s+data-layout="([^"]+)"\s*>(.*?)</template>', re.DOTALL
)
OPTIONAL_RE = re.compile(r"\{\{#([a-z_]+)\}\}(.*?)\{\{/\1\}\}", re.DOTALL)
TOKEN_RE = re.compile(r"\{\{([a-z_]+)\}\}")

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}
EMU_PER_INCH = 914400


def _text_of(shape):
    return " ".join(t.text or "" for t in shape.iterfind(".//a:t", NS)).strip()


def _font_size_pt(shape):
    """Point size the layout sets for this placeholder's first outline level, if any.

    Renderers use it to estimate whether planned text will fit the box. A layout that
    leaves the size to the master returns None, and the caller falls back to a default —
    an estimate from the wrong size is worse than an admitted absence.
    """
    for path in (".//a:lstStyle/a:lvl1pPr/a:defRPr", ".//a:pPr/a:defRPr", ".//a:rPr"):
        el = shape.find(path, NS)
        if el is not None and el.get("sz"):
            return int(el.get("sz")) / 100
    return None


def _geometry(shape):
    xfrm = shape.find(".//a:xfrm", NS)
    if xfrm is None:
        return None
    off, ext = xfrm.find("a:off", NS), xfrm.find("a:ext", NS)
    if off is None or ext is None:
        return None
    return {
        "x_in": round(int(off.get("x", 0)) / EMU_PER_INCH, 2),
        "y_in": round(int(off.get("y", 0)) / EMU_PER_INCH, 2),
        "w_in": round(int(ext.get("cx", 0)) / EMU_PER_INCH, 2),
        "h_in": round(int(ext.get("cy", 0)) / EMU_PER_INCH, 2),
    }


def profile_layout(xml_bytes, part_name):
    root = ET.fromstring(xml_bytes)
    placeholders = []

    for shape in root.iterfind(".//p:sp", NS):
        nv = shape.find(".//p:nvSpPr/p:nvPr/p:ph", NS)
        if nv is None:
            continue
        name_el = shape.find(".//p:nvSpPr/p:cNvPr", NS)
        placeholders.append(
            {
                "type": nv.get("type", "body"),
                "idx": nv.get("idx"),
                "name": name_el.get("name") if name_el is not None else None,
                "prompt_text": _text_of(shape) or None,
                "geometry": _geometry(shape),
                "font_size_pt": _font_size_pt(shape),
            }
        )

    pics = len(list(root.iterfind(".//p:pic", NS)))
    graphics = len(list(root.iterfind(".//p:graphicFrame", NS)))

    csld = root.find("p:cSld", NS)
    name = csld.get("name") if csld is not None else None

    return {
        "part": part_name,
        "name": name,
        "type": root.get("type"),
        "placeholder_count": len(placeholders),
        "placeholders": placeholders,
        "static_images": pics,
        "graphic_frames": graphics,
    }


def profile_html_template(template_dir):
    """Profile an HTML template directory by reading its layouts.html."""
    layouts_file = template_dir / "layouts.html"
    if not layouts_file.is_file():
        sys.exit(f"HTML template has no layouts.html: {layouts_file}")

    # Strip comments first — the file documents its own format using <template
    # data-layout="..."> in prose, which would otherwise parse as a layout.
    source = COMMENT_RE.sub("", layouts_file.read_text(encoding="utf-8"))
    layouts = []

    for layout_id, body in TEMPLATE_BLOCK_RE.findall(source):
        optional = set()
        for name, inner in OPTIONAL_RE.findall(body):
            optional.add(name)
            optional.update(TOKEN_RE.findall(inner) or [])
        # A token is optional if it is the subject of, or sits inside, a {{#...}} block.
        placeholders = []
        for name in dict.fromkeys(TOKEN_RE.findall(body)):
            placeholders.append(
                {
                    "type": name,
                    "idx": None,
                    "name": name,
                    "required": name not in optional,
                    "prompt_text": None,
                    "geometry": None,
                    "font_size_pt": None,
                }
            )
        layouts.append(
            {
                "part": layout_id,
                "name": layout_id.replace("-", " ").title(),
                "type": "html",
                "placeholder_count": len(placeholders),
                "placeholders": placeholders,
                "static_images": 0,
                "graphic_frames": 0,
            }
        )

    if not layouts:
        sys.exit(f"no <template data-layout=\"...\"> blocks found in {layouts_file}")

    return {
        "template": str(template_dir),
        "kind": "html",
        "renderer": "render_html.py",
        "layout_count": len(layouts),
        "master_count": 1,
        "example_slide_count": 0,
        "theme_fonts": {},
        "layouts": layouts,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("template", type=Path,
                    help=".potx/.pptx file, or an HTML template directory containing layouts.html")
    ap.add_argument("-o", "--out", type=Path, default=Path("template_profile.json"))
    args = ap.parse_args()

    if args.template.is_dir():
        profile = profile_html_template(args.template)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        print(f"Profiled {profile['layout_count']} HTML layouts from {args.template} -> {args.out}")
        for layout in profile["layouts"]:
            required = [p["name"] for p in layout["placeholders"] if p["required"]]
            optional = [p["name"] for p in layout["placeholders"] if not p["required"]]
            print(f"  {layout['part']:<20} required: {', '.join(required) or '—'}")
            if optional:
                print(f"  {'':<20} optional: {', '.join(optional)}")
        return 0

    if not args.template.is_file():
        sys.exit(f"template not found: {args.template}")
    if args.template.suffix.lower() not in (".potx", ".pptx"):
        sys.exit(f"expected .potx, .pptx, or an HTML template directory; got {args.template.suffix}")

    layouts, theme_fonts = [], {}
    with zipfile.ZipFile(args.template) as zf:
        names = zf.namelist()

        for name in sorted(n for n in names if n.startswith("ppt/slideLayouts/slideLayout")):
            try:
                layouts.append(profile_layout(zf.read(name), name))
            except ET.ParseError as exc:
                print(f"  could not parse {name}: {exc}", file=sys.stderr)

        for name in (n for n in names if n.startswith("ppt/theme/theme")):
            root = ET.fromstring(zf.read(name))
            scheme = root.find(".//a:fontScheme", NS)
            if scheme is not None:
                major = scheme.find("a:majorFont/a:latin", NS)
                minor = scheme.find("a:minorFont/a:latin", NS)
                theme_fonts[name] = {
                    "major": major.get("typeface") if major is not None else None,
                    "minor": minor.get("typeface") if minor is not None else None,
                }

        slide_count = sum(1 for n in names if n.startswith("ppt/slides/slide"))
        master_count = sum(1 for n in names if n.startswith("ppt/slideMasters/slideMaster"))

    profile = {
        "template": str(args.template),
        "kind": "pptx",
        "renderer": "pptx skill (template workflow)",
        "layout_count": len(layouts),
        "master_count": master_count,
        "example_slide_count": slide_count,
        "theme_fonts": theme_fonts,
        "layouts": layouts,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(profile, indent=2), encoding="utf-8")

    print(f"Profiled {len(layouts)} layouts from {args.template.name} -> {args.out}")
    for layout in layouts:
        kinds = ", ".join(sorted({p["type"] for p in layout["placeholders"]})) or "none"
        print(f"  {Path(layout['part']).stem:<16} {layout['name'] or '(unnamed)':<32} "
              f"{layout['placeholder_count']} ph ({kinds})")
    if slide_count:
        print(f"\n{slide_count} example slide(s) present — thumbnail them "
              f"(pptx skill: scripts/thumbnail.py) to see the intended house style.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
