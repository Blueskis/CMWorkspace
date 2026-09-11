import { parsePdf } from "../src/parse-pdf.js";
import { parsePptxSource } from "../src/parse-pptx-source.js";
import { readFileSync, existsSync } from "node:fs";
import { execFileSync } from "node:child_process";

console.log("### PDF: real tender chapter (text-heavy, TOC-heavy)");
const r1 = await parsePdf(readFileSync("../examples/cfs-ch8/inputs/CFS-Part2-Ch8-Change-Mgt-and-Training.pdf"), "cfs-ch8.pdf");
console.log(`  sections=${r1.sections.length} assets=${r1.assets.length} pages=${r1.document.page_count}`);
console.log(`  classifiers: ${JSON.stringify(r1.sections.reduce((a,s)=>{a[s.classifier]=(a[s.classifier]||0)+1;return a},{}))}`);
r1.sections.slice(0,6).forEach(s=>console.log(`    ${s.section_id.padEnd(22)} ${s.title.slice(0,58)}`));
r1.notes.forEach(n=>console.log("  NOTE:", n));

console.log("\n### PDF: image fixture");
const r2 = await parsePdf(readFileSync("test/fixtures/with-image.pdf"), "with-image.pdf");
console.log(`  sections=${r2.sections.length} assets=${r2.assets.length}`);
r2.notes.forEach(n=>console.log("  NOTE:", n));

console.log("\n### PPTX source");
if (!existsSync("test/fixtures/sample-source.pptx"))
  execFileSync("python3", ["../tests/fixtures/make_pptx_fixture.py","-o","test/fixtures/sample-source.pptx"]);
const r3 = await parsePptxSource(readFileSync("test/fixtures/sample-source.pptx"), "sample-source.pptx");
console.log(`  sections=${r3.sections.length} assets=${r3.assets.length}`);
r3.sections.forEach(s=>console.log(`    ${s.section_id.padEnd(26)} [${s.classifier}] ${s.title}`));
r3.assets.forEach(a=>console.log(`    asset ${a.asset_id} ${a.width_px}x${a.height_px} sec=${a.section_id} alt=${a.alt_text}`));

// verify extracted PNG bytes are real
console.log("\n### verify extracted image bytes");
const asset = r2.assets[0];
console.log("  bytes:", asset.bytes.length, "first bytes:", Array.from(asset.bytes.slice(0,8)));
const { writeFileSync } = await import("node:fs");
writeFileSync("test/out/extracted-from-pdf.png", asset.bytes);
