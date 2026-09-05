/**
 * Parity: the JS parser and the Python pipeline must agree on the same document.
 *
 *   node test/parity.mjs
 *
 * This is the guard against the one genuinely permanent hazard in shipping a browser port
 * alongside the Python original: the two drifting apart, so that a deck generated in the
 * page quietly differs from one generated in a Claude session. It runs map_source.py and
 * extract_assets.py over the same files the JS modules read, and compares the fields that
 * actually matter downstream — section ids (screenshot placement keys off them), titles,
 * classifiers (Stage 5 enforces coverage on 'procedure'), text, and the surviving assets
 * after noise filtering.
 */

import { execFileSync } from "node:child_process";
import { readFileSync, mkdtempSync, rmSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { parseDocx } from "../src/parse-docx.js";

const SCRIPTS = "../skills/training-material-generator/scripts";

function py(script, args) {
  return execFileSync("python3", [join(SCRIPTS, script), ...args], { encoding: "utf8", cwd: process.cwd() });
}

let failures = 0;
const check = (label, a, b) => {
  const ok = JSON.stringify(a) === JSON.stringify(b);
  if (!ok) {
    failures++;
    console.log(`  MISMATCH ${label}`);
    console.log(`    python: ${JSON.stringify(a).slice(0, 300)}`);
    console.log(`    js    : ${JSON.stringify(b).slice(0, 300)}`);
  } else {
    console.log(`  ok  ${label}`);
  }
};

const cases = [
  ["synthetic fixture", "../tests/fixtures/__built__/sample-fsd.docx", true],
  ["real FSD", "../training/supplier-block-unblock-20260829/inputs/FSD_MMWA014_Supplier_Block_Unblock.docx", false],
];

for (const [label, path, needsBuild] of cases) {
  const tmp = mkdtempSync(join(tmpdir(), "parity-"));
  try {
    let docx = path;
    if (needsBuild) {
      docx = join(tmp, "sample-fsd.docx");
      execFileSync("python3", ["../tests/fixtures/make_docx_fixture.py", "-o", docx], { encoding: "utf8" });
    }
    console.log(`\n### ${label}`);

    // --- python ---
    const smPath = join(tmp, "source_map.json");
    const aiPath = join(tmp, "asset_index.json");
    py("map_source.py", [docx, "-o", smPath, "--run-id", "parity"]);
    py("extract_assets.py", [docx, "--assets", join(tmp, "assets"), "-o", aiPath, "--run-id", "parity"]);
    const pySections = JSON.parse(readFileSync(smPath, "utf8")).sections;
    const pyAssets = JSON.parse(readFileSync(aiPath, "utf8")).assets;

    // --- js ---
    const js = await parseDocx(readFileSync(docx), docx.split("/").pop());

    check("section count", pySections.length, js.sections.length);
    check("section ids", pySections.map((s) => s.section_id), js.sections.map((s) => s.section_id));
    check("section titles", pySections.map((s) => s.title), js.sections.map((s) => s.title));
    check("section paths", pySections.map((s) => s.section_path), js.sections.map((s) => s.section_path));
    check("classifiers", pySections.map((s) => s.classifier), js.sections.map((s) => s.classifier));
    check("section text", pySections.map((s) => s.text), js.sections.map((s) => s.text));
    check("table counts", pySections.map((s) => s.table_count), js.sections.map((s) => s.table_count));

    check("asset ids", pyAssets.map((a) => a.asset_id), js.assets.map((a) => a.asset_id));
    check("asset sections", pyAssets.map((a) => a.section_id), js.assets.map((a) => a.section_id));
    check("asset captions", pyAssets.map((a) => a.caption_candidate), js.assets.map((a) => a.caption_candidate));
    check("asset sizes", pyAssets.map((a) => [a.width_px, a.height_px]), js.assets.map((a) => [a.width_px, a.height_px]));
    check("asset roles", pyAssets.map((a) => a.role), js.assets.map((a) => a.role));
    check("asset quality", pyAssets.map((a) => a.quality), js.assets.map((a) => a.quality));
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
}

console.log(failures ? `\n${failures} PARITY MISMATCH(ES)` : "\nJS and Python agree on every compared field.");
process.exit(failures ? 1 : 0);
