/**
 * Parse a .pptx used as a SOURCE document (not as the template) — one section per slide.
 *
 * Browser port of map_source.py's parse_pptx + extract_assets.py's pptx path. The thing
 * that differs from the .docx path, and the reason this is its own module: media is
 * resolved through each slide's OWN rels part rather than one document-wide rels, so an
 * image's owning slide is known directly.
 */

import { getJSZip, parseXml } from "./env.js";
import { attr, findAll, findFirst, parseRels, resolveTarget, textOf } from "./xml.js";
import { classify, imagePixelSize, slugify } from "./parse-docx.js";

export async function parsePptxSource(bytes, filename) {
  const JSZip = await getJSZip();
  const zip = await JSZip.loadAsync(bytes);
  const documentId = slugify(filename.replace(/\.[^.]+$/, ""));

  const slideNames = Object.keys(zip.files)
    .filter((n) => /^ppt\/slides\/slide\d+\.xml$/.test(n))
    .sort((a, b) => parseInt(a.match(/(\d+)\.xml$/)[1], 10) - parseInt(b.match(/(\d+)\.xml$/)[1], 10));

  if (slideNames.length === 0) {
    throw new Error(`${filename}: no slides found — is this a PowerPoint file?`);
  }

  const sections = [];
  const assets = [];

  for (let i = 0; i < slideNames.length; i++) {
    const part = slideNames[i];
    const n = i + 1;
    const doc = await parseXml(await zip.file(part).async("string"));

    let title = null;
    for (const sp of findAll(doc, "sp")) {
      const ph = findFirst(sp, "ph");
      if (ph && ["title", "ctrTitle"].includes(attr(ph, "type"))) {
        title = textOf(sp, "t").trim();
        break;
      }
    }
    title = title || `Slide ${n}`;
    const sectionId = `${documentId}#slide${n}`;

    let bodyText = textOf(doc, "t");
    if (title && bodyText.includes(title)) bodyText = bodyText.replace(title, "");
    bodyText = bodyText.trim();

    const pics = findAll(doc, "pic");
    const tables = findAll(doc, "tbl");

    sections.push({
      section_id: sectionId, document_id: documentId,
      section_path: title, title, level: 1, clause_number: `slide${n}`,
      page_start: n, page_end: n,
      char_count: bodyText.length,
      figure_count: pics.length, table_count: tables.length,
      classifier: classify(title, bodyText, false),
      text: bodyText,
    });

    // Media through this slide's own rels.
    const relsPart = `ppt/slides/_rels/slide${n}.xml.rels`;
    if (!zip.file(relsPart)) continue;
    const rels = parseRels(await parseXml(await zip.file(relsPart).async("string")));

    for (const pic of pics) {
      const blip = findFirst(pic, "blip");
      if (!blip) continue;
      const target = rels[attr(blip, "embed")]?.target;
      if (!target) continue;
      const mediaPart = resolveTarget(target, part);
      const f = zip.file(mediaPart);
      if (!f) continue;
      const b = await f.async("uint8array");
      const { w, h, fmt } = imagePixelSize(b);
      const cNvPr = findFirst(pic, "cNvPr");
      const order = assets.length + 1;
      assets.push({
        asset_id: `${documentId}-img-${String(order).padStart(3, "0")}`,
        document_id: documentId,
        ext: fmt === "jpeg" ? "jpg" : fmt === "other" ? (mediaPart.split(".").pop() || "bin") : fmt,
        format: fmt, width_px: w, height_px: h,
        aspect: w && h ? Math.round((w / h) * 10000) / 10000 : null,
        doc_order_index: order,
        section_id: sectionId, nearest_heading: title,
        caption_candidate: null,
        alt_text: cNvPr ? (attr(cNvPr, "descr") || attr(cNvPr, "name")) : null,
        repeat_count: 1,
        role: Math.max(w, h) > 0 && Math.max(w, h) < 150 ? "icon" : "screenshot",
        quality: Math.max(w, h) > 0 && Math.max(w, h) < 400 ? ["low_res"] : [],
        bytes: b,
      });
    }
  }

  return {
    document: { document_id: documentId, filename, format: "pptx", page_count: slideNames.length },
    sections, assets, assets_dropped: 0,
  };
}
