"""Profile a slide template: what layouts exist and what each one can hold.

Two template kinds, one output schema:

  * **.potx/.pptx** — reads ppt/slideLayouts/*.xml for layouts and placeholders.
  * **a directory** — an HTML template; reads layouts.html for <template data-layout>
    blocks and their {{placeholder}} tokens.

Because both kinds emit the same profile, `manifest.build()` validates a plan identically
against either — only the renderer downstream differs. Profiling an HTML template is also
what keeps its profile honest: the placeholder list is derived from layouts.html itself, so
editing a layout cannot silently drift from the profile a plan is checked against.

Stdlib only. A .pptx/.potx is a ZIP of XML, and reading it needs no dependencies. Note the
pptx skill's warning about ElementTree *writing* OOXML; this module only reads, never
round-trips, so that hazard does not apply.

Errors are raised as ValueError rather than exited on — the CLI wrappers in each skill's
scripts/ decide how to report them.
"""

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from .htmlkit import COMMENT_RE, OPTIONAL_RE, TEMPLATE_BLOCK_RE, TOKEN_RE

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


def profile_html_template(template_dir):
    """Profile an HTML template directory by reading its layouts.html."""
    template_dir = Path(template_dir)
    layouts_file = template_dir / "layouts.html"
    if not layouts_file.is_file():
        raise ValueError(f"HTML template has no layouts.html: {layouts_file}")

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
        raise ValueError(f'no <template data-layout="..."> blocks found in {layouts_file}')

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


def profile_pptx_template(path, on_parse_error=None):
    """Profile a .potx/.pptx by reading its slideLayouts and theme.

    `on_parse_error(part_name, exc)` is called for a layout part that will not parse, so
    the caller decides how loud to be; the layout is skipped either way.
    """
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"template not found: {path}")
    if path.suffix.lower() not in (".potx", ".pptx"):
        raise ValueError(
            f"expected .potx, .pptx, or an HTML template directory; got {path.suffix}"
        )

    layouts, theme_fonts = [], {}
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()

        for name in sorted(n for n in names if n.startswith("ppt/slideLayouts/slideLayout")):
            try:
                layouts.append(profile_layout(zf.read(name), name))
            except ET.ParseError as exc:
                if on_parse_error:
                    on_parse_error(name, exc)

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

    return {
        "template": str(path),
        "kind": "pptx",
        "renderer": "pptx skill (template workflow)",
        "layout_count": len(layouts),
        "master_count": master_count,
        "example_slide_count": slide_count,
        "theme_fonts": theme_fonts,
        "layouts": layouts,
    }


def profile(path, on_parse_error=None):
    """Profile whichever kind of template `path` is."""
    path = Path(path)
    if path.is_dir():
        return profile_html_template(path)
    return profile_pptx_template(path, on_parse_error=on_parse_error)
