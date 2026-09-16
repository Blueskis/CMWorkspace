#!/usr/bin/env node
/**
 * Rasterise every page of a PDF to a PNG — the pdf.js-based replacement for `pdftoppm`
 * (poppler), which is not installed in this project's dev/CI containers and is not a
 * dependency this repo wants to add just for visual QA and the vision pass. pdf.js is
 * already a webapp/lib-deck dependency (parse-pdf.js uses it for text/image extraction),
 * so this reuses the same library rather than introducing a second PDF stack.
 *
 *     node lib/deck/cli/rasterise.mjs deck.pdf -o slides/
 *     node lib/deck/cli/rasterise.mjs source.pdf -o vision/pages/ --prefix page --scale 2
 *
 * Writes <prefix>-1.png, <prefix>-2.png, ... in page order — same numbering convention
 * the pptx skill's own pdftoppm-based flow uses, so a caller (or a human) can swap this
 * in without renaming anything downstream. Node only (no browser Canvas needed): uses
 * pdf.js's own NodeCanvasFactory-equivalent via the `canvas` package, which is already a
 * webapp dependency for exactly this Node-side rasterisation path.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { getPdfJs } from "../env.js";

async function main() {
  const args = process.argv.slice(2);
  const input = args[0];
  if (!input || input.startsWith("-")) {
    console.error("usage: rasterise.mjs <input.pdf> -o <out-dir> [--prefix name] [--scale 2]");
    process.exit(1);
  }
  const outIdx = args.indexOf("-o");
  const outDir = outIdx >= 0 ? args[outIdx + 1] : "rasterised";
  const prefixIdx = args.indexOf("--prefix");
  const prefix = prefixIdx >= 0 ? args[prefixIdx + 1] : "page";
  const scaleIdx = args.indexOf("--scale");
  const scale = scaleIdx >= 0 ? parseFloat(args[scaleIdx + 1]) : 2.0;

  const { readFileSync } = await import("node:fs");
  const { createCanvas } = await import("canvas");

  const pdfjsLib = await getPdfJs();
  const data = new Uint8Array(readFileSync(input));
  const doc = await pdfjsLib.getDocument({ data }).promise;

  mkdirSync(outDir, { recursive: true });
  const written = [];
  for (let i = 1; i <= doc.numPages; i++) {
    const page = await doc.getPage(i);
    const viewport = page.getViewport({ scale });
    const canvas = createCanvas(Math.ceil(viewport.width), Math.ceil(viewport.height));
    const ctx = canvas.getContext("2d");
    await page.render({ canvasContext: ctx, viewport }).promise;
    const outPath = join(outDir, `${prefix}-${i}.png`);
    writeFileSync(outPath, canvas.toBuffer("image/png"));
    written.push(outPath);
  }
  for (const p of written) console.log(p);
  return written;
}

main().catch((err) => {
  console.error(err.message ?? err);
  process.exit(1);
});
