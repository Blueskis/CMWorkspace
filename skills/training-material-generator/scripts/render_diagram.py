#!/usr/bin/env python3
"""Render a diagram_spec into a native DrawingML shape group, plus an SVG preview (Stage 3/4).

    python render_diagram.py diagram_spec.json --type process \\
        --bbox 0.5,1.5,9.0,5.0 --id-start 100 \\
        -o diagrams/approval-flow.xml --svg diagrams/approval-flow.svg

Five diagram types, chosen because each maps to a prose shape FSDs actually contain (see
reference/diagram-patterns.md for which):

    process    numbered procedure steps  -> box-and-arrow flow
    swimlane   role-by-step prose/table   -> lane grid
    decision   "if X then Y" rules        -> condition/outcome chain
    hierarchy  escalation / org structure -> tree
    timeline   milestones / cut-over      -> horizontal axis

The output XML fragment is a self-contained, independently-parseable `<p:grpSp>...
</p:grpSp>` (namespaces declared on the root) sized to the bounding box given —
normally a layout's picture or content placeholder geometry from template_profile.json.
inject_slide_xml.py imports it into a real slide's shape tree; this script never touches
a live deck.

Two rules keep a diagram on-template, matching template_map.json's own
`respect_theme_fonts` discipline:

  * **Colours are always `<a:schemeClr val="accent1"/>` references, never hex.** The
    diagram then re-colours correctly if the client's theme changes.
  * **Fonts are left to inherit** — no `<a:latin typeface="...">` is ever written.

Labels auto-fit by stepping the font size down (14pt -> 8pt) against an estimated text
width. If a label still will not fit its box at the floor size, this script **exits
non-zero naming the label and by how much** rather than emitting text that will clip —
per the pptx skill's own "never ship text that overflows its shape" rule, which a
generated diagram is not exempt from. Split the diagram or shorten the label and re-run.

Stdlib only.
"""

import argparse
import json
import math
import sys
from pathlib import Path

EMU_PER_INCH = 914400
PT_PER_INCH = 72
FONT_SIZES = (14, 12, 11, 10, 9, 8)
CHAR_WIDTH_FACTOR = 0.52   # average glyph width as a fraction of font size, for a sans body font
LINE_HEIGHT_FACTOR = 1.25
PALETTE_CYCLE = ["accent1", "accent2", "accent3", "accent4", "accent5", "accent6"]


class DiagramSpecError(Exception):
    """The diagram_spec is malformed or references something that doesn't exist
    (an unknown role, an empty required list, ...). Caught by build_training_deck.py
    and reported per-block rather than crashing the whole build."""


class DiagramOverflowError(Exception):
    """A label will not fit its box even at the smallest allowed font. Caught the same
    way as DiagramSpecError; main() below turns either into a CLI exit."""


# ---------------------------------------------------------------------------
# Text fit
# ---------------------------------------------------------------------------

def _lines_needed(text, box_w_in, font_pt):
    chars_per_line = max(1, int((box_w_in * PT_PER_INCH) / (font_pt * CHAR_WIDTH_FACTOR)))
    return max(1, math.ceil(len(text) / chars_per_line))


def fit_font(text, box_w_in, box_h_in, label_for_error):
    for size in FONT_SIZES:
        lines = _lines_needed(text, box_w_in, size)
        needed_h_in = (lines * size * LINE_HEIGHT_FACTOR) / PT_PER_INCH
        if needed_h_in <= box_h_in:
            return size, lines
    smallest = FONT_SIZES[-1]
    lines = _lines_needed(text, box_w_in, smallest)
    needed_h_in = (lines * smallest * LINE_HEIGHT_FACTOR) / PT_PER_INCH
    raise DiagramOverflowError(
        f"diagram label will not fit: '{label_for_error}' needs {needed_h_in:.2f}in "
        f"tall at {smallest}pt (box is {box_w_in:.2f}x{box_h_in:.2f}in). "
        f"Shorten the label or split the diagram across more boxes/slides."
    )


# ---------------------------------------------------------------------------
# Scene model — shared by the OOXML and SVG renderers
# ---------------------------------------------------------------------------

def make_box(x, y, w, h, text, fill, shape="rect"):
    font_pt, _ = fit_font(text, w - 0.15, h - 0.15, text)
    return {"type": "box", "shape": shape, "x": x, "y": y, "w": w, "h": h, "text": text,
            "fill": fill, "font_pt": font_pt}


def make_arrow(x1, y1, x2, y2):
    return {"type": "arrow", "x1": x1, "y1": y1, "x2": x2, "y2": y2}


def make_line(x1, y1, x2, y2):
    """A structural line (lane divider/border) — no arrowhead, unlike make_arrow."""
    return {"type": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2}


def make_label(x, y, w, h, text, align="ctr", font_pt=10):
    return {"type": "label", "x": x, "y": y, "w": w, "h": h, "text": text, "align": align, "font_pt": font_pt}


# ---------------------------------------------------------------------------
# Layouts
# ---------------------------------------------------------------------------

def layout_process(spec, bx, by, bw, bh):
    steps = spec["steps"]
    if not steps:
        raise DiagramSpecError("process diagram_spec needs a non-empty 'steps' list")
    n = len(steps)
    gap = 0.3
    box_w = (bw - gap * (n - 1)) / n
    box_h = min(1.4, bh)
    y = by + (bh - box_h) / 2
    scene = []
    for i, step in enumerate(steps):
        x = bx + i * (box_w + gap)
        scene.append(make_box(x, y, box_w, box_h, step, PALETTE_CYCLE[i % len(PALETTE_CYCLE)]))
        if i < n - 1:
            scene.append(make_arrow(x + box_w, y + box_h / 2, x + box_w + gap, y + box_h / 2))
    return scene


def layout_swimlane(spec, bx, by, bw, bh):
    roles = spec["roles"]
    steps = spec["steps"]  # [{"step": "...", "role": "..."}]
    if not roles or not steps:
        raise DiagramSpecError("swimlane diagram_spec needs non-empty 'roles' and 'steps'")
    lane_h = bh / len(roles)
    label_w = min(1.6, bw * 0.2)
    col_area_w = bw - label_w
    col_w = col_area_w / len(steps)
    scene = []
    for r, role in enumerate(roles):
        ly = by + r * lane_h
        scene.append(make_label(bx, ly, label_w, lane_h, role, align="l", font_pt=11))
        scene.append(make_line(bx, ly, bx + bw, ly))  # lane divider
    scene.append(make_line(bx, by + bh, bx + bw, by + bh))
    scene.append(make_line(bx + label_w, by, bx + label_w, by + bh))

    role_index = {r: i for i, r in enumerate(roles)}
    box_h = min(1.0, lane_h * 0.7)
    prev_exit = None
    for c, item in enumerate(steps):
        role = item["role"]
        if role not in role_index:
            raise DiagramSpecError(f"swimlane step references unknown role '{role}' — not in {roles}")
        r = role_index[role]
        cx = bx + label_w + c * col_w
        cy = by + r * lane_h + (lane_h - box_h) / 2
        box_x, box_w = cx + 0.1, col_w - 0.2
        scene.append(make_box(box_x, cy, box_w, box_h, item["step"], PALETTE_CYCLE[r % len(PALETTE_CYCLE)]))
        # Connect box EDGES, not centers — a center-to-center line on a cross-lane step
        # cuts straight through the intervening box text. Edge-to-edge confines the
        # connector to the (empty) gap between columns instead.
        entry = (box_x, cy + box_h / 2)
        exit_ = (box_x + box_w, cy + box_h / 2)
        if prev_exit:
            scene.append(make_arrow(prev_exit[0], prev_exit[1], entry[0], entry[1]))
        prev_exit = exit_
    return scene


def layout_decision(spec, bx, by, bw, bh):
    rules = spec["rules"]  # [{"condition": "...", "outcome": "..."}]
    if not rules:
        raise DiagramSpecError("decision diagram_spec needs a non-empty 'rules' list")
    n = len(rules)
    row_h = bh / n
    box_h = min(0.9, row_h * 0.7)
    cond_w = bw * 0.55
    out_w = bw * 0.35
    gap = bw * 0.1
    scene = []
    for i, rule in enumerate(rules):
        y = by + i * row_h + (row_h - box_h) / 2
        scene.append(make_box(bx, y, cond_w, box_h, rule["condition"], "lt2", shape="diamond"))
        scene.append(make_arrow(bx + cond_w, y + box_h / 2, bx + cond_w + gap, y + box_h / 2))
        scene.append(make_box(bx + cond_w + gap, y, out_w, box_h, rule["outcome"], PALETTE_CYCLE[i % len(PALETTE_CYCLE)]))
    return scene


def layout_hierarchy(spec, bx, by, bw, bh):
    root = spec["root"]
    if not root:
        raise DiagramSpecError("hierarchy diagram_spec needs a 'root' node")

    levels = []

    def walk(node, depth):
        while len(levels) <= depth:
            levels.append([])
        levels[depth].append(node)
        for child in node.get("children", []):
            walk(child, depth + 1)

    walk(root, 0)
    depth_count = len(levels)
    row_h = bh / depth_count
    box_h = min(0.8, row_h * 0.6)

    positions = {}

    def assign_x(node, depth, x_lo, x_hi):
        children = node.get("children", [])
        cx = (x_lo + x_hi) / 2
        positions[id(node)] = (cx, depth)
        if children:
            step = (x_hi - x_lo) / len(children)
            for i, child in enumerate(children):
                assign_x(child, depth + 1, x_lo + i * step, x_lo + (i + 1) * step)

    assign_x(root, 0, bx, bx + bw)

    scene = []
    box_w = min(2.2, bw / max(len(lvl) for lvl in levels))

    def place(node, depth):
        cx, _ = positions[id(node)]
        y = by + depth * row_h + (row_h - box_h) / 2
        x = cx - box_w / 2
        scene.append(make_box(x, y, box_w, box_h, node["name"], PALETTE_CYCLE[depth % len(PALETTE_CYCLE)]))
        for child in node.get("children", []):
            ccx, _ = positions[id(child)]
            cy = by + (depth + 1) * row_h + (row_h - box_h) / 2
            scene.append(make_arrow(cx, y + box_h, ccx, cy))
            place(child, depth + 1)

    place(root, 0)
    return scene


def layout_timeline(spec, bx, by, bw, bh):
    milestones = spec["milestones"]  # [{"label": "...", "date": "..."}]
    if not milestones:
        raise DiagramSpecError("timeline diagram_spec needs a non-empty 'milestones' list")
    n = len(milestones)
    axis_y = by + bh * 0.5
    scene = [make_arrow(bx, axis_y, bx + bw, axis_y)]
    box_w = min(1.8, bw / n * 0.9)
    box_h = min(0.7, bh * 0.3)
    for i, m in enumerate(milestones):
        cx = bx + (bw / n) * (i + 0.5)
        above = (i % 2 == 0)
        y = (axis_y - box_h - 0.15) if above else (axis_y + 0.15)
        scene.append(make_arrow(cx, axis_y, cx, y + (box_h if above else 0)))
        scene.append(make_box(cx - box_w / 2, y, box_w, box_h, m["label"], PALETTE_CYCLE[i % len(PALETTE_CYCLE)]))
        date_y = (y - 0.3) if above else (y + box_h + 0.05)
        if m.get("date"):
            scene.append(make_label(cx - box_w / 2, date_y, box_w, 0.25, m["date"], font_pt=9))
    return scene


LAYOUTS = {
    "process": layout_process,
    "swimlane": layout_swimlane,
    "decision": layout_decision,
    "hierarchy": layout_hierarchy,
    "timeline": layout_timeline,
}


# ---------------------------------------------------------------------------
# OOXML renderer
# ---------------------------------------------------------------------------

def _emu(inches):
    return int(round(inches * EMU_PER_INCH))


def render_ooxml(scene, bx, by, bw, bh, id_start=100, group_name="Diagram"):
    ids = iter(range(id_start, id_start + len(scene) + 1))
    group_id = next(ids)
    shapes_xml = []

    for node in scene:
        sid = next(ids)
        if node["type"] == "box":
            preset = "ellipse" if node["shape"] == "diamond" else "roundRect"
            shapes_xml.append(f'''
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="{sid}" name="{group_name} Box {sid}"/>
          <p:cNvSpPr/>
          <p:nvPr/>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="{_emu(node['x'])}" y="{_emu(node['y'])}"/><a:ext cx="{_emu(node['w'])}" cy="{_emu(node['h'])}"/></a:xfrm>
          <a:prstGeom prst="{preset}"><a:avLst/></a:prstGeom>
          <a:solidFill><a:schemeClr val="{node['fill']}"/></a:solidFill>
        </p:spPr>
        <p:txBody>
          <a:bodyPr wrap="square" anchor="ctr"><a:normAutofit/></a:bodyPr>
          <a:p><a:pPr algn="ctr"/><a:r><a:rPr lang="en-US" sz="{node['font_pt'] * 100}"/><a:t>{_xml_escape(node['text'])}</a:t></a:r></a:p>
        </p:txBody>
      </p:sp>''')
        elif node["type"] == "label":
            align = {"l": "l", "ctr": "ctr", "r": "r"}.get(node["align"], "l")
            shapes_xml.append(f'''
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="{sid}" name="{group_name} Label {sid}"/>
          <p:cNvSpPr txBox="1"/>
          <p:nvPr/>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="{_emu(node['x'])}" y="{_emu(node['y'])}"/><a:ext cx="{_emu(node['w'])}" cy="{_emu(node['h'])}"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
          <a:noFill/>
        </p:spPr>
        <p:txBody>
          <a:bodyPr wrap="square" anchor="ctr"/>
          <a:p><a:pPr algn="{align}"/><a:r><a:rPr lang="en-US" sz="{node['font_pt'] * 100}"/><a:t>{_xml_escape(node['text'])}</a:t></a:r></a:p>
        </p:txBody>
      </p:sp>''')
        elif node["type"] in ("arrow", "line"):
            x1, y1, x2, y2 = node["x1"], node["y1"], node["x2"], node["y2"]
            off_x, off_y = min(x1, x2), min(y1, y2)
            ext_cx, ext_cy = max(abs(x2 - x1), 0.01), max(abs(y2 - y1), 0.01)
            flip_h = ' flipH="1"' if x2 < x1 else ""
            flip_v = ' flipV="1"' if y2 < y1 else ""
            tail_end = '<a:tailEnd type="arrow"/>' if node["type"] == "arrow" else ""
            shapes_xml.append(f'''
      <p:cxnSp>
        <p:nvCxnSpPr>
          <p:cNvPr id="{sid}" name="{group_name} Connector {sid}"/>
          <p:cNvCxnSpPr/>
          <p:nvPr/>
        </p:nvCxnSpPr>
        <p:spPr>
          <a:xfrm{flip_h}{flip_v}><a:off x="{_emu(off_x)}" y="{_emu(off_y)}"/><a:ext cx="{_emu(ext_cx)}" cy="{_emu(ext_cy)}"/></a:xfrm>
          <a:prstGeom prst="straightConnector1"><a:avLst/></a:prstGeom>
          <a:ln w="19050"><a:solidFill><a:schemeClr val="tx1"/></a:solidFill>
            {tail_end}
          </a:ln>
        </p:spPr>
      </p:cxnSp>''')

    fragment = f'''<p:grpSp xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:nvGrpSpPr>
    <p:cNvPr id="{group_id}" name="{group_name}"/>
    <p:cNvGrpSpPr/>
    <p:nvPr/>
  </p:nvGrpSpPr>
  <p:grpSpPr>
    <a:xfrm>
      <a:off x="{_emu(bx)}" y="{_emu(by)}"/>
      <a:ext cx="{_emu(bw)}" cy="{_emu(bh)}"/>
      <a:chOff x="{_emu(bx)}" y="{_emu(by)}"/>
      <a:chExt cx="{_emu(bw)}" cy="{_emu(bh)}"/>
    </a:xfrm>
  </p:grpSpPr>
  {''.join(shapes_xml)}
</p:grpSp>
'''
    return fragment


def _xml_escape(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&apos;"))


# ---------------------------------------------------------------------------
# SVG preview renderer
# ---------------------------------------------------------------------------

DEFAULT_PREVIEW_COLORS = {
    "accent1": "#4472C4", "accent2": "#ED7D31", "accent3": "#A5A5A5",
    "accent4": "#FFC000", "accent5": "#5B9BD5", "accent6": "#70AD47",
    "lt1": "#FFFFFF", "lt2": "#E7E6E6", "tx1": "#000000",
}


def render_svg(scene, bx, by, bw, bh, theme_colors=None):
    colors = dict(DEFAULT_PREVIEW_COLORS)
    if theme_colors:
        colors.update(theme_colors)
    dpi = 96
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{bw*dpi:.0f}" height="{bh*dpi:.0f}" '
              f'viewBox="{bx*dpi:.0f} {by*dpi:.0f} {bw*dpi:.0f} {bh*dpi:.0f}" font-family="sans-serif">']
    parts.append(f'<rect x="{bx*dpi:.0f}" y="{by*dpi:.0f}" width="{bw*dpi:.0f}" height="{bh*dpi:.0f}" fill="#FAFAFA" stroke="#DDDDDD"/>')
    for node in scene:
        if node["type"] == "box":
            x, y, w, h = node["x"] * dpi, node["y"] * dpi, node["w"] * dpi, node["h"] * dpi
            fill = colors.get(node["fill"], "#999999")
            if node["shape"] == "diamond":
                cx, cy = x + w / 2, y + h / 2
                parts.append(f'<ellipse cx="{cx:.0f}" cy="{cy:.0f}" rx="{w/2:.0f}" ry="{h/2:.0f}" fill="{fill}" stroke="#333"/>')
            else:
                parts.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="6" fill="{fill}" stroke="#333"/>')
            parts.append(_svg_text(node["text"], x + w / 2, y + h / 2, node["font_pt"], "middle", "#111"))
        elif node["type"] == "label":
            x, y, w, h = node["x"] * dpi, node["y"] * dpi, node["w"] * dpi, node["h"] * dpi
            anchor = {"l": "start", "ctr": "middle", "r": "end"}.get(node["align"], "start")
            tx = x if anchor == "start" else (x + w if anchor == "end" else x + w / 2)
            parts.append(_svg_text(node["text"], tx, y + h / 2, node["font_pt"], anchor, "#333"))
        elif node["type"] in ("arrow", "line"):
            x1, y1, x2, y2 = node["x1"] * dpi, node["y1"] * dpi, node["x2"] * dpi, node["y2"] * dpi
            marker = ' marker-end="url(#arrow)"' if node["type"] == "arrow" else ""
            parts.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="#333" stroke-width="2"{marker}/>')
    parts.insert(1, '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#333"/></marker></defs>')
    parts.append("</svg>")
    return "\n".join(parts)


def _svg_text(text, x, y, font_pt, anchor, color):
    return (f'<text x="{x:.0f}" y="{y:.0f}" font-size="{font_pt}" text-anchor="{anchor}" '
            f'dominant-baseline="middle" fill="{color}">{_xml_escape(text)}</text>')


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

def render(diagram_type, spec, bbox, id_start=100, theme_colors=None):
    """bbox: (x_in, y_in, w_in, h_in). Returns (ooxml_str, svg_str)."""
    if diagram_type not in LAYOUTS:
        raise DiagramSpecError(f"unknown diagram_type '{diagram_type}' — must be one of {sorted(LAYOUTS)}")
    bx, by, bw, bh = bbox
    scene = LAYOUTS[diagram_type](spec, bx, by, bw, bh)
    ooxml = render_ooxml(scene, bx, by, bw, bh, id_start=id_start, group_name=diagram_type.title())
    svg = render_svg(scene, bx, by, bw, bh, theme_colors=theme_colors)
    return ooxml, svg


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path, help="JSON file: {\"diagram_type\": ..., \"spec\": {...}} or bare spec with --type")
    ap.add_argument("--type", choices=sorted(LAYOUTS), help="Overrides diagram_type in the spec file")
    ap.add_argument("--bbox", required=True, help="x_in,y_in,w_in,h_in — the target placeholder's geometry")
    ap.add_argument("--id-start", type=int, default=100, help="First shape id to use, above the target slide's existing max id")
    ap.add_argument("--theme-colors", type=Path, default=None, help="theme_colors JSON from template_profile.json, for a faithful SVG preview")
    ap.add_argument("-o", "--out", type=Path, required=True, help="Output OOXML fragment path")
    ap.add_argument("--svg", type=Path, default=None, help="Output SVG preview path (defaults next to -o with .svg)")
    args = ap.parse_args()

    payload = json.loads(args.spec.read_text(encoding="utf-8"))
    diagram_type = args.type or payload.get("diagram_type")
    spec = payload.get("spec", payload)
    if not diagram_type:
        sys.exit("diagram_type not given: pass --type or include \"diagram_type\" in the spec file")

    bbox = tuple(float(v) for v in args.bbox.split(","))
    if len(bbox) != 4:
        sys.exit("--bbox must be x_in,y_in,w_in,h_in")

    theme_colors = None
    if args.theme_colors:
        theme_colors = json.loads(args.theme_colors.read_text(encoding="utf-8"))

    try:
        ooxml, svg = render(diagram_type, spec, bbox, id_start=args.id_start, theme_colors=theme_colors)
    except (DiagramSpecError, DiagramOverflowError) as exc:
        sys.exit(str(exc))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(ooxml, encoding="utf-8")
    svg_path = args.svg or args.out.with_suffix(".svg")
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_text(svg, encoding="utf-8")

    print(f"rendered {diagram_type} diagram -> {args.out}")
    print(f"preview -> {svg_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
