/**
 * Render a screenshot's annotations[] into a native DrawingML shape group, plus an SVG
 * preview — the browser twin of `renderDiagram()`'s architecture and invariants.
 *
 * Browser port of skills/training-material-generator/scripts/render_annotation.py. Same
 * five types, same coordinate convention, same invariants:
 *
 *   - colours are ALWAYS <a:schemeClr val="accent1"/> (or accent2 for the zoom frame)
 *     references, never hex, so an annotation re-colours with the client's own theme;
 *   - fonts are never set, so they inherit from the template;
 *   - a callout number that will not fit its circle throws (DiagramOverflowError,
 *     re-exported from render-diagram.js) rather than emitting clipped text;
 *   - nothing here ever touches the screenshot's PIXELS — every shape is a vector overlay
 *     drawn OVER an untouched picture. The one legitimate exception, true redaction, is
 *     canvas-ops.js's job, not this module's; a `redact` annotation's shape here is
 *     COSMETIC ONLY (see the docstring on validateAnnotations below).
 *
 * Coordinates are 0-1 fractions of the SCREENSHOT IMAGE, origin top-left — never of the
 * slide or the placeholder. `renderAnnotation()` takes the already-computed FITTED rect
 * (build-pptx.js's own `fitExtent(geom, imagePixelSize(bytes))` — the exact rectangle the
 * picture was aspect-fitted and centred into), so an overlay coordinate always lands on
 * the same point of the picture the injector placed. Never hand-derive this rect a second
 * way; pass the one `composeSlide`'s picture-placement code already computed.
 */

import { emu, xmlEscape } from "./xml.js";
import { linesNeeded, fitFontSize } from "./text-fit.js";
import { DiagramOverflowError } from "./render-diagram.js";

export { DiagramOverflowError };

const CALLOUT_FONT_SIZES = [14, 12, 11, 10, 9, 8]; // same range render_annotation.py borrows from render_diagram.py

const CIRCLE_FRACTION_OF_HEIGHT = 0.05; // callout circle diameter, as a fraction of the fitted image height
const CIRCLE_MIN_IN = 0.22; // floor, so a heavily letterboxed image still gets a readable circle
const HIGHLIGHT_LINE_BASE_W = 28575; // EMU (~2.25pt), at a 4in-tall reference image
const ARROW_LINE_W = 19050; // EMU (~1.5pt) — matches render-diagram.js's connector weight
const REDACT_FILL_SCHEME = "tx1";
const ZOOM_FRAME_SCHEME = "accent2";

export const VALID_TYPES = ["highlight", "callout", "arrow", "redact", "zoom"];

export class AnnotationSpecError extends Error {}

function scaledLineWeight(baseW, fittedHIn, referenceHIn = 4.0) {
  return Math.max(9525, Math.min(baseW * 2, Math.round(baseW * (fittedHIn / referenceHIn))));
}

function fitCalloutFont(text, boxWIn, boxHIn) {
  const size = fitFontSize((pt) => linesNeeded(text, boxWIn, pt), boxHIn, CALLOUT_FONT_SIZES);
  if (size != null) return size;
  const smallest = CALLOUT_FONT_SIZES[CALLOUT_FONT_SIZES.length - 1];
  throw new DiagramOverflowError(
    `callout number "${text}" will not fit its circle even at ${smallest}pt (circle is ` +
      `${boxWIn.toFixed(2)}x${boxHIn.toFixed(2)}in) — this deck's callout numbering has ` +
      `run past what a legible circle can hold.`
  );
}

function pointToIn(point, fx, fy, fw, fh, label) {
  if (!Array.isArray(point) || point.length !== 2) {
    throw new AnnotationSpecError(`${label}: point must be [u, v]`);
  }
  const [u, v] = point;
  if (!(u >= 0 && u <= 1 && v >= 0 && v <= 1)) {
    throw new AnnotationSpecError(`${label}: point [${u}, ${v}] is outside 0-1 bounds`);
  }
  return [fx + u * fw, fy + v * fh];
}

function rectToIn(rect, fx, fy, fw, fh, label) {
  if (!Array.isArray(rect) || rect.length !== 4) {
    throw new AnnotationSpecError(`${label}: rect must be [u, v, du, dv]`);
  }
  const [u, v, du, dv] = rect;
  if (!(u >= 0 && u <= 1 && v >= 0 && v <= 1 && du > 0 && dv > 0 && u + du <= 1.0001 && v + dv <= 1.0001)) {
    throw new AnnotationSpecError(`${label}: rect [${rect.join(", ")}] is out of 0-1 bounds or extends past the image edge`);
  }
  return [fx + u * fw, fy + v * fh, du * fw, dv * fh];
}

// ---------------------------------------------------------------------------
// Per-type shape emitters
// ---------------------------------------------------------------------------

function highlightShape(sid, ann, fx, fy, fw, fh, groupName) {
  const [x, y, w, h] = rectToIn(ann.rect, fx, fy, fw, fh, `highlight (step ${ann.step})`);
  const lineW = scaledLineWeight(HIGHLIGHT_LINE_BASE_W, fh);
  return `
      <p:sp>
        <p:nvSpPr><p:cNvPr id="${sid}" name="${groupName} Highlight ${sid}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="${emu(x)}" y="${emu(y)}"/><a:ext cx="${emu(w)}" cy="${emu(h)}"/></a:xfrm>
          <a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom>
          <a:noFill/>
          <a:ln w="${lineW}"><a:solidFill><a:schemeClr val="accent1"/></a:solidFill></a:ln>
        </p:spPr>
      </p:sp>`;
}

function calloutShape(sid, ann, fx, fy, fw, fh, groupName) {
  const step = ann.step;
  if (!Number.isInteger(step) || step < 1) {
    throw new AnnotationSpecError(`callout at ${JSON.stringify(ann.point)}: "step" must be a positive integer`);
  }
  const [cx, cy] = pointToIn(ann.point, fx, fy, fw, fh, `callout (step ${step})`);
  const diameter = Math.max(CIRCLE_MIN_IN, CIRCLE_FRACTION_OF_HEIGHT * fh);
  const text = String(step);
  const fontPt = fitCalloutFont(text, diameter * 0.7, diameter * 0.7);
  const x = cx - diameter / 2, y = cy - diameter / 2;
  return `
      <p:sp>
        <p:nvSpPr><p:cNvPr id="${sid}" name="${groupName} Callout ${sid}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="${emu(x)}" y="${emu(y)}"/><a:ext cx="${emu(diameter)}" cy="${emu(diameter)}"/></a:xfrm>
          <a:prstGeom prst="ellipse"><a:avLst/></a:prstGeom>
          <a:solidFill><a:schemeClr val="accent1"/></a:solidFill>
        </p:spPr>
        <p:txBody>
          <a:bodyPr wrap="none" anchor="ctr" lIns="0" tIns="0" rIns="0" bIns="0"/>
          <a:p><a:pPr algn="ctr"/><a:r><a:rPr lang="en-US" sz="${fontPt * 100}" b="1"><a:solidFill><a:schemeClr val="bg1"/></a:solidFill></a:rPr><a:t>${xmlEscape(text)}</a:t></a:r></a:p>
        </p:txBody>
      </p:sp>`;
}

function arrowShape(sid, ann, fx, fy, fw, fh, groupName) {
  const [x1, y1] = pointToIn(ann.from, fx, fy, fw, fh, `arrow from (step ${ann.step})`);
  const [x2, y2] = pointToIn(ann.to, fx, fy, fw, fh, `arrow to (step ${ann.step})`);
  const offX = Math.min(x1, x2), offY = Math.min(y1, y2);
  const extCx = Math.max(Math.abs(x2 - x1), 0.01), extCy = Math.max(Math.abs(y2 - y1), 0.01);
  const flipH = x2 < x1 ? ' flipH="1"' : "";
  const flipV = y2 < y1 ? ' flipV="1"' : "";
  const lineW = scaledLineWeight(ARROW_LINE_W, fh);
  return `
      <p:cxnSp>
        <p:nvCxnSpPr><p:cNvPr id="${sid}" name="${groupName} Arrow ${sid}"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>
        <p:spPr>
          <a:xfrm${flipH}${flipV}><a:off x="${emu(offX)}" y="${emu(offY)}"/><a:ext cx="${emu(extCx)}" cy="${emu(extCy)}"/></a:xfrm>
          <a:prstGeom prst="straightConnector1"><a:avLst/></a:prstGeom>
          <a:ln w="${lineW}"><a:solidFill><a:schemeClr val="accent1"/></a:solidFill><a:tailEnd type="triangle"/></a:ln>
        </p:spPr>
      </p:cxnSp>`;
}

function redactShape(sid, ann, fx, fy, fw, fh, groupName) {
  const [x, y, w, h] = rectToIn(ann.rect, fx, fy, fw, fh, `redact (${ann.reason ?? "no reason given"})`);
  return `
      <p:sp>
        <p:nvSpPr><p:cNvPr id="${sid}" name="${groupName} Redact ${sid}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="${emu(x)}" y="${emu(y)}"/><a:ext cx="${emu(w)}" cy="${emu(h)}"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
          <a:solidFill><a:schemeClr val="${REDACT_FILL_SCHEME}"/></a:solidFill>
          <a:ln><a:noFill/></a:ln>
        </p:spPr>
      </p:sp>`;
}

/** Returns [frameXml, leaderXml] — two shapes, so the caller must reserve two ids. */
function zoomShapes(sid1, sid2, ann, fx, fy, fw, fh, groupName) {
  const [x, y, w, h] = rectToIn(ann.rect, fx, fy, fw, fh, `zoom (step ${ann.step})`);
  const lineW = scaledLineWeight(HIGHLIGHT_LINE_BASE_W, fh);
  const frame = `
      <p:sp>
        <p:nvSpPr><p:cNvPr id="${sid1}" name="${groupName} ZoomFrame ${sid1}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="${emu(x)}" y="${emu(y)}"/><a:ext cx="${emu(w)}" cy="${emu(h)}"/></a:xfrm>
          <a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom>
          <a:noFill/>
          <a:ln w="${lineW}"><a:solidFill><a:schemeClr val="${ZOOM_FRAME_SCHEME}"/></a:solidFill></a:ln>
        </p:spPr>
      </p:sp>`;

  const place = ann.place ?? "right";
  const edgeX = { left: x, right: x + w, below: x + w / 2 }[place];
  const edgeY = { left: y + h / 2, right: y + h / 2, below: y + h }[place];
  const leadX = { left: fx, right: fx + fw, below: edgeX }[place];
  const leadY = { left: edgeY, right: edgeY, below: fy + fh }[place];
  const offX = Math.min(edgeX, leadX), offY = Math.min(edgeY, leadY);
  const extCx = Math.max(Math.abs(leadX - edgeX), 0.01), extCy = Math.max(Math.abs(leadY - edgeY), 0.01);
  const flipH = leadX < edgeX ? ' flipH="1"' : "";
  const flipV = leadY < edgeY ? ' flipV="1"' : "";
  const leader = `
      <p:cxnSp>
        <p:nvCxnSpPr><p:cNvPr id="${sid2}" name="${groupName} ZoomLeader ${sid2}"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>
        <p:spPr>
          <a:xfrm${flipH}${flipV}><a:off x="${emu(offX)}" y="${emu(offY)}"/><a:ext cx="${emu(extCx)}" cy="${emu(extCy)}"/></a:xfrm>
          <a:prstGeom prst="straightConnector1"><a:avLst/></a:prstGeom>
          <a:ln w="${ARROW_LINE_W}"><a:solidFill><a:schemeClr val="${ZOOM_FRAME_SCHEME}"/></a:solidFill><a:prstDash val="dash"/></a:ln>
        </p:spPr>
      </p:cxnSp>`;
  return [frame, leader];
}

// ---------------------------------------------------------------------------
// OOXML renderer
// ---------------------------------------------------------------------------

function renderOoxml(annotations, fx, fy, fw, fh, idStart, groupName) {
  let nextId = idStart + 1; // idStart itself is reserved for the group shape
  const shapes = [];

  annotations.forEach((ann, i) => {
    if (!VALID_TYPES.includes(ann.type)) {
      throw new AnnotationSpecError(`annotation ${i}: unknown type "${ann.type}" — must be one of ${VALID_TYPES.join(", ")}`);
    }
    if (ann.type === "highlight") shapes.push(highlightShape(nextId++, ann, fx, fy, fw, fh, groupName));
    else if (ann.type === "callout") shapes.push(calloutShape(nextId++, ann, fx, fy, fw, fh, groupName));
    else if (ann.type === "arrow") shapes.push(arrowShape(nextId++, ann, fx, fy, fw, fh, groupName));
    else if (ann.type === "redact") shapes.push(redactShape(nextId++, ann, fx, fy, fw, fh, groupName));
    else if (ann.type === "zoom") {
      const [frame, leader] = zoomShapes(nextId, nextId + 1, ann, fx, fy, fw, fh, groupName);
      nextId += 2;
      shapes.push(frame, leader);
    }
  });

  const ooxml = `<p:grpSp>
  <p:nvGrpSpPr><p:cNvPr id="${idStart}" name="${groupName}"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
  <p:grpSpPr>
    <a:xfrm>
      <a:off x="${emu(fx)}" y="${emu(fy)}"/><a:ext cx="${emu(fw)}" cy="${emu(fh)}"/>
      <a:chOff x="${emu(fx)}" y="${emu(fy)}"/><a:chExt cx="${emu(fw)}" cy="${emu(fh)}"/>
    </a:xfrm>
  </p:grpSpPr>${shapes.join("")}
</p:grpSp>`;
  return { ooxml, idsUsed: nextId - idStart };
}

// ---------------------------------------------------------------------------
// SVG preview — matches render_annotation.py's fixed-hex preview, distinct from the
// schemeClr OOXML output (a preview needs a concrete colour, not a theme reference).
// ---------------------------------------------------------------------------

function renderSvg(annotations, fx, fy, fw, fh) {
  const dpi = 96;
  const parts = [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${(fw * dpi).toFixed(0)}" height="${(fh * dpi).toFixed(0)}" viewBox="0 0 ${(fw * dpi).toFixed(0)} ${(fh * dpi).toFixed(0)}">`,
  ];
  const toPx = (xIn, yIn) => [(xIn - fx) * dpi, (yIn - fy) * dpi];

  for (const ann of annotations) {
    if (ann.type === "highlight") {
      const [x, y, w, h] = rectToIn(ann.rect, fx, fy, fw, fh, "highlight");
      const [px, py] = toPx(x, y);
      parts.push(`<rect x="${px.toFixed(1)}" y="${py.toFixed(1)}" width="${(w * dpi).toFixed(1)}" height="${(h * dpi).toFixed(1)}" fill="none" stroke="#2E3D77" stroke-width="3" rx="6"/>`);
    } else if (ann.type === "callout") {
      const [cx, cy] = pointToIn(ann.point, fx, fy, fw, fh, "callout");
      const [pcx, pcy] = toPx(cx, cy);
      const r = (Math.max(CIRCLE_MIN_IN, CIRCLE_FRACTION_OF_HEIGHT * fh) / 2) * dpi;
      parts.push(`<circle cx="${pcx.toFixed(1)}" cy="${pcy.toFixed(1)}" r="${r.toFixed(1)}" fill="#2E3D77"/>`);
      parts.push(`<text x="${pcx.toFixed(1)}" y="${(pcy + r * 0.35).toFixed(1)}" text-anchor="middle" font-size="${r.toFixed(1)}" fill="#fff" font-weight="bold">${xmlEscape(ann.step)}</text>`);
    } else if (ann.type === "arrow") {
      const [x1, y1] = pointToIn(ann.from, fx, fy, fw, fh, "arrow");
      const [x2, y2] = pointToIn(ann.to, fx, fy, fw, fh, "arrow");
      const [p1x, p1y] = toPx(x1, y1), [p2x, p2y] = toPx(x2, y2);
      parts.push(`<line x1="${p1x.toFixed(1)}" y1="${p1y.toFixed(1)}" x2="${p2x.toFixed(1)}" y2="${p2y.toFixed(1)}" stroke="#2E3D77" stroke-width="2" marker-end="url(#ann-arrowhead)"/>`);
    } else if (ann.type === "redact") {
      const [x, y, w, h] = rectToIn(ann.rect, fx, fy, fw, fh, "redact");
      const [px, py] = toPx(x, y);
      parts.push(`<rect x="${px.toFixed(1)}" y="${py.toFixed(1)}" width="${(w * dpi).toFixed(1)}" height="${(h * dpi).toFixed(1)}" fill="#111"/>`);
    } else if (ann.type === "zoom") {
      const [x, y, w, h] = rectToIn(ann.rect, fx, fy, fw, fh, "zoom");
      const [px, py] = toPx(x, y);
      parts.push(`<rect x="${px.toFixed(1)}" y="${py.toFixed(1)}" width="${(w * dpi).toFixed(1)}" height="${(h * dpi).toFixed(1)}" fill="none" stroke="#5B6FB0" stroke-width="2" stroke-dasharray="4,3" rx="4"/>`);
    }
  }
  parts.push('<defs><marker id="ann-arrowhead" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#2E3D77"/></marker></defs>');
  parts.push("</svg>");
  return parts.join("\n");
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

/**
 * @param {object[]} annotations
 * @param {number[]} fittedRect [fx, fy, fw, fh] in inches — the ALREADY-FITTED image rect
 *   (build-pptx.js's `fitExtent(geom, imagePixelSize(bytes))`), never the raw placeholder bbox.
 * @param {object} [opts]
 * @returns {{ooxml: string, svg: string, idsUsed: number}}
 */
export function renderAnnotation(annotations, fittedRect, { idStart = 200, groupName = "Annotations" } = {}) {
  const [fx, fy, fw, fh] = fittedRect;
  const { ooxml, idsUsed } = renderOoxml(annotations, fx, fy, fw, fh, idStart, groupName);
  const svg = renderSvg(annotations, fx, fy, fw, fh);
  return { ooxml, svg, idsUsed };
}

// ---------------------------------------------------------------------------
// Plan-level validation — used by plan.js right after Claude's annotate-stage reply, and
// by qa.js's check 6 (same rules, same field names, so a plan hand-edited after generation
// is still caught exactly as generation-time output is).
// ---------------------------------------------------------------------------

/**
 * Validates one image block's annotations against its bound bullets count. Returns
 * `{errors: string[]}` — never throws; callers decide whether an error list means "drop
 * the whole set" (plan.js, generation time) or "hard-fail the report" (qa.js, audit time).
 * Mirrors qa_training.py's 6a/6b checks exactly, including the "pixel coordinate slip"
 * guard: a value greater than 1 anywhere in a rect/point/from/to is almost always a raw
 * pixel number Claude returned instead of a 0-1 fraction, and is called out by name so the
 * failure is legible rather than a silent out-of-bounds rejection.
 */
export function validateAnnotations(annotations, bulletCount) {
  const errors = [];
  const checkNums = (arr, label) => {
    for (const v of arr) {
      if (typeof v !== "number" || Number.isNaN(v)) { errors.push(`${label}: non-numeric coordinate`); return; }
      if (v > 1) { errors.push(`${label}: value ${v} looks like a pixel coordinate, not a 0-1 fraction`); return; }
      if (v < 0) { errors.push(`${label}: value ${v} is negative`); return; }
    }
  };

  const steps = [];
  for (const ann of annotations ?? []) {
    const label = `${ann.type ?? "?"}${ann.step != null ? ` step ${ann.step}` : ""}`;
    if (!VALID_TYPES.includes(ann.type)) { errors.push(`unknown annotation type "${ann.type}"`); continue; }
    if (ann.type === "highlight" || ann.type === "redact" || ann.type === "zoom") {
      if (!Array.isArray(ann.rect) || ann.rect.length !== 4) errors.push(`${label}: rect must be [u,v,du,dv]`);
      else checkNums(ann.rect, label);
    } else if (ann.type === "callout") {
      if (!Array.isArray(ann.point) || ann.point.length !== 2) errors.push(`${label}: point must be [u,v]`);
      else checkNums(ann.point, label);
    } else if (ann.type === "arrow") {
      if (!Array.isArray(ann.from) || ann.from.length !== 2) errors.push(`${label}: "from" must be [u,v]`);
      else checkNums(ann.from, `${label} from`);
      if (!Array.isArray(ann.to) || ann.to.length !== 2) errors.push(`${label}: "to" must be [u,v]`);
      else checkNums(ann.to, `${label} to`);
    }
    if (ann.type === "redact" && !ann.reason) errors.push(`redact annotation missing "reason"`);
    if (["highlight", "callout", "arrow", "zoom"].includes(ann.type) && ann.step != null) steps.push(ann.step);
  }

  if (steps.length) {
    if (bulletCount == null) {
      errors.push(`${steps.length} annotation(s) reference a step, but no single bullets block was found to bind against`);
    } else {
      const expected = new Set(Array.from({ length: bulletCount }, (_, i) => i + 1));
      const got = [...steps].sort((a, b) => a - b);
      const gotSet = new Set(got);
      const setsEqual = gotSet.size === expected.size && [...expected].every((v) => gotSet.has(v));
      if (!setsEqual || got.length !== steps.length) {
        errors.push(`step numbers [${got.join(", ")}] do not match bullets 1..${bulletCount} exactly (duplicates, gaps, or out-of-range)`);
      }
    }
  }
  return { errors };
}
