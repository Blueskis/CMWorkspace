import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { validateEdits, applyTriageEdits, sectionDigest } = require("../src/triage-edit.js");

function fakeTriage(rows) {
  const sections = rows.map((r, i) => ({
    id: `sec-${i}`, ref: `${i + 1}`, heading: r.heading, body: r.body || r.heading,
    excerpt: r.excerpt || r.heading, page: i + 1, verdict: r.verdict,
    score: 0, coverage: 0, strong: [], offTopic: 0, cues: [],
  }));
  const counts = sections.reduce((acc, s) => (acc[s.verdict] = (acc[s.verdict] || 0) + 1, acc),
    { "cm-core": 0, "cm-adjacent": 0, "not-cm": 0 });
  return { sections, words: 100, crossRefs: [], counts };
}

// Case 1: reclassify not-cm -> cm-core, counts recompute, nothing else touched.
test("case 1: reclassify updates verdict and counts, leaves other clauses alone", () => {
  const t = fakeTriage([
    { heading: "Warranty", verdict: "not-cm" },
    { heading: "Training Plan", verdict: "cm-core" },
  ]);
  const { triage, errors } = applyTriageEdits(t, [{ op: "reclassify", sectionId: "sec-0", verdict: "cm-core" }]);
  assert.deepEqual(errors, []);
  assert.equal(triage.sections[0].verdict, "cm-core");
  assert.equal(triage.sections[1].verdict, "cm-core");
  assert.deepEqual(triage.counts, { "cm-core": 2, "cm-adjacent": 0, "not-cm": 0 });
});

// Case 2: reclassify stamps an edited marker naming previous verdict + source.
test("case 2: reclassify stamps an edited marker with previous verdict and source", () => {
  const t = fakeTriage([{ heading: "Warranty", verdict: "not-cm" }]);
  const { triage } = applyTriageEdits(t, [{ op: "reclassify", sectionId: "sec-0", verdict: "cm-core" }], "user");
  assert.deepEqual(triage.sections[0].edited, { field: "verdict", from: "not-cm", source: "user" });
});

// Case 3: rename changes heading only, body/excerpt untouched.
test("case 3: rename changes only the heading, not the evidence", () => {
  const t = fakeTriage([{ heading: "Old Heading", excerpt: "the original excerpt text", verdict: "cm-core" }]);
  const { triage } = applyTriageEdits(t, [{ op: "rename", sectionId: "sec-0", heading: "New Heading" }]);
  assert.equal(triage.sections[0].heading, "New Heading");
  assert.equal(triage.sections[0].excerpt, "the original excerpt text");
  assert.equal(triage.sections[0].body, "Old Heading");
});

// Case 4: add a manual clause -> appears with manual:true, included in counts.
test("case 4: add appends a manual clause and it counts", () => {
  const t = fakeTriage([{ heading: "Existing", verdict: "cm-core" }]);
  const { triage, errors } = applyTriageEdits(t, [
    { op: "add", heading: "Orientation Programme", verdict: "cm-core", excerpt: "clause 6 text" },
  ]);
  assert.deepEqual(errors, []);
  assert.equal(triage.sections.length, 2);
  const added = triage.sections[1];
  assert.equal(added.manual, true);
  assert.equal(added.heading, "Orientation Programme");
  assert.equal(added.verdict, "cm-core");
  assert.equal(triage.counts["cm-core"], 2);
});

// Case 5: remove a manual clause deletes it; remove a parsed clause demotes it instead.
test("case 5: remove deletes a manual clause but only demotes a parsed one", () => {
  const t = fakeTriage([{ heading: "Parsed Clause", verdict: "cm-core" }]);
  const withManual = applyTriageEdits(t, [
    { op: "add", heading: "Manual Clause", verdict: "cm-core" },
  ]).triage;

  const afterRemoveManual = applyTriageEdits(withManual, [
    { op: "remove", sectionId: withManual.sections[1].id },
  ]).triage;
  assert.equal(afterRemoveManual.sections.length, 1);
  assert.equal(afterRemoveManual.sections[0].heading, "Parsed Clause");

  const afterRemoveParsed = applyTriageEdits(t, [{ op: "remove", sectionId: "sec-0" }]).triage;
  assert.equal(afterRemoveParsed.sections.length, 1, "the parsed clause is not deleted");
  assert.equal(afterRemoveParsed.sections[0].verdict, "not-cm", "it is demoted instead");
  assert.equal(afterRemoveParsed.sections[0].body, "Parsed Clause", "its body is intact");
});

// Case 6: an edit naming an unknown sectionId is rejected; other edits in the batch survive.
test("case 6: an unknown sectionId is rejected without losing the rest of the batch", () => {
  const t = fakeTriage([{ heading: "A", verdict: "not-cm" }]);
  const { triage, errors } = applyTriageEdits(t, [
    { op: "reclassify", sectionId: "sec-99", verdict: "cm-core" },
    { op: "reclassify", sectionId: "sec-0", verdict: "cm-core" },
  ]);
  assert.equal(errors.length, 1);
  assert.match(errors[0].reason, /unknown section id/);
  assert.equal(triage.sections[0].verdict, "cm-core");
});

// Case 7: an invalid verdict is rejected the same way.
test("case 7: an invalid verdict is rejected", () => {
  const t = fakeTriage([{ heading: "A", verdict: "not-cm" }]);
  const { triage, errors } = applyTriageEdits(t, [
    { op: "reclassify", sectionId: "sec-0", verdict: "extremely-relevant" },
  ]);
  assert.equal(errors.length, 1);
  assert.match(errors[0].reason, /unknown verdict/);
  assert.equal(triage.sections[0].verdict, "not-cm", "the invalid edit did not apply");
});

// Case 8: a mixed batch applies the valid edits and reports the invalid ones; triage never half-written.
test("case 8: a mixed batch applies valid edits and reports invalid ones", () => {
  const t = fakeTriage([
    { heading: "A", verdict: "not-cm" },
    { heading: "B", verdict: "not-cm" },
  ]);
  const { triage, errors } = applyTriageEdits(t, [
    { op: "reclassify", sectionId: "sec-0", verdict: "cm-core" },
    { op: "reclassify", sectionId: "sec-1", verdict: "bogus" },
    { op: "rename", sectionId: "sec-missing", heading: "X" },
  ]);
  assert.equal(errors.length, 2);
  assert.equal(triage.sections[0].verdict, "cm-core");
  assert.equal(triage.sections[1].verdict, "not-cm");
  assert.equal(triage.sections.length, 2, "no section was dropped by a bad edit");
});

// Case 9: sectionDigest over many clauses under a tight budget stays under budget
// and reports how many it left out.
test("case 9: sectionDigest respects its byte budget and reports omissions", () => {
  const rows = Array.from({ length: 40 }, (_, i) => ({
    heading: `Clause about a fairly specific change management topic number ${i}`,
    excerpt: "Some excerpt text that repeats to pad out the length of this clause a fair bit more.",
    verdict: "cm-core",
  }));
  const t = fakeTriage(rows);
  const budget = 1500;
  const digest = sectionDigest(t, budget);
  const bytes = new TextEncoder().encode(digest).length;
  assert.ok(bytes <= budget + 200, `digest is ${bytes} bytes against a ${budget} budget (small overrun allowed for the omission line)`);
  assert.match(digest, /more clause\(s\) not listed/);
});
