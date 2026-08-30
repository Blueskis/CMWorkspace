/**
 * Render a diagram spec into a native DrawingML shape group, plus an SVG preview.
 *
 * Browser port of skills/training-material-generator/scripts/render_diagram.py. Same five
 * types, same geometry, same invariants:
 *
 *   - colours are ALWAYS <a:schemeClr val="accent1"/> references, never hex, so a diagram
 *     re-colours with the client's own theme instead of drifting off-template;
 *   - fonts are never set, so they inherit from the template;
 *   - a label that will not fit at the smallest allowed size throws rather than emitting
 *     clipped text.
 *
 * The swimlane connector fix from the v0.2 run ports with it: connectors join box EDGES,
 * not centres, because a centre-to-centre line on a cross-lane step draws straight through
 * the intervening box's text.
 *
 * The SVG preview is not decoration here — the UI shows it in the confirm step so a
 * diagram can be judged before the deck is built.
 */

import { emu, xmlEscape } from "./xml.js";

const PT_PER_INCH = 72;
const FONT_SIZES = [14, 12, 11, 10, 9, 8];
const CHAR_WIDTH_FACTOR = 0.52; // average glyph width as a fraction of font size
const LINE_HEIGHT_FACTOR = 1.25;
const PALETTE_CYCLE = ["accent1", "accent2", "accent3", "accent4", "accent5", "accent6"];

export class DiagramSpecError extends Error {}
export class DiagramOverflowError extends Error {}

// ---------------------------------------------------------------------------
// Text fit
// ---------------------------------------------------------------------------

function linesNeeded(text, boxWIn, fontPt) {
  const charsPerLine = Math.max(1, Math.floor((boxWIn * PT_PER_INCH) / (fontPt * CHAR_WIDTH_FACTOR)));
  return Math.max(1, Math.ceil(String(text).length / charsPerLine));
}

function fitFont(text, boxWIn, boxHIn) {
  for (const size of FONT_SIZES) {
    const lines = linesNeeded(text, boxWIn, size);
    if ((lines * size * LINE_HEIGHT_FACTOR) / PT_PER_INCH <= boxHIn) return size;
  }
  const smallest = FONT_SIZES[FONT_SIZES.length - 1];
  const lines = linesNeeded(text, boxWIn, smallest);
  const neededH = (lines * smallest * LINE_HEIGHT_FACTOR) / PT_PER_INCH;
  throw new DiagramOverflowError(
    `diagram label will not fit: "${text}" needs ${neededH.toFixed(2)}in tall at ${smallest}pt ` +
      `(box is ${boxWIn.toFixed(2)}x${boxHIn.toFixed(2)}in). Shorten the label or split the diagram.`
  );
}

// ---------------------------------------------------------------------------
// Scene model — shared by the OOXML and SVG renderers
// ---------------------------------------------------------------------------

function makeBox(x, y, w, h, text, fill, shape = "rect") {
  const fontPt = fitFont(text, w - 0.15, h - 0.15);
  return { type: "box", shape, x, y, w, h, text, fill, fontPt };
}
const makeArrow = (x1, y1, x2, y2) => ({ type: "arrow", x1, y1, x2, y2 });
/** A structural line (lane divider/border) — no arrowhead, unlike makeArrow. */
const makeLine = (x1, y1, x2, y2) => ({ type: "line", x1, y1, x2, y2 });
const makeLabel = (x, y, w, h, text, align = "ctr", fontPt = 10) => ({
  type: "label", x, y, w, h, text, align, fontPt,
});

// ---------------------------------------------------------------------------
// Layouts
// ---------------------------------------------------------------------------

function layoutProcess(spec, bx, by, bw, bh) {
  const steps = spec.steps ?? [];
  if (steps.length === 0) throw new DiagramSpecError("process diagram needs a non-empty 'steps' list");
  const n = steps.length;
  const gap = 0.3;
  const boxW = (bw - gap * (n - 1)) / n;
  const boxH = Math.min(1.4, bh);
  const y = by + (bh - boxH) / 2;
  const scene = [];
  steps.forEach((step, i) => {
    const x = bx + i * (boxW + gap);
    scene.push(makeBox(x, y, boxW, boxH, step, PALETTE_CYCLE[i % PALETTE_CYCLE.length]));
    if (i < n - 1) scene.push(makeArrow(x + boxW, y + boxH / 2, x + boxW + gap, y + boxH / 2));
  });
  return scene;
}

function layoutSwimlane(spec, bx, by, bw, bh) {
  const roles = spec.roles ?? [];
  const steps = spec.steps ?? [];
  if (roles.length === 0 || steps.length === 0) {
    throw new DiagramSpecError("swimlane diagram needs non-empty 'roles' and 'steps'");
  }
  const laneH = bh / roles.length;
  const labelW = Math.min(1.6, bw * 0.2);
  const colW = (bw - labelW) / steps.length;
  const scene = [];

  roles.forEach((role, r) => {
    const ly = by + r * laneH;
    scene.push(makeLabel(bx, ly, labelW, laneH, role, "l", 11));
    scene.push(makeLine(bx, ly, bx + bw, ly));
  });
  scene.push(makeLine(bx, by + bh, bx + bw, by + bh));
  scene.push(makeLine(bx + labelW, by, bx + labelW, by + bh));

  const roleIndex = new Map(roles.map((r, i) => [r, i]));
  const boxH = Math.min(1.0, laneH * 0.7);
  let prevExit = null;

  steps.forEach((item, c) => {
    if (!roleIndex.has(item.role)) {
      throw new DiagramSpecError(
        `swimlane step references unknown role "${item.role}" — not in ${JSON.stringify(roles)}`
      );
    }
    const r = roleIndex.get(item.role);
    const cx = bx + labelW + c * colW;
    const cy = by + r * laneH + (laneH - boxH) / 2;
    const boxX = cx + 0.1;
    const boxW = colW - 0.2;
    scene.push(makeBox(boxX, cy, boxW, boxH, item.step, PALETTE_CYCLE[r % PALETTE_CYCLE.length]));
    // Edge-to-edge, not centre-to-centre — see the module docstring.
    const entry = [boxX, cy + boxH / 2];
    const exit = [boxX + boxW, cy + boxH / 2];
    if (prevExit) scene.push(makeArrow(prevExit[0], prevExit[1], entry[0], entry[1]));
    prevExit = exit;
  });
  return scene;
}

function layoutDecision(spec, bx, by, bw, bh) {
  const rules = spec.rules ?? [];
  if (rules.length === 0) throw new DiagramSpecError("decision diagram needs a non-empty 'rules' list");
  const rowH = bh / rules.length;
  const boxH = Math.min(0.9, rowH * 0.7);
  const condW = bw * 0.55;
  const outW = bw * 0.35;
  const gap = bw * 0.1;
  const scene = [];
  rules.forEach((rule, i) => {
    const y = by + i * rowH + (rowH - boxH) / 2;
    scene.push(makeBox(bx, y, condW, boxH, rule.condition, "lt2", "diamond"));
    scene.push(makeArrow(bx + condW, y + boxH / 2, bx + condW + gap, y + boxH / 2));
    scene.push(makeBox(bx + condW + gap, y, outW, boxH, rule.outcome, PALETTE_CYCLE[i % PALETTE_CYCLE.length]));
  });
  return scene;
}

function layoutHierarchy(spec, bx, by, bw, bh) {
  const root = spec.root;
  if (!root) throw new DiagramSpecError("hierarchy diagram needs a 'root' node");

  const levels = [];
  (function walk(node, depth) {
    while (levels.length <= depth) levels.push([]);
    levels[depth].push(node);
    (node.children ?? []).forEach((c) => walk(c, depth + 1));
  })(root, 0);

  const rowH = bh / levels.length;
  const boxH = Math.min(0.8, rowH * 0.6);
  const positions = new Map();

  (function assignX(node, depth, xLo, xHi) {
    const kids = node.children ?? [];
    positions.set(node, [(xLo + xHi) / 2, depth]);
    if (kids.length) {
      const step = (xHi - xLo) / kids.length;
      kids.forEach((c, i) => assignX(c, depth + 1, xLo + i * step, xLo + (i + 1) * step));
    }
  })(root, 0, bx, bx + bw);

  const widest = Math.max(...levels.map((l) => l.length));
  const boxW = Math.min(2.2, bw / widest);
  const scene = [];

  (function place(node, depth) {
    const [cx] = positions.get(node);
    const y = by + depth * rowH + (rowH - boxH) / 2;
    scene.push(makeBox(cx - boxW / 2, y, boxW, boxH, node.name, PALETTE_CYCLE[depth % PALETTE_CYCLE.length]));
    (node.children ?? []).forEach((child) => {
      const [ccx] = positions.get(child);
      const cy = by + (depth + 1) * rowH + (rowH - boxH) / 2;
      scene.push(makeArrow(cx, y + boxH, ccx, cy));
      place(child, depth + 1);
    });
  })(root, 0);
  return scene;
}

function layoutTimeline(spec, bx, by, bw, bh) {
  const milestones = spec.milestones ?? [];
  if (milestones.length === 0) throw new DiagramSpecError("timeline diagram needs a non-empty 'milestones' list");
  const n = milestones.length;
  const axisY = by + bh * 0.5;
  const scene = [makeLine(bx, axisY, bx + bw, axisY)];
  const boxW = Math.min(1.8, (bw / n) * 0.9);
  const boxH = Math.min(0.7, bh * 0.3);
  milestones.forEach((m, i) => {
    const cx = bx + (bw / n) * (i + 0.5);
    const above = i % 2 === 0;
    const y = above ? axisY - boxH - 0.15 : axisY + 0.15;
    scene.push(makeLine(cx, axisY, cx, y + (above ? boxH : 0)));
    scene.push(makeBox(cx - boxW / 2, y, boxW, boxH, m.label, PALETTE_CYCLE[i % PALETTE_CYCLE.length]));
    if (m.date) {
      const dateY = above ? y - 0.3 : y + boxH + 0.05;
      scene.push(makeLabel(cx - boxW / 2, dateY, boxW, 0.25, m.date, "ctr", 9));
    }
  });
  return scene;
}

const LAYOUTS = {
  process: layoutProcess,
  swimlane: layoutSwimlane,
  decision: layoutDecision,
  hierarchy: layoutHierarchy,
  timeline: layoutTimeline,
};

export const DIAGRAM_TYPES = Object.keys(LAYOUTS);

// ---------------------------------------------------------------------------
// OOXML renderer
// ---------------------------------------------------------------------------

function renderOoxml(scene, bx, by, bw, bh, idStart, groupName) {
  let nextId = idStart;
  const groupId = nextId++;
  const shapes = [];

  for (const node of scene) {
    const sid = nextId++;
    if (node.type === "box") {
      const preset = node.shape === "diamond" ? "ellipse" : "roundRect";
      shapes.push(`
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="${sid}" name="${groupName} Box ${sid}"/><p:cNvSpPr/><p:nvPr/>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="${emu(node.x)}" y="${emu(node.y)}"/><a:ext cx="${emu(node.w)}" cy="${emu(node.h)}"/></a:xfrm>
          <a:prstGeom prst="${preset}"><a:avLst/></a:prstGeom>
          <a:solidFill><a:schemeClr val="${node.fill}"/></a:solidFill>
        </p:spPr>
        <p:txBody>
          <a:bodyPr wrap="square" anchor="ctr"><a:normAutofit/></a:bodyPr>
          <a:p><a:pPr algn="ctr"/><a:r><a:rPr lang="en-US" sz="${node.fontPt * 100}"/><a:t>${xmlEscape(node.text)}</a:t></a:r></a:p>
        </p:txBody>
      </p:sp>`);
    } else if (node.type === "label") {
      shapes.push(`
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="${sid}" name="${groupName} Label ${sid}"/><p:cNvSpPr txBox="1"/><p:nvPr/>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm><a:off x="${emu(node.x)}" y="${emu(node.y)}"/><a:ext cx="${emu(node.w)}" cy="${emu(node.h)}"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/>
        </p:spPr>
        <p:txBody>
          <a:bodyPr wrap="square" anchor="ctr"/>
          <a:p><a:pPr algn="${node.align}"/><a:r><a:rPr lang="en-US" sz="${node.fontPt * 100}"/><a:t>${xmlEscape(node.text)}</a:t></a:r></a:p>
        </p:txBody>
      </p:sp>`);
    } else {
      const { x1, y1, x2, y2 } = node;
      const offX = Math.min(x1, x2);
      const offY = Math.min(y1, y2);
      const extCx = Math.max(Math.abs(x2 - x1), 0.01);
      const extCy = Math.max(Math.abs(y2 - y1), 0.01);
      const flipH = x2 < x1 ? ' flipH="1"' : "";
      const flipV = y2 < y1 ? ' flipV="1"' : "";
      const tailEnd = node.type === "arrow" ? '<a:tailEnd type="arrow"/>' : "";
      shapes.push(`
      <p:cxnSp>
        <p:nvCxnSpPr>
          <p:cNvPr id="${sid}" name="${groupName} Connector ${sid}"/><p:cNvCxnSpPr/><p:nvPr/>
        </p:nvCxnSpPr>
        <p:spPr>
          <a:xfrm${flipH}${flipV}><a:off x="${emu(offX)}" y="${emu(offY)}"/><a:ext cx="${emu(extCx)}" cy="${emu(extCy)}"/></a:xfrm>
          <a:prstGeom prst="straightConnector1"><a:avLst/></a:prstGeom>
          <a:ln w="19050"><a:solidFill><a:schemeClr val="tx1"/></a:solidFill>${tailEnd}</a:ln>
        </p:spPr>
      </p:cxnSp>`);
    }
  }

  return `<p:grpSp>
  <p:nvGrpSpPr>
    <p:cNvPr id="${groupId}" name="${groupName}"/><p:cNvGrpSpPr/><p:nvPr/>
  </p:nvGrpSpPr>
  <p:grpSpPr>
    <a:xfrm>
      <a:off x="${emu(bx)}" y="${emu(by)}"/><a:ext cx="${emu(bw)}" cy="${emu(bh)}"/>
      <a:chOff x="${emu(bx)}" y="${emu(by)}"/><a:chExt cx="${emu(bw)}" cy="${emu(bh)}"/>
    </a:xfrm>
  </p:grpSpPr>${shapes.join("")}
</p:grpSp>`;
}

// ---------------------------------------------------------------------------
// SVG preview
// ---------------------------------------------------------------------------

const PREVIEW_FALLBACK = {
  accent1: "#4472C4", accent2: "#ED7D31", accent3: "#A5A5A5",
  accent4: "#FFC000", accent5: "#5B9BD5", accent6: "#70AD47",
  lt1: "#FFFFFF", lt2: "#E7E6E6", tx1: "#000000",
};

function renderSvg(scene, bx, by, bw, bh, themeColors) {
  // Preview in the template's OWN colours where known, so the confirm step shows what
  // the slide will actually look like rather than a generic stand-in.
  const colors = { ...PREVIEW_FALLBACK };
  for (const [k, v] of Object.entries(themeColors ?? {})) {
    if (typeof v === "string" && /^[0-9a-fA-F]{6}$/.test(v)) colors[k] = `#${v}`;
  }
  const dpi = 96;
  const parts = [
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${bx * dpi} ${by * dpi} ${bw * dpi} ${bh * dpi}" font-family="system-ui, sans-serif" width="100%">`,
    `<defs><marker id="dgm-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#444"/></marker></defs>`,
  ];
  const txt = (t, x, y, size, anchor, fill) =>
    `<text x="${x.toFixed(0)}" y="${y.toFixed(0)}" font-size="${size}" text-anchor="${anchor}" dominant-baseline="middle" fill="${fill}">${xmlEscape(t)}</text>`;

  for (const node of scene) {
    if (node.type === "box") {
      const x = node.x * dpi, y = node.y * dpi, w = node.w * dpi, h = node.h * dpi;
      const fill = colors[node.fill] ?? "#999";
      parts.push(
        node.shape === "diamond"
          ? `<ellipse cx="${(x + w / 2).toFixed(0)}" cy="${(y + h / 2).toFixed(0)}" rx="${(w / 2).toFixed(0)}" ry="${(h / 2).toFixed(0)}" fill="${fill}" stroke="#333"/>`
          : `<rect x="${x.toFixed(0)}" y="${y.toFixed(0)}" width="${w.toFixed(0)}" height="${h.toFixed(0)}" rx="6" fill="${fill}" stroke="#333"/>`
      );
      parts.push(txt(node.text, x + w / 2, y + h / 2, node.fontPt, "middle", "#111"));
    } else if (node.type === "label") {
      const x = node.x * dpi, y = node.y * dpi, w = node.w * dpi, h = node.h * dpi;
      const anchor = node.align === "l" ? "start" : node.align === "r" ? "end" : "middle";
      const tx = anchor === "start" ? x : anchor === "end" ? x + w : x + w / 2;
      parts.push(txt(node.text, tx, y + h / 2, node.fontPt, anchor, "#333"));
    } else {
      const marker = node.type === "arrow" ? ' marker-end="url(#dgm-arrow)"' : "";
      parts.push(
        `<line x1="${(node.x1 * dpi).toFixed(0)}" y1="${(node.y1 * dpi).toFixed(0)}" x2="${(node.x2 * dpi).toFixed(0)}" y2="${(node.y2 * dpi).toFixed(0)}" stroke="#444" stroke-width="2"${marker}/>`
      );
    }
  }
  parts.push("</svg>");
  return parts.join("\n");
}

// ---------------------------------------------------------------------------

/**
 * @param {string} diagramType one of DIAGRAM_TYPES
 * @param {object} spec        the type's own spec shape
 * @param {number[]} bbox      [x_in, y_in, w_in, h_in] — normally a placeholder's geometry
 * @returns {{ooxml: string, svg: string}}
 */
export function renderDiagram(diagramType, spec, bbox, { idStart = 100, themeColors = null } = {}) {
  const layout = LAYOUTS[diagramType];
  if (!layout) {
    throw new DiagramSpecError(
      `unknown diagram type "${diagramType}" — must be one of ${DIAGRAM_TYPES.join(", ")}`
    );
  }
  const [bx, by, bw, bh] = bbox;
  const scene = layout(spec, bx, by, bw, bh);
  return {
    ooxml: renderOoxml(scene, bx, by, bw, bh, idStart, diagramType[0].toUpperCase() + diagramType.slice(1)),
    svg: renderSvg(scene, bx, by, bw, bh, themeColors),
  };
}
