#!/usr/bin/env python3
"""Profile an approved .potx/.pptx template: what layouts exist and what each can hold.

    python profile_template.py proposal-assets/templates/firm.potx -o template_profile.json

Stage 2 needs to know which layouts are available before planning slides, and Stage 4
needs each layout's placeholder inventory to fill it. Reading that from the template
means the plan can only ever reference layouts the approved template actually has.

Stdlib only (zipfile + ElementTree) — a .pptx/.potx is a ZIP of XML, and reading it needs
no dependencies. Note the pptx skill's warning about ElementTree *writing* OOXML; this
script only reads, never round-trips, so that hazard doesn't apply here.

Pair with the pptx skill's `scripts/thumbnail.py` for the visual side: this tells you what
a layout contains, the thumbnail grid tells you what it looks like. Choose layouts using
both.
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}
EMU_PER_INCH = 914400


def _text_of(shape):
    return " ".join(t.text or "" for t in shape.iterfind(".//a:t", NS)).strip()


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


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("template", type=Path, help=".potx or .pptx — the firm's approved template")
    ap.add_argument("-o", "--out", type=Path, default=Path("template_profile.json"))
    args = ap.parse_args()

    if not args.template.is_file():
        sys.exit(f"template not found: {args.template}")
    if args.template.suffix.lower() not in (".potx", ".pptx"):
        sys.exit(f"expected .potx or .pptx, got {args.template.suffix}")

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
