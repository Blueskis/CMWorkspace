#!/usr/bin/env python3
"""Render a proposal plan into a real .pptx built on an approved template (Stage 5).

    python render_pptx.py proposals/<run>/proposal_plan.json \\
        proposal-assets/templates/pptx-generic/pptx-generic.potx \\
        -o proposals/<run>/proposal.pptx

Takes the plan and the template, writes the deck. No manual OOXML step, no second tool.

## How it stays on the firm's template

The deck is the template. Every part of the source package — master, layouts, theme,
fonts, table styles — is carried across untouched; the only parts this script *adds* are
`ppt/slides/slideN.xml`, their relationships, and notes slides. Nothing is rebuilt from
scratch, so there is no lookalike to drift.

Within a slide, content goes into the layout's own placeholders, addressed by the
placeholder reference in the plan and resolved through `build_deck.py` (which also
handles aliasing onto a template that names things differently). Slide XML sets **no
fonts and no colours** — every run inherits from the layout, which inherits from the
master and the theme. That is a checkable property, and `qa_pptx.py` checks it: slide
XML carrying `<a:latin>` or `<a:srgbClr>` is off-template by definition.

Three kinds of content cannot live inside a text placeholder — tables, metric tiles,
phase strips and team grids are shapes, not paragraphs. Those are drawn at the
placeholder's own geometry, and they still name colours as theme slots (`accent1`,
`tx2`) and fonts as theme references (`+mj-lt`), so they follow the template's palette
rather than overriding it.

## What it refuses to do quietly

  * A block flagged `gap: true` becomes a visible amber `[GAP]` panel. Never substitute
    text, never a silent omission. Gap panels are the one place fixed colours are used —
    they are review annotations that have to stay legible on any template, including a
    template whose accent colour happens to be amber.
  * Text that will not fit its placeholder is reported, and the placeholder gets an
    autofit shrink so the overflow cannot silently clip. Both the warning and the shrink
    factor appear in the run output.
  * Every slide's knowledge-bank source IDs go into the layout's `footer` placeholder by
    default. `--sources hidden` is for a client-facing copy, once the practitioner has
    reviewed the provenance.

Stdlib only. A .pptx is a ZIP of XML; this script writes that XML as text rather than
round-tripping it through ElementTree, which is what the `pptx` skill warns against.
"""

import argparse
import html
import json
import math
import re
import struct
import sys
import zipfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_deck import build, load_map  # noqa: E402  (same-directory sibling modules)
from profile_template import profile_layout  # noqa: E402

EMU_PER_INCH = 914400
XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
NS_P = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"')
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CT_SLIDE = "application/vnd.openxmlformats-officedocument.presentationml.slide+xml"
CT_NOTES = "application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"
CT_PRESENTATION = ("application/vnd.openxmlformats-officedocument.presentationml."
                   "presentation.main+xml")
TABLE_STYLE_ID = "{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}"  # built-in Medium Style 2

# Gap panels are review annotations, not design. Fixed colours so they read as a warning
# on any template — including one whose own accent happens to be amber.
GAP_FILL = "FEF3C7"
GAP_LINE = "B45309"
GAP_TEXT = "78350F"

DEFAULT_BODY_PT = 18.0
DEFAULT_TITLE_PT = 26.0
MIN_FONT_SCALE = 0.70  # below this, shrinking is hiding a planning problem — warn instead

TEXT_KINDS = {"text", "heading", "paragraph", "bullets"}
SHAPE_KINDS = {"table", "metric", "phases", "members", "image"}


def esc(value):
    return html.escape(str(value), quote=True)


def emu(inches):
    return int(round(inches * EMU_PER_INCH))


def xfrm(x, y, w, h, tag="a"):
    return (f'<{tag}:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/>'
            f'<a:ext cx="{emu(w)}" cy="{emu(h)}"/></{tag}:xfrm>')


# --- text fitting ----------------------------------------------------------


def text_lines(paragraphs, chars_per_line):
    """Lines a set of paragraphs needs at a given wrap width."""
    return sum(max(1, math.ceil(len(p) / chars_per_line)) for p in paragraphs if p is not None)


def fit_ratio(paragraphs, geometry, font_pt):
    """How full a placeholder is: 1.0 is exactly full, >1 overflows.

    Deliberately a rough model — average glyph advance of half an em, line height of
    1.25. It is not trying to be a layout engine, only to catch the slide that is
    obviously too long while the plan can still be changed.
    """
    if not geometry or not font_pt:
        return None
    width_pt = geometry["w_in"] * 72
    height_pt = geometry["h_in"] * 72
    chars_per_line = max(1, int(width_pt / (font_pt * 0.5)))
    capacity = max(1.0, height_pt / (font_pt * 1.25))
    return text_lines(paragraphs, chars_per_line) / capacity


# --- block content -> paragraphs -------------------------------------------


def block_paragraphs(fill):
    """A text-kind fill as a list of (text, level, bullet) paragraphs.

    Only `bullets` gets bullets. A lead-in paragraph or a column heading that inherits
    the layout's bullet reads as a one-item list, which is how a generated deck starts
    looking generated.
    """
    kind, content = fill["kind"], fill["content"]
    if kind == "bullets":
        items = content if isinstance(content, list) else [content]
        return [(str(i), 0, True) for i in items]
    if kind == "paragraph":
        paras = content if isinstance(content, list) else [content]
        return [(str(p), 0, False) for p in paras]
    return [(str(content), 0, False)]


def para_xml(text, level=0, *, bullet=True, size_pt=None, colour=None, font=None,
             bold=False, caps=False, space_after=None):
    """One <a:p>. With no styling arguments it inherits everything from the layout."""
    props = []
    attrs = ""
    if not bullet:
        # Cancelling the bullet is not enough: the layout's hanging indent stays, so an
        # unbulleted paragraph wraps with its second line indented under nothing.
        attrs = ' marL="0" indent="0"'
        props.append("<a:buNone/>")
    if space_after is not None:
        props.append(f'<a:spcAft><a:spcPts val="{int(space_after)}"/></a:spcAft>')

    rpr_attrs = ['lang="en-GB"']
    if size_pt:
        rpr_attrs.append(f'sz="{int(round(size_pt * 100))}"')
    if bold:
        rpr_attrs.append('b="1"')
    if caps:
        rpr_attrs.append('cap="all"')
    rpr_children = ""
    if colour:
        rpr_children += f"<a:solidFill>{colour_fill(colour)}</a:solidFill>"
    if font:
        rpr_children += f'<a:latin typeface="{font}"/>'

    rpr = f'<a:rPr {" ".join(rpr_attrs)}>{rpr_children}</a:rPr>' if rpr_children else \
          f'<a:rPr {" ".join(rpr_attrs)}/>'
    lvl = f' lvl="{level}"' if level else ""
    ppr = f'<a:pPr{lvl}{attrs}>{"".join(props)}</a:pPr>' if (props or lvl or attrs) else ""
    return f'<a:p>{ppr}<a:r>{rpr}<a:t>{esc(text)}</a:t></a:r></a:p>'


# --- shapes ----------------------------------------------------------------


def placeholder_sp(shape_id, ph, paragraphs, *, font_scale=None, geometry_override=None):
    """A slide shape bound to a layout placeholder. Sets no fonts and no colours."""
    ph_attrs = f'type="{ph.get("type", "body")}"'
    if ph.get("idx") is not None:
        ph_attrs += f' idx="{ph["idx"]}"'

    autofit = "<a:normAutofit/>"
    if font_scale is not None and font_scale < 1.0:
        pct = int(round(font_scale * 100000))
        reduction = int(round((1 - font_scale) * 50000))
        autofit = f'<a:normAutofit fontScale="{pct}" lnSpcReduction="{reduction}"/>'

    sppr = f"<p:spPr>{xfrm(*geometry_override)}</p:spPr>" if geometry_override else "<p:spPr/>"
    body = "".join(para_xml(text, level, bullet=bullet)
                   for text, level, bullet in paragraphs) or \
        '<a:p><a:endParaRPr lang="en-GB"/></a:p>'

    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{esc(ph.get("name") or "Content")}"/>'
        f'<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
        f'<p:nvPr><p:ph {ph_attrs}/></p:nvPr></p:nvSpPr>'
        f'{sppr}'
        f'<p:txBody><a:bodyPr>{autofit}</a:bodyPr><a:lstStyle/>{body}</p:txBody></p:sp>'
    )


def text_box(shape_id, name, geom, paragraphs, *, fill_scheme=None, line_scheme=None,
             anchor="t", rounded=False, fill_hex=None, line_hex=None):
    """A free text shape for content that cannot live in a placeholder."""
    fill = "<a:noFill/>"
    if fill_hex:
        fill = f'<a:solidFill><a:srgbClr val="{fill_hex}"/></a:solidFill>'
    elif fill_scheme:
        fill = f'<a:solidFill><a:schemeClr val="{fill_scheme}"/></a:solidFill>'

    if line_hex:
        line = (f'<a:ln w="28575"><a:solidFill><a:srgbClr val="{line_hex}"/></a:solidFill>'
                f'</a:ln>')
    elif line_scheme:
        line = (f'<a:ln w="9525"><a:solidFill><a:schemeClr val="{line_scheme}"/>'
                f'</a:solidFill></a:ln>')
    else:
        line = "<a:ln><a:noFill/></a:ln>"

    geometry = 'roundRect' if rounded else 'rect'
    avlst = '<a:gd name="adj" fmla="val 6000"/>' if rounded else ""
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{esc(name)}"/>'
        f'<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr>{xfrm(*geom)}<a:prstGeom prst="{geometry}"><a:avLst>{avlst}</a:avLst>'
        f'</a:prstGeom>{fill}{line}</p:spPr>'
        f'<p:txBody><a:bodyPr anchor="{anchor}" wrap="square" lIns="91440" tIns="54864" '
        f'rIns="91440" bIns="54864"><a:normAutofit/></a:bodyPr><a:lstStyle/>'
        f'{"".join(paragraphs)}</p:txBody></p:sp>'
    )


def colour_fill(colour):
    """A hex literal or a theme slot name -> the matching DrawingML colour element."""
    if re.fullmatch(r"[0-9A-F]{6}", colour):
        return f'<a:srgbClr val="{colour}"/>'
    return f'<a:schemeClr val="{colour}"/>'


def rule(shape_id, name, x, y, w, colour, width_emu=28575):
    return (
        f'<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="{shape_id}" name="{esc(name)}"/>'
        f'<p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>'
        f'<p:spPr>{xfrm(x, y, w, 0)}<a:prstGeom prst="line"><a:avLst/></a:prstGeom>'
        f'<a:ln w="{width_emu}"><a:solidFill>{colour_fill(colour)}</a:solidFill></a:ln>'
        f'</p:spPr></p:cxnSp>'
    )


# --- composite content shapes ----------------------------------------------


def render_table(shape_id, geom, content, font_pt):
    headers = content.get("headers", []) if isinstance(content, dict) else []
    rows = content.get("rows", []) if isinstance(content, dict) else []
    cols = max(len(headers), max((len(r) for r in rows), default=0), 1)

    x, y, w, h = geom
    col_w = emu(w / cols)
    row_count = len(rows) + (1 if headers else 0)
    row_h = emu(min(0.42, h / max(row_count, 1)))

    def cell(text, *, header=False):
        # The pinned table style fills the header row with accent1, so header text is
        # the background colour, not the text colour — otherwise it is navy on blue.
        para = para_xml(text, bullet=False, size_pt=font_pt * (0.92 if header else 1.0),
                        colour="bg1" if header else "tx2", font="+mn-lt", bold=header,
                        caps=header, space_after=0)
        return (f'<a:tc><a:txBody><a:bodyPr/><a:lstStyle/>{para}</a:txBody>'
                f'<a:tcPr marL="68580" marR="68580" marT="45720" marB="45720" '
                f'anchor="t"/></a:tc>')

    trs = []
    if headers:
        trs.append(f'<a:tr h="{row_h}">' +
                   "".join(cell(c, header=True) for c in headers) +
                   "".join(cell("", header=True) for _ in range(cols - len(headers))) +
                   "</a:tr>")
    for row in rows:
        trs.append(f'<a:tr h="{row_h}">' +
                   "".join(cell(c) for c in row) +
                   "".join(cell("") for _ in range(cols - len(row))) +
                   "</a:tr>")

    grid = "".join(f'<a:gridCol w="{col_w}"/>' for _ in range(cols))
    return (
        f'<p:graphicFrame><p:nvGraphicFramePr>'
        f'<p:cNvPr id="{shape_id}" name="Table {shape_id}"/>'
        f'<p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr>'
        f'<p:nvPr/></p:nvGraphicFramePr>'
        f'{xfrm(x, y, w, h, tag="p")}'
        f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/'
        f'2006/table"><a:tbl>'
        f'<a:tblPr firstRow="1" bandRow="1"><a:tableStyleId>{TABLE_STYLE_ID}'
        f'</a:tableStyleId></a:tblPr>'
        f'<a:tblGrid>{grid}</a:tblGrid>'
        f'{"".join(trs)}</a:tbl></a:graphicData></a:graphic></p:graphicFrame>'
    )


def render_metrics(next_id, geom, content, font_pt):
    tiles = content if isinstance(content, list) else [content]
    x, y, w, h = geom
    gap = 0.18
    tile_w = (w - gap * (len(tiles) - 1)) / max(len(tiles), 1)
    shapes = []
    for i, tile in enumerate(tiles):
        paras = [
            para_xml(tile.get("value", ""), bullet=False, size_pt=font_pt * 1.9,
                     colour="tx1", font="+mj-lt", bold=True, space_after=200),
            para_xml(tile.get("label", ""), bullet=False, size_pt=font_pt * 0.62,
                     colour="tx2", font="+mn-lt", space_after=0),
        ]
        shapes.append(text_box(next_id + i, f"Metric {i + 1}",
                               (x + i * (tile_w + gap), y, tile_w, h), paras,
                               fill_scheme="accent6", anchor="ctr", rounded=True))
    return shapes


def render_phases(next_id, geom, content, font_pt):
    phases = content if isinstance(content, list) else [content]
    x, y, w, h = geom
    gap = 0.22
    col_w = (w - gap * (len(phases) - 1)) / max(len(phases), 1)
    shapes, shape_id = [], next_id
    for i, phase in enumerate(phases):
        col_x = x + i * (col_w + gap)
        shapes.append(rule(shape_id, f"Phase rule {i + 1}", col_x, y, col_w, "accent1"))
        shape_id += 1

        paras = [para_xml(phase.get("label", f"Phase {i + 1}"), bullet=False,
                          size_pt=font_pt * 0.7, colour="accent1", font="+mn-lt",
                          bold=True, caps=True, space_after=120),
                 para_xml(phase.get("name", ""), bullet=False, size_pt=font_pt * 1.05,
                          colour="tx1", font="+mj-lt", bold=True, space_after=200)]
        detail = phase.get("detail")
        for line in (detail if isinstance(detail, list) else ([detail] if detail else [])):
            paras.append(para_xml(f"— {line}", bullet=False, size_pt=font_pt * 0.78,
                                  colour="tx2", font="+mn-lt", space_after=140))
        shapes.append(text_box(shape_id, f"Phase {i + 1}",
                               (col_x, y + 0.08, col_w, h - 0.08), paras))
        shape_id += 1
    return shapes


def render_members(next_id, geom, content, font_pt):
    members = content if isinstance(content, list) else [content]
    x, y, w, h = geom
    cols = min(4, max(len(members), 1))
    rows = math.ceil(len(members) / cols)
    gap_x, gap_y = 0.24, 0.22
    card_w = (w - gap_x * (cols - 1)) / cols
    card_h = (h - gap_y * (rows - 1)) / rows

    shapes, shape_id = [], next_id
    for i, member in enumerate(members):
        cx = x + (i % cols) * (card_w + gap_x)
        cy = y + (i // cols) * (card_h + gap_y)
        name = str(member.get("name", ""))
        # A role profile can come from the bank while the person is still unconfirmed —
        # flag those names so an unstaffed slot reads as one rather than as a hire.
        is_gap = name.startswith("[GAP]")
        # Gap-flagged cards carry fixed amber like any other gap marker, so they take the
        # GAP-marker- name too — that prefix is what tells the fidelity scan these
        # colours are a deliberate annotation rather than the deck drifting off-template.
        label = f"GAP-marker-member-{i + 1}" if is_gap else f"Member {i + 1}"
        shapes.append(rule(shape_id, f"{label} rule", cx, cy, card_w,
                           GAP_LINE if is_gap else "accent3"))
        shape_id += 1

        paras = [para_xml(name, bullet=False, size_pt=font_pt * 1.05,
                          colour=GAP_LINE if is_gap else "tx1", font="+mj-lt", bold=True,
                          space_after=100),
                 para_xml(member.get("role", ""), bullet=False, size_pt=font_pt * 0.7,
                          colour="accent1", font="+mn-lt", bold=True, space_after=180),
                 para_xml(member.get("bio", ""), bullet=False, size_pt=font_pt * 0.78,
                          colour="tx2", font="+mn-lt", space_after=0)]
        shapes.append(text_box(shape_id, label,
                               (cx, cy + 0.06, card_w, card_h - 0.06), paras))
        shape_id += 1
    return shapes


def render_gap(shape_id, geom, note):
    paras = [
        para_xml("[GAP]", bullet=False, size_pt=11, colour=GAP_LINE, font="+mn-lt",
                 bold=True, caps=True, space_after=140),
        para_xml(note or "Not covered by the knowledge bank.", bullet=False, size_pt=13,
                 colour=GAP_TEXT, font="+mn-lt", space_after=0),
    ]
    return text_box(shape_id, f"GAP-marker-{shape_id}", geom, paras,
                    fill_hex=GAP_FILL, line_hex=GAP_LINE, rounded=True)


# --- images ----------------------------------------------------------------


def image_size_px(data):
    """(w, h) for PNG/JPEG, or None. Enough to preserve aspect ratio when placing."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker, length = data[i + 1], struct.unpack(">H", data[i + 2:i + 4])[0]
            if marker in range(0xC0, 0xCF) and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            i += 2 + length
    return None


def render_image(shape_id, geom, rid, data):
    x, y, w, h = geom
    size = image_size_px(data)
    if size and size[1]:
        ratio = size[0] / size[1]
        if w / h > ratio:      # box is wider than the image — pillarbox it
            new_w = h * ratio
            x, w = x + (w - new_w) / 2, new_w
        else:                  # box is taller — letterbox it
            new_h = w / ratio
            y, h = y + (h - new_h) / 2, new_h
    return (
        f'<p:pic><p:nvPicPr><p:cNvPr id="{shape_id}" name="Picture {shape_id}"/>'
        f'<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
        f'<p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch>'
        f'</p:blipFill>'
        f'<p:spPr>{xfrm(x, y, w, h)}<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        f'</p:spPr></p:pic>'
    )


# --- slide assembly --------------------------------------------------------


def geom_of(ph, fallback):
    g = ph.get("geometry")
    if not g:
        return fallback
    return (g["x_in"], g["y_in"], g["w_in"], g["h_in"])


STACK_GAP = 0.14


def desired_height(fill, width_in, font_pt):
    """Roughly how much vertical room a fill wants, for stacking several in one slot.

    Only consulted when a placeholder receives more than one block. A single block keeps
    the placeholder's full box, because the layout sized that box for it.
    """
    if fill.get("gap"):
        note = fill.get("gap_note") or ""
        per_line = max(1, int(width_in * 72 / (13 * 0.5)))
        return min(2.6, 0.55 + max(1, math.ceil(len(note) / per_line)) * 13 * 1.35 / 72)

    kind, content = fill["kind"], fill["content"]
    if kind == "table":
        rows = len(content.get("rows", [])) if isinstance(content, dict) else 0
        rows += 1 if (isinstance(content, dict) and content.get("headers")) else 0
        return max(0.6, rows * max(0.34, font_pt * 0.7 * 2.6 / 72))
    if kind == "metric":
        return 1.5
    if kind == "phases":
        phases = content if isinstance(content, list) else [content]
        deepest = max((len(p.get("detail") or []) if isinstance(p.get("detail"), list)
                       else 1) for p in phases) if phases else 1
        return 0.75 + deepest * 0.26
    if kind == "members":
        members = content if isinstance(content, list) else [content]
        return math.ceil(len(members) / min(4, max(len(members), 1))) * 1.6
    if kind == "image":
        return 2.5

    paragraphs = [t for t, _, _ in block_paragraphs(fill)]
    per_line = max(1, int(width_in * 72 / (font_pt * 0.5)))
    return text_lines(paragraphs, per_line) * font_pt * 1.35 / 72


def stack(units, box, font_pt):
    """Lay a placeholder's units out top to bottom inside its box.

    A unit is either a run of text blocks (which share one placeholder shape) or a
    single shape block. Everything gets its natural height when there is room, leaving
    slack at the bottom the way the HTML deck does; when there is not, every unit is
    scaled by the same factor — proportional crowding beats one block silently landing
    on top of another.
    """
    x, y, w, h = box
    wants = []
    for kind, payload in units:
        fills = payload if kind == "text" else [payload]
        wants.append(sum(desired_height(f, w, font_pt) for f in fills))

    slack = STACK_GAP * (len(units) - 1)
    if sum(wants) + slack > h:
        scale = (h - slack) / max(sum(wants), 0.01)
        wants = [max(0.3, want * scale) for want in wants]

    boxes, cursor = [], y
    for want in wants:
        boxes.append((x, cursor, w, want))
        cursor += want + STACK_GAP
    return boxes


def slide_footer_text(step, plan, mode, position, total):
    if mode == "hidden":
        return None
    sources = sorted({s for fill in step["fills"] for s in fill.get("sources", [])})
    gaps = sum(1 for fill in step["fills"] if fill.get("gap"))

    left = "Sources: " + ", ".join(sources) if sources else ""
    if gaps:
        marker = f"{gaps} open gap{'s' if gaps > 1 else ''}"
        left = f"{left} · {marker}" if left else marker
    right = f"{plan.get('client', '')} · {position} / {total}".strip(" ·")
    return f"{left or 'No sources recorded'}    |    {right}"


def build_slide(step, plan, options, media, position, total):
    """One manifest step -> (slide xml, extra relationships, warnings)."""
    shapes, warnings, rels = [], [], []
    shape_id = 2
    fallback_box = (0.62, 1.68, 12.09, 4.98)

    # Group by resolved placeholder so several blocks aimed at one slot merge, the way
    # the HTML renderer concatenates them.
    grouped = {}
    for fill in step["fills"]:
        key = fill["resolved"].get("name") or fill["placeholder"]
        grouped.setdefault(key, {"ph": fill["resolved"], "fills": []})["fills"].append(fill)

    # A plan carries each slide's title once, at slide level; only a cover slide bothers
    # to also target the title placeholder with a block. Back-fill it wherever the layout
    # has a title slot and nothing claimed it, or every content slide lands untitled.
    title_ph = options["titles"].get(step["layout_part"])
    if title_ph is not None and step.get("title"):
        claimed = any(g["ph"] is title_ph or
                      (g["ph"].get("name") or "").lower() == "title" for g in grouped.values())
        if not claimed:
            grouped["title"] = {
                "ph": title_ph,
                "fills": [{"kind": "text", "content": step["title"], "sources": [],
                           "gap": False}],
            }

    for key, group in grouped.items():
        ph = group["ph"]
        geom = geom_of(ph, fallback_box)
        font_pt = ph.get("font_size_pt") or (
            DEFAULT_TITLE_PT if str(ph.get("type", "")).endswith("itle") else DEFAULT_BODY_PT
        )

        # Consecutive text blocks aimed at one slot merge into a single placeholder
        # shape; anything else claims its own band of the box.
        units, run = [], []
        for fill in group["fills"]:
            if not fill.get("gap") and fill["kind"] in TEXT_KINDS:
                run.append(fill)
            else:
                if run:
                    units.append(("text", run))
                    run = []
                units.append(("shape", fill))
        if run:
            units.append(("text", run))

        # One unit keeps the placeholder's whole box — the layout sized that box for it.
        single = len(units) == 1
        boxes = [geom] if single else stack(units, geom, font_pt)

        for (unit_kind, payload), box in zip(units, boxes):
            if unit_kind == "text":
                paragraphs = [p for f in payload for p in block_paragraphs(f)]
                ratio = fit_ratio([t for t, _, _ in paragraphs],
                                  {"w_in": box[2], "h_in": box[3]}, font_pt)
                scale = None
                if ratio and ratio > 1.0:
                    scale = max(MIN_FONT_SCALE, 1 / ratio)
                    warnings.append(
                        f"{step['slide_id']}/{key}: text is ~{ratio:.0%} of the space at "
                        f"{font_pt:.0f}pt — autofit set to {scale:.0%}"
                        + ("; still over, cut content" if 1 / ratio < MIN_FONT_SCALE else "")
                    )
                shapes.append(placeholder_sp(shape_id, ph, paragraphs, font_scale=scale,
                                             geometry_override=None if single else box))
                shape_id += 1
                continue

            fill = payload
            if fill.get("gap"):
                shapes.append(render_gap(shape_id, box, fill.get("gap_note")))
                shape_id += 1
                continue

            kind, content = fill["kind"], fill["content"]
            if kind == "table":
                shapes.append(render_table(shape_id, box, content, font_pt * 0.7))
                shape_id += 1
            elif kind == "metric":
                new = render_metrics(shape_id, box, content, font_pt)
                shapes += new
                shape_id += len(new)
            elif kind == "phases":
                new = render_phases(shape_id, box, content, font_pt)
                shapes += new
                shape_id += len(new)
            elif kind == "members":
                new = render_members(shape_id, box, content, font_pt)
                shapes += new
                shape_id += len(new)
            elif kind == "image":
                src = content.get("src") if isinstance(content, dict) else content
                path = Path(str(src))
                if not path.is_file():
                    warnings.append(f"{step['slide_id']}/{key}: image not found: {src}")
                    shapes.append(render_gap(shape_id, box,
                                             f"Image missing at build time: {src}"))
                    shape_id += 1
                    continue
                data = path.read_bytes()
                rid, target = media.add(data, path.suffix.lower())
                rels.append((rid, f"{REL}/image", target))
                shapes.append(render_image(shape_id, box, rid, data))
                shape_id += 1

    footer_ph = options["footers"].get(step["layout_part"])
    footer = slide_footer_text(step, plan, options["sources"], position, total)
    if footer_ph is not None and footer:
        shapes.append(placeholder_sp(shape_id, footer_ph, [(footer, 0, False)]))
        shape_id += 1

    xml = (
        XML_DECL +
        f'<p:sld {NS_P}><p:cSld><p:spTree>'
        f'<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        f'<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        f'<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        f'{"".join(shapes)}</p:spTree></p:cSld>'
        f'<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
    )
    return xml, rels, warnings


def notes_slide(text):
    body = "".join(para_xml(line, bullet=False) for line in str(text).split("\n") if line.strip())
    return (
        XML_DECL +
        f'<p:notes {NS_P}><p:cSld><p:spTree>'
        f'<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        f'<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        f'<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        f'<p:sp><p:nvSpPr><p:cNvPr id="2" name="Notes Placeholder 1"/>'
        f'<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
        f'<p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr><p:spPr/>'
        f'<p:txBody><a:bodyPr/><a:lstStyle/>{body}</p:txBody></p:sp>'
        f'</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:notes>'
    )


# --- package ---------------------------------------------------------------


class Media:
    """Collects embedded images, deduplicating identical bytes."""

    def __init__(self):
        self.parts = {}
        self._by_hash = {}
        self._n = 0

    def add(self, data, suffix):
        key = (len(data), hash(data))
        if key in self._by_hash:
            target = self._by_hash[key]
        else:
            self._n += 1
            ext = suffix if suffix in (".png", ".jpg", ".jpeg", ".gif") else ".png"
            target = f"ppt/media/proposal{self._n}{ext}"
            self.parts[target] = data
            self._by_hash[key] = target
        # Relationship IDs are per-slide, so the caller pairs this target with its own.
        return f"rIdImg{abs(hash(target)) % 100000}", "../media/" + Path(target).name


def rels_xml(pairs):
    body = "".join(f'<Relationship Id="{rid}" Type="{typ}" Target="{target}"/>'
                   for rid, typ, target in pairs)
    return (XML_DECL + '<Relationships xmlns="http://schemas.openxmlformats.org/package/'
            f'2006/relationships">{body}</Relationships>')


def next_rel_id(rels_text):
    used = [int(m) for m in re.findall(r'Id="rId(\d+)"', rels_text)]
    return max(used, default=0) + 1


def strip_parts(parts, prefixes):
    for name in list(parts):
        if any(name.startswith(p) for p in prefixes):
            del parts[name]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", type=Path)
    ap.add_argument("template", type=Path, help="the approved .potx/.pptx to build on")
    ap.add_argument("-o", "--out", type=Path, default=Path("proposal.pptx"))
    ap.add_argument("--profile", type=Path,
                    help="template_profile.json (default: alongside the template, "
                         "else profiled on the fly)")
    ap.add_argument("--map", type=Path, dest="template_map",
                    help="template_map.json with layout_aliases / placeholder_aliases")
    ap.add_argument("--sources", choices=["footer", "hidden"], default="footer",
                    help="Show knowledge-bank source IDs per slide (default: footer). "
                         "'hidden' is for a reviewed client-facing copy only.")
    args = ap.parse_args()

    if not args.template.is_file():
        sys.exit(f"template not found: {args.template}")
    if args.template.suffix.lower() not in (".potx", ".pptx"):
        sys.exit(f"expected a .potx or .pptx template; got {args.template.suffix}")

    plan = json.loads(args.plan.read_text(encoding="utf-8"))

    profile_path = args.profile or args.template.with_name("template_profile.json")
    if profile_path.is_file():
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    else:
        print(f"no profile at {profile_path} — profiling {args.template.name} in memory")
        with zipfile.ZipFile(args.template) as zf:
            layouts = [profile_layout(zf.read(n), n)
                       for n in sorted(zf.namelist())
                       if n.startswith("ppt/slideLayouts/slideLayout")]
        profile = {"template": str(args.template), "kind": "pptx", "layouts": layouts}

    if profile.get("kind") == "html":
        sys.exit("that profile describes an HTML template — profile the .potx instead, "
                 "or use render_html.py")

    steps, errors = build(plan, profile, load_map(args.template_map))
    if errors:
        for err in errors:
            print(f"  ERROR {err}", file=sys.stderr)
        sys.exit("plan does not validate against the template — fix the plan, not the renderer")

    with zipfile.ZipFile(args.template) as zf:
        parts = {n: zf.read(n) for n in zf.namelist()}

    has_notes_master = any(n.startswith("ppt/notesMasters/notesMaster") for n in parts)
    # The template's own example slides are scaffolding, not content. Everything else —
    # master, layouts, theme, fonts, table styles — carries across untouched.
    strip_parts(parts, ("ppt/slides/", "ppt/notesSlides/"))

    footers, titles = {}, {}
    for layout in profile.get("layouts", []):
        for ph in layout.get("placeholders", []):
            name = (ph.get("name") or "").lower()
            if name == "footer":
                footers.setdefault(layout["part"], ph)
            if name == "title" or ph.get("type") in ("title", "ctrTitle"):
                titles.setdefault(layout["part"], ph)

    media = Media()
    options = {"sources": args.sources, "footers": footers, "titles": titles}

    pres_rels = parts["ppt/_rels/presentation.xml.rels"].decode("utf-8")
    pres_rels = re.sub(
        r'<Relationship[^>]*Type="[^"]*/slide"[^>]*/>', "", pres_rels)
    rid = next_rel_id(pres_rels)

    slide_entries, all_warnings, notes_count = [], [], 0
    total = len(steps)

    for i, step in enumerate(steps, 1):
        xml, image_rels, warnings = build_slide(step, plan, options, media, i, total)
        all_warnings += warnings

        slide_part = f"ppt/slides/slide{i}.xml"
        slide_rels = [("rId1", f"{REL}/slideLayout",
                       "../slideLayouts/" + Path(step["layout_part"]).name)]
        # Image shapes were built with provisional rIds; bind them to this slide's.
        for n, (provisional, typ, target) in enumerate(image_rels, 2):
            slide_rels.append((f"rId{n}", typ, target))
            xml = xml.replace(f'r:embed="{provisional}"', f'r:embed="rId{n}"')
        parts[slide_part] = xml.encode("utf-8")

        if step.get("speaker_notes") and has_notes_master:
            notes_count += 1
            notes_part = f"ppt/notesSlides/notesSlide{notes_count}.xml"
            parts[notes_part] = notes_slide(step["speaker_notes"]).encode("utf-8")
            parts[f"ppt/notesSlides/_rels/notesSlide{notes_count}.xml.rels"] = rels_xml([
                ("rId1", f"{REL}/notesMaster", "../notesMasters/notesMaster1.xml"),
                ("rId2", f"{REL}/slide", f"../slides/slide{i}.xml"),
            ]).encode("utf-8")
            slide_rels.append((f"rId{len(slide_rels) + 1}", f"{REL}/notesSlide",
                               f"../notesSlides/notesSlide{notes_count}.xml"))

        parts[f"ppt/slides/_rels/slide{i}.xml.rels"] = rels_xml(slide_rels).encode("utf-8")
        slide_entries.append((f"rId{rid}", slide_part))
        rid += 1

    for target, data in media.parts.items():
        parts[target] = data

    # presentation.xml.rels — slide relationships appended after the template's own.
    pres_rels = pres_rels.replace(
        "</Relationships>",
        "".join(f'<Relationship Id="{r}" Type="{REL}/slide" Target="{p[len("ppt/"):]}"/>'
                for r, p in slide_entries) + "</Relationships>")
    parts["ppt/_rels/presentation.xml.rels"] = pres_rels.encode("utf-8")

    # presentation.xml — rebuild the slide list.
    pres = parts["ppt/presentation.xml"].decode("utf-8")
    pres = re.sub(r"<p:sldIdLst>.*?</p:sldIdLst>", "", pres, flags=re.DOTALL)
    sld_id_lst = "<p:sldIdLst>" + "".join(
        f'<p:sldId id="{256 + i}" r:id="{r}"/>' for i, (r, _) in enumerate(slide_entries)
    ) + "</p:sldIdLst>"
    pres = pres.replace("<p:sldSz", sld_id_lst + "<p:sldSz", 1)
    parts["ppt/presentation.xml"] = pres.encode("utf-8")

    # [Content_Types].xml — drop stale slide overrides, declare the new parts, and make
    # the package a presentation even when the template was a .potx.
    ct = parts["[Content_Types].xml"].decode("utf-8")
    ct = re.sub(r'<Override PartName="/ppt/(slides|notesSlides)/[^"]*"[^>]*/>', "", ct)
    ct = ct.replace(
        "application/vnd.openxmlformats-officedocument.presentationml.template.main+xml",
        CT_PRESENTATION)
    for ext in {Path(t).suffix.lstrip(".") for t in media.parts}:
        if f'Extension="{ext}"' not in ct:
            mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
            ct = ct.replace("<Override", f'<Default Extension="{ext}" '
                                         f'ContentType="{mime}"/><Override', 1)
    new_overrides = "".join(
        f'<Override PartName="/{p}" ContentType="{CT_SLIDE}"/>' for _, p in slide_entries
    ) + "".join(
        f'<Override PartName="/ppt/notesSlides/notesSlide{n}.xml" ContentType="{CT_NOTES}"/>'
        for n in range(1, notes_count + 1)
    )
    ct = ct.replace("</Types>", new_overrides + "</Types>")
    parts["[Content_Types].xml"] = ct.encode("utf-8")

    if "docProps/app.xml" in parts:
        app = parts["docProps/app.xml"].decode("utf-8")
        app = re.sub(r"<Slides>\d+</Slides>", f"<Slides>{total}</Slides>", app)
        app = re.sub(r"<Notes>\d+</Notes>", f"<Notes>{notes_count}</Notes>", app)
        parts["docProps/app.xml"] = app.encode("utf-8")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(parts):
            data = parts[name]
            zf.writestr(name, data if isinstance(data, bytes) else data.encode("utf-8"))

    gaps = sum(1 for s in steps for f in s["fills"] if f.get("gap"))
    size_kb = args.out.stat().st_size // 1024
    print(f"Rendered {total} slides -> {args.out} ({size_kb} KB)")
    print(f"  template: {args.template}   sources: {args.sources}")
    if notes_count:
        print(f"  {notes_count} slide(s) carry speaker notes")
    elif any(s.get("speaker_notes") for s in steps) and not has_notes_master:
        print("  speaker notes skipped — the template has no notes master", file=sys.stderr)
    if gaps:
        print(f"  {gaps} [GAP] panel(s) rendered visibly — see qa_report.md for the action list")
    for warning in all_warnings:
        print(f"  OVERFLOW {warning}", file=sys.stderr)
    limit = plan.get("slide_budget", {}).get("limit")
    if limit and total > limit:
        print(f"  WARNING: {total} slides exceeds the RFP limit of {limit}", file=sys.stderr)
    print(f"  Draft for practitioner review — generated {date.today().isoformat()}")
    print("  Next: qa_pptx.py for template fidelity and overflow checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
