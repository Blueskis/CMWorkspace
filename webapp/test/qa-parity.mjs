import { audit, hardFail } from "../src/qa.js";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";

const brief = JSON.parse(readFileSync("../tests/fixtures/qa/training_brief.json"));
const planPass = JSON.parse(readFileSync("../tests/fixtures/qa/deck_plan_pass.json"));
const questions = JSON.parse(readFileSync("../tests/fixtures/qa/question_bank_pass.json"));

// Rebuild source_map/asset_index from the docx fixture, same as run_tests.py does
execFileSync("python3", ["../tests/fixtures/make_docx_fixture.py", "-o", "test/out/sample-fsd.docx"]);
execFileSync("python3", ["../skills/training-material-generator/scripts/map_source.py",
  "test/out/sample-fsd.docx", "-o", "test/out/source_map.json", "--run-id", "t"]);
execFileSync("python3", ["../skills/training-material-generator/scripts/extract_assets.py",
  "test/out/sample-fsd.docx", "--assets", "test/out/assets", "-o", "test/out/asset_index.json", "--run-id", "t"]);
const sourceMap = JSON.parse(readFileSync("test/out/source_map.json"));
const assetIndex = JSON.parse(readFileSync("test/out/asset_index.json"));

// deck_plan.json in Python uses "modules[].objective_ids" + "slides[].blocks[].sources" —
// same shape qa.js expects. But block.placeholder/kind key names differ slightly from
// what build-pptx.js uses (slot vs placeholder) — qa.js only reads sources/gap/kind/content,
// which are shape-compatible with the Python plan fixture directly.
const corpus = { sections: sourceMap.sections, assets: assetIndex.assets };

function run(label, brief_, plan_, questions_) {
  const r = audit(brief_, plan_, corpus, questions_);
  console.log(`${label}: hardFail=${hardFail(r)} loNoSlide=${JSON.stringify(r.loNoSlide)} loNoQuestion=${JSON.stringify(r.loNoQuestion)} missingProvenance=${JSON.stringify(r.missingProvenance)} uncoveredProcedures=${JSON.stringify(r.uncoveredProcedures)}`);
  return r;
}

run("clean plan", brief, planPass, questions);

// missing question for LO2
const q2 = { run_id: "t", questions: questions.questions.filter(q => q.objective_id !== "LO2") };
const r2 = run("missing Q for LO2", brief, planPass, q2);
if (!r2.loNoQuestion.includes("LO2")) { console.log("FAIL: expected LO2 in loNoQuestion"); process.exit(1); }

// block without sources/gap
const planNoProv = JSON.parse(JSON.stringify(planPass));
planNoProv.modules[1].slides[0].blocks[0].sources = [];
const r3 = run("no provenance", brief, planNoProv, questions);
if (!r3.missingProvenance.length) { console.log("FAIL: expected missingProvenance"); process.exit(1); }

// uncovered procedure section
const planUncov = JSON.parse(JSON.stringify(planPass));
for (const s of planUncov.modules[0].slides) for (const b of s.blocks) b.sources = ["sample-fsd#4"];
const r4 = run("uncovered procedure", brief, planUncov, questions);
if (!r4.uncoveredProcedures.includes("sample-fsd#4.2.1")) { console.log("FAIL: expected sample-fsd#4.2.1 uncovered"); process.exit(1); }

// out_of_scope clears it
const briefOOS = JSON.parse(JSON.stringify(brief));
briefOOS.out_of_scope = [{ section_id: "sample-fsd#4.2.1", reason: "covered elsewhere" }];
const r5 = run("out_of_scope clears", briefOOS, planUncov, questions);
if (r5.uncoveredProcedures.includes("sample-fsd#4.2.1")) { console.log("FAIL: expected cleared"); process.exit(1); }

console.log("\nAll qa.js parity checks passed.");
