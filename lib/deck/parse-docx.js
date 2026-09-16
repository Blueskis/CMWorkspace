/**
 * Parse a .docx into a section outline plus the screenshots it embeds.
 *
 * Browser port of map_source.py + extract_assets.py + lib/section_walk.py, combined into
 * one pass. Those three are separate in Python only so two CLI scripts can share the
 * heading walk; here the outline and the assets come from a single traversal, which is
 * also the cheapest way to guarantee they agree — an image's section_id must be the same
 * id the outline gave that span, or Stage 3 cannot place a screenshot by the step it
 * illustrates.
 *
 * Parity with the Python implementation is asserted by test/run.js against shared
 * fixtures: same section_ids, same titles, same classifiers, same text.
 */

import { getJSZip, parseXml } from "./env.js";
import { attr, children, findAll, findFirst, parseRels, resolveTarget, textOf } from "./xml.js";

const HEADING_STYLE_RE = /^Heading\s*([0-9]+)$/i;
const CLAUSE_RE = /^(\d+(?:\.\d+)*)\.?\s+(\S.*)$/;

const STEP_CUE_RE = /\bstep\s+\d+\b|\b(?:click|select|enter|navigate|choose|submit|approve|reject)\b/i;
const REFERENCE_CUE_RE = /\bfield\b|\battribute\b|\bcolumn\b|\bdata\s+element\b|\bmandatory\b|\boptional\b/i;
const CONFIG_CUE_RE = /\bconfigur\w*\b|\bsetting\b|\bparameter\b|\bdefault\s+value\b/i;
const NONFUNC_CUE_RE = /\bperformance\b|\bavailability\b|\bsecurity\b|\bSLA\b|\bresponse\s+time\b|\baudit\s+log\b/i;

// Noise thresholds — identical to extract_assets.py's.
const HARD_DROP_REPEAT = 2;
const HARD_DROP_MIN_PX = 20;
const LOW_RES_MAX_PX = 400;
const TINY_MAX_PX = 150;
const WIDE_ASPECT = 3.0;

export function slugify(name) {
  return (name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "doc";
}

/** Cheap heuristic, deliberately biased toward 'procedure' — that is the classification
 *  Stage 5 enforces coverage on, so a false positive costs a review and a false negative
 *  costs a silently untaught task. Mirrors map_source.py's classify(). */
export function classify(title, text, hasNumberedSteps) {
  const probe = `${title}\n${(text || "").slice(0, 1500)}`;
  if (hasNumberedSteps || STEP_CUE_RE.test(probe)) return "procedure";
  if (NONFUNC_CUE_RE.test(probe)) return "non-functional";
  if (CONFIG_CUE_RE.test(probe)) return "config";
  if (REFERENCE_CUE_RE.test(probe)) return "reference";
  return "narrative";
}

/** FNV-1a over the bytes — stands in for Python's exact-bytes dict when counting repeats,
 *  so a letterhead reused through different media parts is still caught. */
function hashBytes(bytes) {
  let h = 0x811c9dc5;
  const step = Math.max(1, Math.floor(bytes.length / 4096)); // sample large images
  for (let i = 0; i < bytes.length; i += step) {
    h ^= bytes[i];
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return `${h.toString(16)}:${bytes.length}`;
}

export function imagePixelSize(bytes) {
  const b = bytes;
  const dv = new DataView(b.buffer, b.byteOffset, b.byteLength);
  if (b.length > 24 && b[0] === 0x89 && b[1] === 0x50) return { w: dv.getUint32(16), h: dv.getUint32(20), fmt: "png" };
  if (b.length > 4 && b[0] === 0xff && b[1] === 0xd8) {
    let i = 2;
    while (i < b.length - 9) {
      if (b[i] !== 0xff) { i++; continue; }
      const m = b[i + 1];
      if (m === 0xd8 || m === 0x01 || (m >= 0xd0 && m <= 0xd7)) { i += 2; continue; }
      const len = dv.getUint16(i + 2);
      if (m >= 0xc0 && m <= 0xcf && m !== 0xc4 && m !== 0xc8 && m !== 0xcc) {
        return { h: dv.getUint16(i + 5), w: dv.getUint16(i + 7), fmt: "jpeg" };
      }
      i += 2 + len;
    }
    return { w: 0, h: 0, fmt: "jpeg" };
  }
  if (b.length > 10 && b[0] === 0x47 && b[1] === 0x49) return { w: dv.getUint16(6, true), h: dv.getUint16(8, true), fmt: "gif" };
  if (b.length > 26 && b[0] === 0x42 && b[1] === 0x4d) return { w: dv.getInt32(18, true), h: Math.abs(dv.getInt32(22, true)), fmt: "bmp" };
  const head = new TextDecoder().decode(b.slice(0, 5));
  if (head.startsWith("<?xml") || head.startsWith("<svg")) return { w: 0, h: 0, fmt: "svg" };
  return { w: 0, h: 0, fmt: "other" };
}

function guessRole(w, h, fmt, repeat) {
  if (["svg", "emf", "wmf"].includes(fmt)) return "diagram-image";
  const maxDim = Math.max(w, h);
  if (maxDim && maxDim < TINY_MAX_PX) return repeat > 1 ? "icon" : "decorative";
  if (repeat > 1 && w && h && w < 300 && h < 300) return "logo";
  return "screenshot";
}

function qualityFlags(w, h) {
  const flags = [];
  const maxDim = Math.max(w, h);
  if (maxDim > 0 && maxDim < TINY_MAX_PX) flags.push("tiny");
  else if (maxDim > 0 && maxDim < LOW_RES_MAX_PX) flags.push("low_res");
  if (w && h) {
    const a = w / h;
    if (a > WIDE_ASPECT || a < 1 / WIDE_ASPECT) flags.push("very_wide");
  }
  return flags;
}

/** Heading paragraph -> [level, title, clause] or null. Mirrors section_walk.py. */
function headingFromParagraph(p) {
  const pStyle = findFirst(p, "pStyle");
  const styleVal = pStyle ? attr(pStyle, "val") : null;
  const text = textOf(p, "t").trim();
  if (styleVal === "Title") return [1, text || "(untitled)", null];
  const m = HEADING_STYLE_RE.exec(styleVal || "");
  if (!m) return null;
  const cm = CLAUSE_RE.exec(text);
  return [parseInt(m[1], 10), text || "(untitled)", cm ? cm[1] : null];
}

/**
 * @param {ArrayBuffer|Uint8Array} bytes
 * @param {string} filename
 * @returns {{document, sections, assets}}
 */
export async function parseDocx(bytes, filename) {
  const JSZip = await getJSZip();
  const zip = await JSZip.loadAsync(bytes);
  const documentId = slugify(filename.replace(/\.[^.]+$/, ""));

  const docFile = zip.file("word/document.xml");
  if (!docFile) throw new Error(`${filename}: not a Word document (no word/document.xml).`);
  const doc = await parseXml(await docFile.async("string"));

  let rels = {};
  const relsFile = zip.file("word/_rels/document.xml.rels");
  if (relsFile) rels = parseRels(await parseXml(await relsFile.async("string")));

  const body = findFirst(doc, "body");
  if (!body) throw new Error(`${filename}: no <w:body> — the file may be corrupt.`);

  // --- single document-order walk ---------------------------------------
  const stack = [];       // [level, title, section_id]
  const sections = [];
  const byId = new Map();
  let counter = 0;
  let current = null;
  const rawAssets = [];

  const newSectionId = (clause) =>
    clause ? `${documentId}#${clause}` : `${documentId}#s${++counter}`;

  function openHeading(level, title, clause) {
    while (stack.length && stack[stack.length - 1][0] >= level) stack.pop();
    const id = newSectionId(clause);
    stack.push([level, title, id]);
    current = {
      section_id: id, document_id: documentId,
      section_path: stack.map((s) => s[1]).join(" > "),
      title, level, clause_number: clause,
      page_start: null, page_end: null,
      char_count: 0, figure_count: 0, table_count: 0,
      _text: "", _steps: false,
    };
    sections.push(current);
    byId.set(id, current);
    return current;
  }
  const ensureRoot = () => { if (!current) openHeading(1, "(document start)", null); };

  const topLevel = children(body);
  for (let i = 0; i < topLevel.length; i++) {
    const el = topLevel[i];
    const tag = el.tagName.includes(":") ? el.tagName.split(":").pop() : el.tagName;

    if (tag === "p") {
      const heading = headingFromParagraph(el);
      if (heading) { openHeading(heading[0], heading[1], heading[2]); continue; }
      ensureRoot();

      if (findFirst(el, "numPr")) current._steps = true;

      const blips = findAll(el, "blip");
      if (blips.length) {
        current.figure_count += blips.length;
        // Caption: the FSD convention is a "Figure N: ..." line AFTER the image.
        let caption = null;
        for (let j = i + 1; j < topLevel.length; j++) {
          const nxt = topLevel[j];
          const ntag = nxt.tagName.includes(":") ? nxt.tagName.split(":").pop() : nxt.tagName;
          if (ntag !== "p") break;
          const t = textOf(nxt, "t").trim();
          if (t) caption = t;
          break;
        }
        const docPr = findFirst(el, "docPr");
        const alt = docPr ? (attr(docPr, "descr") || attr(docPr, "name")) : null;
        for (const blip of blips) {
          const rid = attr(blip, "embed");
          const target = rels[rid]?.target;
          if (!target) continue;
          rawAssets.push({
            part: resolveTarget(target, "word/document.xml"),
            alt_text: alt, section_id: current.section_id,
            nearest_heading: current.title, caption_candidate: caption,
          });
        }
      }

      const text = textOf(el, "t").trim();
      if (text) { current._text += text + "\n"; current.char_count += text.length; }
    } else if (tag === "tbl") {
      ensureRoot();
      current.table_count += 1;
      const cellText = textOf(el, "t").trim();
      if (cellText) { current._text += cellText + "\n"; current.char_count += cellText.length; }
    }
  }

  // --- resolve asset bytes, then noise-filter ----------------------------
  const loaded = [];
  for (const a of rawAssets) {
    const f = zip.file(a.part);
    if (!f) continue;
    const b = await f.async("uint8array");
    loaded.push({ ...a, bytes: b, hash: hashBytes(b) });
  }
  const repeats = new Map();
  for (const a of loaded) repeats.set(a.hash, (repeats.get(a.hash) ?? 0) + 1);

  const assets = [];
  let dropped = 0;
  for (const a of loaded) {
    const { w, h, fmt } = imagePixelSize(a.bytes);
    const repeat = repeats.get(a.hash);
    const isVector = ["svg", "emf", "wmf"].includes(fmt);
    if (!isVector && ((w > 0 && w < HARD_DROP_MIN_PX) || (h > 0 && h < HARD_DROP_MIN_PX))) { dropped++; continue; }
    if (repeat > HARD_DROP_REPEAT) { dropped++; continue; }
    const order = assets.length + 1;
    assets.push({
      asset_id: `${documentId}-img-${String(order).padStart(3, "0")}`,
      document_id: documentId,
      ext: fmt === "other" ? (a.part.split(".").pop() || "bin") : fmt === "jpeg" ? "jpg" : fmt,
      format: fmt, width_px: w, height_px: h,
      aspect: w && h ? Math.round((w / h) * 10000) / 10000 : null,
      doc_order_index: order,
      section_id: a.section_id, nearest_heading: a.nearest_heading,
      caption_candidate: a.caption_candidate, alt_text: a.alt_text,
      repeat_count: repeat, role: guessRole(w, h, fmt, repeat), quality: qualityFlags(w, h),
      bytes: a.bytes,
    });
  }

  const finished = sections.map((s) => {
    const { _text, _steps, ...rest } = s;
    return { ...rest, classifier: classify(s.title, _text, _steps), text: _text.trim() };
  });

  return {
    document: { document_id: documentId, filename, format: "docx", page_count: null },
    sections: finished,
    assets,
    assets_dropped: dropped,
  };
}
