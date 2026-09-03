"use strict";

/* =================================================================
   buildPptx — the one call the UI (and the test suite) actually
   makes: template bytes + a list of slide requests in, a finished
   .pptx ArrayBuffer out. Wires together profiling (ooxml-read.js),
   assembly (ooxml-write.js), and zipping (ooxml-zip.js).
   ================================================================= */

function loadDeps() {
  if (typeof module !== "undefined" && module.exports) {
    return {
      unzipAll: require("./ooxml-zip.js").unzipAll,
      zipPackage: require("./ooxml-zip.js").zipPackage,
      profileTemplate: require("./ooxml-read.js").profileTemplate,
      assemblePresentation: require("./ooxml-write.js").assemblePresentation,
    };
  }
  // Browser: these are plain globals from the inlined <script> tags.
  return { unzipAll, zipPackage, profileTemplate, assemblePresentation };
}

function findLayout(profile, layoutName) {
  const wanted = layoutName.toLowerCase();
  return profile.layouts.find(l => (l.name || "").toLowerCase() === wanted)
    || profile.layouts.find(l => l.part.toLowerCase().includes(wanted.replace(/\s+/g, "")));
}

/* templateArrayBuffer: the raw uploaded .potx/.pptx bytes.
   slideRequests: [{ layoutName, shapes: [{want, paragraphs}], notes? }]
   Returns { buffer, warnings, errors, profile }. `buffer` is null
   when errors is non-empty — never emit a file build_deck.py would
   have refused to validate. */
async function buildPptx(templateArrayBuffer, slideRequests) {
  const { unzipAll, zipPackage, profileTemplate, assemblePresentation } = loadDeps();

  const { entries } = await unzipAll(templateArrayBuffer);
  const profile = profileTemplate(entries, "template");

  if (!profile.layoutCount) {
    return {
      buffer: null, warnings: [], profile,
      errors: [{ slide: null, message: "This template has no slide layouts to build on." }],
    };
  }

  const errors = [];
  const slides = [];
  for (const [i, req] of slideRequests.entries()) {
    const layout = findLayout(profile, req.layoutName);
    if (!layout) {
      errors.push({
        slide: i + 1,
        message: `Slide ${i + 1}: no layout named "${req.layoutName}" in this template. `
          + `Available: ${profile.layouts.map(l => l.name).filter(Boolean).join(", ")}.`,
      });
      continue;
    }
    slides.push({
      layoutPart: layout.part,
      layoutPlaceholders: layout.placeholders,
      shapes: req.shapes,
      notes: req.notes,
    });
  }
  if (errors.length) return { buffer: null, warnings: [], errors, profile };

  const result = assemblePresentation(entries, slides);
  if (result.errors.length) {
    return { buffer: null, warnings: result.warnings, errors: result.errors, profile };
  }

  const order = [...result.entries.keys()];
  const buffer = await zipPackage(order.map(name => ({ name, data: result.entries.get(name) })));
  return { buffer, warnings: result.warnings, errors: [], profile };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { buildPptx, findLayout };
}
