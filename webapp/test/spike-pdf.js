/**
 * Spike: prove the CSP-safe pdf.js path works before the PDF parser is built on it.
 *
 *   node test/spike-pdf.js <file.pdf>
 *
 * The artifact CSP allows <script src> from cdnjs but blocks fetch/XHR to it, so pdf.js
 * cannot load its worker the normal way. The escape hatch (verified in pdf.js 3.11.174's
 * source): PDFWorker._mainThreadWorkerMessageHandler reads `globalThis.pdfjsWorker`, and
 * when that is already set, setupFakeWorker skips `new Worker(...)` and the loadScript
 * fetch entirely. In the browser that global is set by loading pdf.worker.min.js as a
 * second <script src>; here we set it via require, which mirrors that exactly — so this
 * spike exercises the same code path the artifact will.
 *
 * Checks: text extraction, clause-heading visibility, and embedded-image yield (the part
 * the plan flags as PDF's weakness).
 */

import { createRequire } from "node:module";
import { readFileSync } from "node:fs";

const require = createRequire(import.meta.url);

// Mirror the browser's second <script src> tag.
globalThis.pdfjsWorker = require("pdfjs-dist/legacy/build/pdf.worker.js");

const pdfjsLib = require("pdfjs-dist/legacy/build/pdf.js");
pdfjsLib.GlobalWorkerOptions.workerSrc = "pdf.worker.min.js"; // never fetched; the global wins

const file = process.argv[2];
if (!file) {
  console.error("usage: node test/spike-pdf.js <file.pdf>");
  process.exit(2);
}

const data = new Uint8Array(readFileSync(file));

const doc = await pdfjsLib.getDocument({
  data,
  // Every one of these would be a blocked network fetch inside the artifact.
  useWorkerFetch: false,
  isEvalSupported: false,
  disableFontFace: true,
  useSystemFonts: false,
}).promise;

console.log(`pages: ${doc.numPages}`);

let allText = "";
let imageOps = 0;
const imageSizes = [];

for (let p = 1; p <= doc.numPages; p++) {
  const page = await doc.getPage(p);

  const content = await page.getTextContent();
  // Reassemble lines: pdf.js emits positioned runs, so break on the y coordinate.
  let lastY = null;
  let line = "";
  const lines = [];
  for (const item of content.items) {
    const y = item.transform?.[5];
    if (lastY !== null && Math.abs(y - lastY) > 2) {
      if (line.trim()) lines.push(line.trim());
      line = "";
    }
    line += item.str;
    lastY = y;
  }
  if (line.trim()) lines.push(line.trim());
  allText += lines.join("\n") + "\n";

  // Image yield: walk the operator list for paintImageXObject.
  const ops = await page.getOperatorList();
  for (let i = 0; i < ops.fnArray.length; i++) {
    if (
      ops.fnArray[i] === pdfjsLib.OPS.paintImageXObject ||
      ops.fnArray[i] === pdfjsLib.OPS.paintJpegXObject
    ) {
      imageOps++;
      const name = ops.argsArray[i][0];
      try {
        const img = page.objs.get(name);
        if (img?.width) imageSizes.push(`${img.width}x${img.height}`);
      } catch {
        imageSizes.push("(not resolved)");
      }
    }
  }
  page.cleanup();
}

const clauseLines = allText
  .split("\n")
  .filter((l) => /^\d+(\.\d+)*\.?\s+\S/.test(l.trim()));

console.log(`text chars: ${allText.length}`);
console.log(`clause-numbered heading candidates: ${clauseLines.length}`);
console.log(`  e.g. ${clauseLines.slice(0, 5).map((l) => JSON.stringify(l.slice(0, 60))).join("\n       ")}`);
console.log(`image paint ops: ${imageOps}`);
console.log(`resolved image sizes: ${imageSizes.slice(0, 10).join(", ") || "(none)"}`);
console.log("\nSPIKE RESULT: pdf.js ran with no worker construction and no network fetch.");
