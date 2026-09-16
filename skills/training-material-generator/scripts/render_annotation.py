#!/usr/bin/env python3
"""Render a screenshot's annotations[] into a native DrawingML shape group (Stage 3/4).

    python render_annotation.py annotations.json \\
        --image training/<run>/assets/fsd-img-014.png \\
        --bbox 0.6,1.8,8.5,4.5 --id-start 200 \\
        -o training/<run>/annotations/task-walkthrough-approve-po-2.xml \\
        [--svg .../task-walkthrough-approve-po-2.svg]

Reverses `reference/screenshot-placement.md`'s old rule 4 by giving it the thing it was
missing rather than contradicting it: this never burns anything into the screenshot's
pixels. Every callout is a real DrawingML shape layered over an untouched picture, exactly
as `render_diagram.py` layers a diagram over nothing — same contract: a self-contained,
independently-parseable `<p:grpSp>...</p:grpSp>` with namespaces on the root, imported by
`inject_slide_xml.py`'s existing `diagram` subcommand (an annotation overlay *is* a diagram
fragment as far as that script is concerned — no change needed there). Colours are always
`<a:schemeClr>` references, never hex; fonts are always left to inherit; a step number is a
real `<a:t>` text run, never a rasterized digit, so it stays exactly as editable and
re-themeable in PowerPoint as everything else this script's sibling already draws.

Five annotation types, matching `deck_plan.json`'s `annotations[]` (see
`reference/annotation-patterns.md` for when to use which):

    highlight   outline a region              -> no-fill rounded rect, accent1 line
    callout     number a point                -> filled circle + editable digit
    arrow       point at something crowded     -> straight connector, arrowhead
    redact      cosmetic mask over a rect       -> opaque rect (see below)
    zoom        frame the region a zoom crops   -> outlined rect + leader line

**Coordinates are 0-1 fractions of the screenshot image, not of the slide.** But
`inject_slide_xml.py`'s `insert_picture` aspect-fits the image inside its placeholder bbox
and centres it — the image essentially never fills the bbox exactly. This script reuses
`inject_slide_xml.py`'s own `fit_extent()` and `image_pixel_size()` to recompute the
identical fitted rect from the same `--image` and `--bbox`, so an overlay coordinate always
lands on the same point of the picture the two scripts agree on. Never hand-derive this
rect a second way.

**`redact` here is cosmetic only — a visible mask, not a guarantee.** A shape drawn on top
of a screenshot covers the field on screen but leaves the original pixels in the .pptx zip
underneath it, recoverable by anyone who unzips the file. `png_ops.py redact` is what
actually destroys the pixels, into a *new* asset; `build_training_deck.py` hard-fails a
`redact` annotation whose block still points at the un-flattened original, so this script's
own redact shape can never become the only thing standing between a client's data and the
deck.

A `zoom` annotation draws the frame and leader line only — the magnified inset itself is a
separate cropped/upscaled asset from `png_ops.py crop`, placed as its own picture via
`inject_slide_xml.py insert picture` at a bbox beside the fitted rect (`build_training_deck.py`
computes that placement bbox from `--place`: left/right/below).

A step number too wide for its circle raises `render_diagram.DiagramOverflowError` — same
class, same handling — rather than emitting clipped text.

Stdlib only.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_diagram import DiagramOverflowError, fit_font, _xml_escape  # noqa: E402
from inject_slide_xml import fit_extent, image_pixel_size  # noqa: E402

EMU_PER_INCH = 914400
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

CIRCLE_FRACTION_OF_HEIGHT = 0.05   # callout circle diameter, as a fraction of the fitted image height
CIRCLE_MIN_IN = 0.22               # floor, so a heavily letterboxed image still gets a readable circle
HIGHLIGHT_LINE_BASE_W = 28575      # EMU (~2.25pt), at a 4in-tall reference image
ARROW_LINE_W = 19050               # EMU (~1.5pt) — matches render_diagram.py's connector weight
REDACT_FILL_SCHEME = "tx1"
ZOOM_FRAME_SCHEME = "accent2"


class AnnotationSpecError(Exception):
    """The annotations list is malformed or references something out of bounds. Caught by
    build_training_deck.py and reported per-block, same convention as
    render_diagram.DiagramSpecError."""


def _emu(inches):
    return int(round(inches * EMU_PER_INCH))


def _scaled_line_weight(base_w, fitted_h_in, reference_h_in=4.0):
    """Line weight scales with the fitted image's height so a callout on a half-width
    letterboxed screenshot doesn't read as disproportionately thick or thin."""
    return max(9525, min(base_w * 2, int(round(base_w * (fitted_h_in / reference_h_in)))))


def _point_to_in(point, fx, fy, fw, fh, label):
    if not (isinstance(point, (list, tuple)) and len(point) == 2):
        raise AnnotationSpecError(f"{label}: point must be [u, v]")
    u, v = point
    if not (0 <= u <= 1 and 0 <= v <= 1):
        raise AnnotationSpecError(f"{label}: point {point} is outside 0-1 bounds")
    return fx + u * fw, fy + v * fh


def _rect_to_in(rect, fx, fy, fw, fh, label):
    if not (isinstance(rect, (list, tuple)) and len(rect) == 4):
        raise AnnotationSpecError(f"{label}: rect must be [u, v, du, dv]")
    u, v, du, dv = rect
    if not (0 <= u <= 1 and 0 <= v <= 1 and du > 0 and dv > 0 and u + du <= 1.0001 and v + dv <= 1.0001):
        raise AnnotationSpecError(f"{label}: rect {rect} is out of 0-1 bounds or extends past the image edge")
    return fx + u * fw, fy + v * fh, du * fw, dv * fh


# ---------------------------------------------------------------------------
# Per-type shape emitters — each returns one XML fragment string
# ---------------------------------------------------------------------------

def _highlight_shape(sid, ann, fx, fy, fw, fh, group_name):
    x, y, w, h = _rect_to_in(ann["rect"], fx, fy, fw, fh, f"highlight (step {ann.get('step')})")
    line_w = _scaled_line_weight(HIGHLIGHT_LINE_BASE_W, fh)
    return f'''
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="{sid}" name="{group_name} Highlight {sid}"/>
          <p:cNvSpPr/>
          <p:nvPr/>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="{_emu(x)}" y="{_emu(y)}"/><a:ext cx="{_emu(w)}" cy="{_emu(h)}"/></a:xfrm>
          <a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom>
          <a:noFill/>
          <a:ln w="{line_w}"><a:solidFill><a:schemeClr val="accent1"/></a:solidFill></a:ln>
        </p:spPr>
      </p:sp>'''


def _callout_shape(sid, ann, fx, fy, fw, fh, group_name):
    step = ann.get("step")
    if not isinstance(step, int) or step < 1:
        raise AnnotationSpecError(f"callout at {ann.get('point')}: 'step' must be a positive integer")
    cx, cy = _point_to_in(ann["point"], fx, fy, fw, fh, f"callout (step {step})")
    diameter = max(CIRCLE_MIN_IN, CIRCLE_FRACTION_OF_HEIGHT * fh)
    text = str(step)
    font_pt, _lines = fit_font(text, diameter * 0.7, diameter * 0.7, f"step {step} callout number")
    x, y = cx - diameter / 2, cy - diameter / 2
    return f'''
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="{sid}" name="{group_name} Callout {sid}"/>
          <p:cNvSpPr/>
          <p:nvPr/>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="{_emu(x)}" y="{_emu(y)}"/><a:ext cx="{_emu(diameter)}" cy="{_emu(diameter)}"/></a:xfrm>
          <a:prstGeom prst="ellipse"><a:avLst/></a:prstGeom>
          <a:solidFill><a:schemeClr val="accent1"/></a:solidFill>
        </p:spPr>
        <p:txBody>
          <a:bodyPr wrap="none" anchor="ctr" lIns="0" tIns="0" rIns="0" bIns="0"/>
          <a:p><a:pPr algn="ctr"/><a:r><a:rPr lang="en-US" sz="{font_pt * 100}" b="1"><a:solidFill><a:schemeClr val="bg1"/></a:solidFill></a:rPr><a:t>{_xml_escape(text)}</a:t></a:r></a:p>
        </p:txBody>
      </p:sp>'''


def _arrow_shape(sid, ann, fx, fy, fw, fh, group_name):
    x1, y1 = _point_to_in(ann["from"], fx, fy, fw, fh, f"arrow from (step {ann.get('step')})")
    x2, y2 = _point_to_in(ann["to"], fx, fy, fw, fh, f"arrow to (step {ann.get('step')})")
    off_x, off_y = min(x1, x2), min(y1, y2)
    ext_cx, ext_cy = max(abs(x2 - x1), 0.01), max(abs(y2 - y1), 0.01)
    flip_h = ' flipH="1"' if x2 < x1 else ""
    flip_v = ' flipV="1"' if y2 < y1 else ""
    line_w = _scaled_line_weight(ARROW_LINE_W, fh)
    return f'''
      <p:cxnSp>
        <p:nvCxnSpPr>
          <p:cNvPr id="{sid}" name="{group_name} Arrow {sid}"/>
          <p:cNvCxnSpPr/>
          <p:nvPr/>
        </p:nvCxnSpPr>
        <p:spPr>
          <a:xfrm{flip_h}{flip_v}><a:off x="{_emu(off_x)}" y="{_emu(off_y)}"/><a:ext cx="{_emu(ext_cx)}" cy="{_emu(ext_cy)}"/></a:xfrm>
          <a:prstGeom prst="straightConnector1"><a:avLst/></a:prstGeom>
          <a:ln w="{line_w}"><a:solidFill><a:schemeClr val="accent1"/></a:solidFill>
            <a:tailEnd type="triangle"/>
          </a:ln>
        </p:spPr>
      </p:cxnSp>'''


def _redact_shape(sid, ann, fx, fy, fw, fh, group_name):
    x, y, w, h = _rect_to_in(ann["rect"], fx, fy, fw, fh, f"redact ({ann.get('reason', 'no reason given')})")
    return f'''
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="{sid}" name="{group_name} Redact {sid}"/>
          <p:cNvSpPr/>
          <p:nvPr/>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="{_emu(x)}" y="{_emu(y)}"/><a:ext cx="{_emu(w)}" cy="{_emu(h)}"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
          <a:solidFill><a:schemeClr val="{REDACT_FILL_SCHEME}"/></a:solidFill>
          <a:ln><a:noFill/></a:ln>
        </p:spPr>
      </p:sp>'''


def _zoom_shapes(sid_iter, ann, fx, fy, fw, fh, group_name):
    """Returns (frame_shape_xml, leader_shape_xml_or_None) — two shapes, so callers must
    pull two ids from the iterator."""
    x, y, w, h = _rect_to_in(ann["rect"], fx, fy, fw, fh, f"zoom (step {ann.get('step')})")
    sid = next(sid_iter)
    line_w = _scaled_line_weight(HIGHLIGHT_LINE_BASE_W, fh)
    frame = f'''
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="{sid}" name="{group_name} ZoomFrame {sid}"/>
          <p:cNvSpPr/>
          <p:nvPr/>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="{_emu(x)}" y="{_emu(y)}"/><a:ext cx="{_emu(w)}" cy="{_emu(h)}"/></a:xfrm>
          <a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom>
          <a:noFill/>
          <a:ln w="{line_w}"><a:solidFill><a:schemeClr val="{ZOOM_FRAME_SCHEME}"/></a:solidFill></a:ln>
        </p:spPr>
      </p:sp>'''

    place = ann.get("place", "right")
    edge_x = {"left": x, "right": x + w, "below": x + w / 2}[place]
    edge_y = {"left": y + h / 2, "right": y + h / 2, "below": y + h}[place]
    lead_x = {"left": fx, "right": fx + fw, "below": edge_x}[place]
    lead_y = {"left": edge_y, "right": edge_y, "below": fy + fh}[place]
    lid = next(sid_iter)
    off_x, off_y = min(edge_x, lead_x), min(edge_y, lead_y)
    ext_cx, ext_cy = max(abs(lead_x - edge_x), 0.01), max(abs(lead_y - edge_y), 0.01)
    flip_h = ' flipH="1"' if lead_x < edge_x else ""
    flip_v = ' flipV="1"' if lead_y < edge_y else ""
    leader = f'''
      <p:cxnSp>
        <p:nvCxnSpPr>
          <p:cNvPr id="{lid}" name="{group_name} ZoomLeader {lid}"/>
          <p:cNvCxnSpPr/>
          <p:nvPr/>
        </p:nvCxnSpPr>
        <p:spPr>
          <a:xfrm{flip_h}{flip_v}><a:off x="{_emu(off_x)}" y="{_emu(off_y)}"/><a:ext cx="{_emu(ext_cx)}" cy="{_emu(ext_cy)}"/></a:xfrm>
          <a:prstGeom prst="straightConnector1"><a:avLst/></a:prstGeom>
          <a:ln w="{ARROW_LINE_W}"><a:solidFill><a:schemeClr val="{ZOOM_FRAME_SCHEME}"/></a:solidFill>
            <a:prstDash val="dash"/>
          </a:ln>
        </p:spPr>
      </p:cxnSp>'''
    return frame, leader


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

VALID_TYPES = {"highlight", "callout", "arrow", "redact", "zoom"}


def render_ooxml(annotations, image_bbox, id_start=200, group_name="Annotations"):
    """image_bbox: (fx, fy, fw, fh) in inches — the *fitted* image rect (already aspect-fit
    and centred within the placeholder bbox, from inject_slide_xml.fit_extent). Returns the
    OOXML fragment string."""
    fx, fy, fw, fh = image_bbox
    sid_counter = [id_start + 1]  # id_start itself is reserved for the group shape

    def next_id():
        v = sid_counter[0]
        sid_counter[0] += 1
        return v

    shapes = []
    for i, ann in enumerate(annotations):
        atype = ann.get("type")
        if atype not in VALID_TYPES:
            raise AnnotationSpecError(f"annotation {i}: unknown type '{atype}' — must be one of {sorted(VALID_TYPES)}")
        if atype == "highlight":
            shapes.append(_highlight_shape(next_id(), ann, fx, fy, fw, fh, group_name))
        elif atype == "callout":
            shapes.append(_callout_shape(next_id(), ann, fx, fy, fw, fh, group_name))
        elif atype == "arrow":
            shapes.append(_arrow_shape(next_id(), ann, fx, fy, fw, fh, group_name))
        elif atype == "redact":
            shapes.append(_redact_shape(next_id(), ann, fx, fy, fw, fh, group_name))
        elif atype == "zoom":
            frame, leader = _zoom_shapes(iter([next_id(), next_id()]), ann, fx, fy, fw, fh, group_name)
            shapes.append(frame)
            shapes.append(leader)

    fragment = f'''<p:grpSp xmlns:p="{P_NS}" xmlns:a="{A_NS}">
  <p:nvGrpSpPr>
    <p:cNvPr id="{id_start}" name="{group_name}"/>
    <p:cNvGrpSpPr/>
    <p:nvPr/>
  </p:nvGrpSpPr>
  <p:grpSpPr>
    <a:xfrm>
      <a:off x="{_emu(fx)}" y="{_emu(fy)}"/>
      <a:ext cx="{_emu(fw)}" cy="{_emu(fh)}"/>
      <a:chOff x="{_emu(fx)}" y="{_emu(fy)}"/>
      <a:chExt cx="{_emu(fw)}" cy="{_emu(fh)}"/>
    </a:xfrm>
  </p:grpSpPr>
  {''.join(shapes)}
</p:grpSp>
'''
    return fragment


def render_svg(annotations, image_bbox):
    """Quick preview, no LibreOffice round-trip needed — mirrors render_diagram.py's own
    SVG-preview convention, scaled to a fixed 96 DPI canvas."""
    fx, fy, fw, fh = image_bbox
    dpi = 96
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{fw*dpi:.0f}" height="{fh*dpi:.0f}" '
              f'viewBox="0 0 {fw*dpi:.0f} {fh*dpi:.0f}">']

    def to_px(x_in, y_in):
        return (x_in - fx) * dpi, (y_in - fy) * dpi

    for ann in annotations:
        atype = ann.get("type")
        if atype == "highlight":
            x, y, w, h = _rect_to_in(ann["rect"], fx, fy, fw, fh, "highlight")
            px, py = to_px(x, y)
            parts.append(f'<rect x="{px:.1f}" y="{py:.1f}" width="{w*dpi:.1f}" height="{h*dpi:.1f}" '
                          f'fill="none" stroke="#2E3D77" stroke-width="3" rx="6"/>')
        elif atype == "callout":
            cx, cy = _point_to_in(ann["point"], fx, fy, fw, fh, "callout")
            pcx, pcy = to_px(cx, cy)
            r = max(CIRCLE_MIN_IN, CIRCLE_FRACTION_OF_HEIGHT * fh) / 2 * dpi
            parts.append(f'<circle cx="{pcx:.1f}" cy="{pcy:.1f}" r="{r:.1f}" fill="#2E3D77"/>')
            parts.append(f'<text x="{pcx:.1f}" y="{pcy+r*0.35:.1f}" text-anchor="middle" '
                          f'font-size="{r:.1f}" fill="#fff" font-weight="bold">{ann.get("step")}</text>')
        elif atype == "arrow":
            x1, y1 = _point_to_in(ann["from"], fx, fy, fw, fh, "arrow")
            x2, y2 = _point_to_in(ann["to"], fx, fy, fw, fh, "arrow")
            p1, p2 = to_px(x1, y1), to_px(x2, y2)
            parts.append(f'<line x1="{p1[0]:.1f}" y1="{p1[1]:.1f}" x2="{p2[0]:.1f}" y2="{p2[1]:.1f}" '
                          f'stroke="#2E3D77" stroke-width="2" marker-end="url(#arrowhead)"/>')
        elif atype == "redact":
            x, y, w, h = _rect_to_in(ann["rect"], fx, fy, fw, fh, "redact")
            px, py = to_px(x, y)
            parts.append(f'<rect x="{px:.1f}" y="{py:.1f}" width="{w*dpi:.1f}" height="{h*dpi:.1f}" fill="#111"/>')
        elif atype == "zoom":
            x, y, w, h = _rect_to_in(ann["rect"], fx, fy, fw, fh, "zoom")
            px, py = to_px(x, y)
            parts.append(f'<rect x="{px:.1f}" y="{py:.1f}" width="{w*dpi:.1f}" height="{h*dpi:.1f}" '
                          f'fill="none" stroke="#5B6FB0" stroke-width="2" stroke-dasharray="4,3" rx="4"/>')

    parts.append('<defs><marker id="arrowhead" markerWidth="8" markerHeight="8" refX="6" refY="3" '
                  'orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#2E3D77"/></marker></defs>')
    parts.append('</svg>')
    return "\n".join(parts)


def render(annotations, image_path, bbox, id_start=200, group_name="Annotations"):
    """bbox: (x_in, y_in, w_in, h_in) — the placeholder's geometry, same as
    inject_slide_xml.py's --bbox. Returns (ooxml_str, svg_str, fitted_rect)."""
    data = Path(image_path).read_bytes()
    dims = image_pixel_size(data)
    if not dims:
        raise AnnotationSpecError(f"could not read pixel dimensions of {image_path}")
    fitted = fit_extent(bbox, *dims)
    ooxml = render_ooxml(annotations, fitted, id_start=id_start, group_name=group_name)
    svg = render_svg(annotations, fitted)
    return ooxml, svg, fitted


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("annotations", type=Path, help='JSON file: {"annotations": [...]} or a bare list')
    ap.add_argument("--image", required=True, type=Path, help="The screenshot the annotations are authored against")
    ap.add_argument("--bbox", required=True, help="x_in,y_in,w_in,h_in — the placeholder's geometry (same value passed to inject_slide_xml.py picture)")
    ap.add_argument("--id-start", type=int, default=200, help="First shape id, above the target slide's existing max id and above the picture's own shape id")
    ap.add_argument("-o", "--out", type=Path, required=True, help="Output OOXML fragment path")
    ap.add_argument("--svg", type=Path, default=None, help="Output SVG preview path (defaults next to -o with .svg)")
    args = ap.parse_args()

    payload = json.loads(args.annotations.read_text(encoding="utf-8"))
    annotations = payload.get("annotations", payload) if isinstance(payload, dict) else payload
    if not isinstance(annotations, list):
        sys.exit("annotations file must be a JSON list, or an object with an \"annotations\" list")

    bbox = tuple(float(v) for v in args.bbox.split(","))
    if len(bbox) != 4:
        sys.exit("--bbox must be x_in,y_in,w_in,h_in")

    try:
        ooxml, svg, fitted = render(annotations, args.image, bbox, id_start=args.id_start)
    except (AnnotationSpecError, DiagramOverflowError) as exc:
        sys.exit(str(exc))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(ooxml, encoding="utf-8")
    svg_path = args.svg or args.out.with_suffix(".svg")
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_text(svg, encoding="utf-8")

    print(f"rendered {len(annotations)} annotation(s) -> {args.out}")
    print(f"fitted image rect: {fitted[0]:.2f},{fitted[1]:.2f} {fitted[2]:.2f}x{fitted[3]:.2f}in")
    print(f"preview -> {svg_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
