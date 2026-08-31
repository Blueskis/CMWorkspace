/**
 * Dispatch a source document to the right parser and merge several into one corpus.
 *
 * Multiple documents are supported for the same reason the Python pipeline supports them
 * (see reference/fsd-extraction.md): an FSD plus an addendum plus a glossary is a normal
 * intake. Each gets its own document_id so section ids stay unambiguous across them.
 */

import { parseDocx } from "./parse-docx.js";
import { parsePptxSource } from "./parse-pptx-source.js";
import { parsePdf } from "./parse-pdf.js";

export const SUPPORTED_SOURCE_EXTS = ["docx", "pptx", "pdf"];

export async function parseSource(file, { onProgress = null } = {}) {
  const name = file.name ?? "document";
  const ext = name.split(".").pop().toLowerCase();
  const bytes = new Uint8Array(await file.arrayBuffer());

  switch (ext) {
    case "docx":
      return parseDocx(bytes, name);
    case "pptx":
    case "potx":
      return parsePptxSource(bytes, name);
    case "pdf":
      return parsePdf(bytes, name, { onProgress });
    case "doc":
      throw new Error(
        `${name}: legacy .doc is not supported. Open it in Word and save as .docx.`
      );
    default:
      throw new Error(
        `${name}: unsupported file type ".${ext}". Upload a ${SUPPORTED_SOURCE_EXTS.join(", ")} file.`
      );
  }
}

/** Merge parsed documents into one corpus, keeping document_ids unique. */
export async function parseSources(files, { onProgress = null } = {}) {
  const documents = [];
  const sections = [];
  const assets = [];
  const notes = [];
  const seen = new Set();

  for (const file of files) {
    const parsed = await parseSource(file, { onProgress });

    // Disambiguate a repeated document_id (two files with the same stem).
    let id = parsed.document.document_id;
    if (seen.has(id)) {
      let n = 2;
      while (seen.has(`${id}-${n}`)) n++;
      const newId = `${id}-${n}`;
      const remap = (s) => s?.replace(new RegExp(`^${id}#`), `${newId}#`);
      parsed.sections.forEach((s) => { s.section_id = remap(s.section_id); s.document_id = newId; });
      parsed.assets.forEach((a) => {
        a.section_id = remap(a.section_id);
        a.asset_id = a.asset_id.replace(new RegExp(`^${id}-`), `${newId}-`);
        a.document_id = newId;
      });
      id = newId;
    }
    seen.add(id);

    documents.push({ ...parsed.document, document_id: id });
    sections.push(...parsed.sections);
    assets.push(...parsed.assets);
    (parsed.notes ?? []).forEach((n) => notes.push(`${parsed.document.filename}: ${n}`));
    if (parsed.assets_dropped) {
      notes.push(
        `${parsed.document.filename}: dropped ${parsed.assets_dropped} repeated or tiny image(s) as letterhead/icons.`
      );
    }
  }

  return { documents, sections, assets, notes };
}
