/**
 * Unit tests for qa.js's annotation-integrity check (report section 8) — port of
 * qa_training.py's own check 6. In-memory plan variants, same style as qa-parity.mjs's
 * mutation scenarios.
 *
 *   node test/qa-annotation.mjs
 */
import { audit, hardFail, renderReport } from "../src/qa.js";

let failures = 0;
function check(label, cond, detail = "") {
  if (cond) console.log(`  ok  ${label}`);
  else { failures++; console.log(`  FAIL ${label} ${detail}`); }
}

const brief = { learning_objectives: [{ lo_id: "LO1", text: "Approve a request" }] };
const corpusFor = (extraAssets = []) => ({
  sections: [{ section_id: "s1", section_path: "4.2", classifier: "procedure" }],
  assets: [
    { asset_id: "img1", role: "screenshot" },
    { asset_id: "img1-r1", role: "screenshot", redacted_from: "img1" },
    ...extraAssets,
  ],
});

function planFor(annotations, { nBullets = 3, assetId = "img1", skipped = [] } = {}) {
  return {
    modules: [{
      module_id: "m1", objective_ids: ["LO1"],
      slides: [{
        slide_id: "s1",
        blocks: [
          { kind: "bullets", content: Array.from({ length: nBullets }, (_, i) => `Step ${i + 1}`), sources: ["s1"] },
          { kind: "image", content: { asset_id: assetId, annotations, skipped }, sources: ["s1"] },
        ],
      }],
    }],
  };
}

// 1. clean callout binding {1..3} against 3 bullets
{
  const plan = planFor([
    { type: "callout", point: [0.5, 0.1], step: 1 },
    { type: "callout", point: [0.5, 0.2], step: 2 },
    { type: "callout", point: [0.5, 0.3], step: 3 },
  ]);
  const r = audit(brief, plan, corpusFor(), null);
  check("clean binding: no binding errors", r.annotationBindingErrors.length === 0);
  check("clean binding: hardFail() is false", hardFail(r) === false);
}

// 2. gap in step numbers -> hard fail
{
  const plan = planFor([
    { type: "callout", point: [0.5, 0.1], step: 1 },
    { type: "callout", point: [0.5, 0.3], step: 3 },
  ]);
  const r = audit(brief, plan, corpusFor(), null);
  check("gap [1,3] vs 3 bullets: binding error recorded", r.annotationBindingErrors.length === 1);
  check("gap [1,3] vs 3 bullets: hardFail() is true", hardFail(r) === true);
}

// 3. out-of-range coordinate -> hard fail
{
  const plan = planFor([{ type: "callout", point: [1.9, 0.2], step: 1 }], { nBullets: 1 });
  const r = audit(brief, plan, corpusFor(), null);
  check("out-of-bounds coordinate: geometry error recorded", r.annotationGeometryErrors.length === 1);
  check("out-of-bounds coordinate: hardFail() is true", hardFail(r) === true);
}

// 4. redact without redacted_from -> hard fail
{
  const plan = planFor([{ type: "redact", rect: [0.1, 0.1, 0.1, 0.1], reason: "vendor" }], { nBullets: 1, assetId: "img1" });
  const r = audit(brief, plan, corpusFor(), null);
  check("un-flattened redact: recorded as hard failure", r.annotationRedactUnflattened.length === 1);
  check("un-flattened redact: hardFail() is true", hardFail(r) === true);
}

// 5. redact WITH redacted_from -> clean
{
  const plan = planFor([{ type: "redact", rect: [0.1, 0.1, 0.1, 0.1], reason: "vendor" }], { nBullets: 1, assetId: "img1-r1" });
  const r = audit(brief, plan, corpusFor(), null);
  check("flattened redact: no redact errors", r.annotationRedactUnflattened.length === 0);
  check("flattened redact: hardFail() is false", hardFail(r) === false);
}

// 6. density — report only, never a hard failure
{
  const dense = Array.from({ length: 8 }, (_, i) => ({ type: "highlight", rect: [0.01 * i, 0.01, 0.02, 0.02] }));
  const plan = planFor(dense, { nBullets: 1 });
  const r = audit(brief, plan, corpusFor(), null);
  check("8 annotations on one screenshot: density reported", r.annotationDensityReport.length === 1);
  check("8 annotations on one screenshot: still not a hard failure", hardFail(r) === false);
}

// 7. skipped targets surface in the report, never fail the build
{
  const plan = planFor([], { nBullets: 3, skipped: [{ step: 2, reason: "crowded toolbar" }] });
  const r = audit(brief, plan, corpusFor(), null);
  check("skipped target recorded", r.annotationSkipped.length === 1);
  check("skipped target: not a hard failure", hardFail(r) === false);
  const report = renderReport(r, "test-run");
  check("report includes the 'could not confidently annotate' section",
    report.includes("Screenshots Claude could not confidently annotate"));
  check("report names the reason", report.includes("crowded toolbar"));
}

console.log(failures ? `\n${failures} FAILURE(S)` : "\nAll qa.js annotation-integrity checks passed.");
process.exit(failures ? 1 : 0);
