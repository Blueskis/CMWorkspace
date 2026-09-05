/**
 * Parse a .pdf into a section outline plus whatever images it embeds.
 *
 * This is the weakest of the three input paths, and the UI says so when it yields little:
 * a PDF has no heading STRUCTURE, only text that happens to look like headings, so the
 * outline is inferred from clause numbering (5.1.11) and short un-punctuated lines. A
 * Word original always parses better and should be preferred when one exists.
 *
 * Two hazards handled here, both found in real documents rather than anticipated:
 *
 *  - TABLE OF CONTENTS. The first thing tried on a real tender PDF produced 106 "heading
 *    candidates", nearly all of them TOC entries with dot leaders
 *    ("1. INTRODUCTION........ 4"). Those are stripped, and a run of them early in the
 *    document is treated as a contents block and skipped entirely.
 *  - CSP. pdf.js cannot load its worker in the artifact, so env.js arranges the
 *    main-thread path; every option that would trigger a network fetch is disabled below.
 */

import { getPdfJs } from "./env.js";
import { classify, imagePixelSize, slugify } from "./parse-docx.js";

const CLAUSE_RE = /^(\d+(?:\.\d+)*)\.?\s+(\S.*)$/;
// A TOC line: dot leaders, or a trailing page number after whitespace.
const TOC_LINE_RE = /\.{4,}|\s\.\s?\.\s?\.|\.{2,}\s*\d+\s*$/;
const TRAILING_PAGENO_RE = /\s+\d{1,3}\s*$/;

function toPlainU8(bytes) {
  if (bytes instanceof ArrayBuffer) return new Uint8Array(bytes);
  if (ArrayBuffer.isView(bytes)) return new Uint8Array(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  return new Uint8Array(bytes);
}

function looksLikeHeading(line) {
  if (line.length > 120) return false;
  if (TOC_LINE_RE.test(line)) return false;
  if (/[.,;:]$/.test(line)) return false;
  return CLAUSE_RE.test(line);
}

/** Reassemble pdf.js's positioned text runs into lines by their y coordinate. */
function itemsToLines(items) {
  const lines = [];
  let lastY = null;
  let buf = "";
  for (const item of items) {
    const y = item.transform?.[5];
    if (lastY !== null && Math.abs(y - lastY) > 2) {
      if (buf.trim()) lines.push(buf.trim());
      buf = "";
    }
    buf += item.str;
    lastY = y;
  }
  if (buf.trim()) lines.push(buf.trim());
  return lines;
}

export async function parsePdf(bytes, filename, { onProgress = null } = {}) {
  const pdfjsLib = await getPdfJs();
  const documentId = slugify(filename.replace(/\.[^.]+$/, ""));

  const doc = await pdfjsLib.getDocument({
    // pdf.js rejects a Node Buffer outright, and Buffer IS a Uint8Array subclass — so an
    // `instanceof Uint8Array` check passes it straight through. Re-view the bytes as a
    // plain Uint8Array so the same call works for Buffer, ArrayBuffer and typed arrays.
    data: toPlainU8(bytes),
    // Each of these would be a network fetch the artifact CSP blocks.
    useWorkerFetch: false,
    isEvalSupported: false,
    disableFontFace: true,
    useSystemFonts: false,
  }).promise;

  const stack = [];
  const sections = [];
  const assets = [];
  let counter = 0;
  let current = null;
  let tocLinesSeen = 0;

  const openHeading = (level, title, clause, page) => {
    while (stack.length && stack[stack.length - 1][0] >= level) stack.pop();
    const id = clause ? `${documentId}#${clause}` : `${documentId}#s${++counter}`;
    stack.push([level, title, id]);
    current = {
      section_id: id, document_id: documentId,
      section_path: stack.map((s) => s[1]).join(" > "),
      title, level, clause_number: clause,
      page_start: page, page_end: page,
      char_count: 0, figure_count: 0, table_count: 0,
      _text: "", _steps: false,
    };
    sections.push(current);
    return current;
  };
  const ensureRoot = (page) => { if (!current) openHeading(1, "(document start)", null, page); };

  for (let p = 1; p <= doc.numPages; p++) {
    onProgress?.(p, doc.numPages);
    const page = await doc.getPage(p);

    for (const line of itemsToLines((await page.getTextContent()).items)) {
      if (TOC_LINE_RE.test(line)) { tocLinesSeen++; continue; }
      if (looksLikeHeading(line)) {
        const m = CLAUSE_RE.exec(line);
        const clause = m[1];
        const title = m[2].replace(TRAILING_PAGENO_RE, "").trim();
        openHeading(clause.split(".").length, title, clause, p);
        continue;
      }
      ensureRoot(p);
      if (/^\d+[.)]\s+\S/.test(line)) current._steps = true;
      if (/\bfigure\s+\d+\b/i.test(line)) current.figure_count += 1;
      current._text += line + "\n";
      current.char_count += line.length;
      current.page_end = p;
    }

    // Embedded images via the operator list.
    try {
      const ops = await page.getOperatorList();
      for (let i = 0; i < ops.fnArray.length; i++) {
        const fn = ops.fnArray[i];
        if (fn !== pdfjsLib.OPS.paintImageXObject && fn !== pdfjsLib.OPS.paintJpegXObject) continue;
        const name = ops.argsArray[i][0];
        let img;
        try { img = page.objs.get(name); } catch { continue; }
        if (!img?.width || !img?.height) continue;
        const png = await imageToPng(img);
        if (!png) continue;
        // A page that is entirely image (a scanned or screenshot-only page) produces no
        // text lines, so nothing has opened a section yet — without this, the image's
        // section_id is null and it can never be placed by the step it illustrates.
        ensureRoot(p);
        if (current.page_start === null) current.page_start = p;
        current.page_end = p;
        const order = assets.length + 1;
        assets.push({
          asset_id: `${documentId}-img-${String(order).padStart(3, "0")}`,
          document_id: documentId, ext: "png", format: "png",
          width_px: img.width, height_px: img.height,
          aspect: Math.round((img.width / img.height) * 10000) / 10000,
          doc_order_index: order,
          section_id: current.section_id,
          nearest_heading: current.title,
          caption_candidate: null, alt_text: null, repeat_count: 1,
          role: Math.max(img.width, img.height) < 150 ? "icon" : "screenshot",
          quality: Math.max(img.width, img.height) < 400 ? ["low_res"] : [],
          bytes: png,
        });
      }
    } catch { /* an unreadable page's images are skipped, its text is still kept */ }
    page.cleanup();
  }

  const finished = sections.map((s) => {
    const { _text, _steps, ...rest } = s;
    return { ...rest, classifier: classify(s.title, _text, _steps), text: _text.trim() };
  });

  return {
    document: { document_id: documentId, filename, format: "pdf", page_count: doc.numPages },
    sections: finished,
    assets,
    assets_dropped: 0,
    notes: buildNotes(finished, assets, tocLinesSeen),
  };
}

function buildNotes(sections, assets, tocLinesSeen) {
  const notes = [];
  if (tocLinesSeen > 5) {
    notes.push(`Skipped ${tocLinesSeen} table-of-contents lines while reading the outline.`);
  }
  if (assets.length === 0) {
    notes.push(
      "No screenshots could be extracted from this PDF. PDFs often store screens as vector " +
        "drawings rather than embedded images, which cannot be lifted out. If you have the " +
        "original Word document, upload that instead — it gives much better screenshots."
    );
  }
  if (sections.length <= 1) {
    notes.push(
      "No clause-numbered headings were found, so the whole document is one section. " +
        "The generated outline will be coarse; a Word original parses far better."
    );
  }
  return notes;
}

/** Turn a pdf.js image object into PNG bytes via a canvas. */
async function imageToPng(img) {
  const { width, height } = img;
  const makeCanvas = () => {
    if (typeof OffscreenCanvas !== "undefined") return new OffscreenCanvas(width, height);
    if (typeof document !== "undefined") {
      const c = document.createElement("canvas");
      c.width = width; c.height = height;
      return c;
    }
    return null;
  };
  let canvas = makeCanvas();
  let nodeCanvasMod = null;
  if (!canvas) {
    // Neither browser canvas API exists — this is the Node test harness. `canvas` (the
    // node-canvas package) is a devDependency used only here, and is marked external in
    // build.js so it is never reachable from the bundle this function ships to the page.
    try {
      nodeCanvasMod = await import("canvas");
      canvas = nodeCanvasMod.createCanvas(width, height);
    } catch {
      return null; // canvas not installed — image extraction is skipped, not crashed
    }
  }

  const ctx = canvas.getContext("2d");
  const imageData = ctx.createImageData(width, height);
  const src = img.data;
  const dst = imageData.data;

  if (src.length === width * height * 4) {
    dst.set(src);
  } else if (src.length === width * height * 3) {
    for (let i = 0, j = 0; i < src.length; i += 3, j += 4) {
      dst[j] = src[i]; dst[j + 1] = src[i + 1]; dst[j + 2] = src[i + 2]; dst[j + 3] = 255;
    }
  } else if (src.length === width * height) {
    for (let i = 0, j = 0; i < src.length; i++, j += 4) {
      dst[j] = dst[j + 1] = dst[j + 2] = src[i]; dst[j + 3] = 255;
    }
  } else {
    return null;
  }
  ctx.putImageData(imageData, 0, 0);

  if (nodeCanvasMod) {
    // node-canvas: synchronous Buffer, no Blob API.
    return new Uint8Array(canvas.toBuffer("image/png"));
  }
  const blob = canvas.convertToBlob
    ? await canvas.convertToBlob({ type: "image/png" })
    : await new Promise((r) => canvas.toBlob(r, "image/png"));
  return new Uint8Array(await blob.arrayBuffer());
}
