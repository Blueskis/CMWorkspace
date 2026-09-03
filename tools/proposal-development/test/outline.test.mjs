import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { buildOutline, reconcileCoverage } = require("../src/outline.js");

function fakeTriage(headings) {
  return {
    sections: headings.map(([heading, verdict]) => ({ heading, verdict, excerpt: "", page: 1 })),
  };
}

// Test case 14: 6 cm-core clauses, 12-slide limit -> <=12 slides, all 6 mapped,
// tender's own order, headings verbatim.
test("case 14: builds an outline within budget, covering every clause in order", () => {
  const headings = [
    "Change Management Strategy and Approach",
    "Change Management Team Structure",
    "Detailed Stakeholder Engagement Plan",
    "Change Impact Assessment",
    "Comprehensive Communications Plan",
    "User Training Plan and Materials",
  ];
  const triage = fakeTriage(headings.map(h => [h, "cm-core"]));
  const { slides, limit, clauseCount, cutForLength } = buildOutline(triage, { slideLimit: 12 });

  assert.equal(clauseCount, 6);
  assert.equal(limit, 12);
  assert.ok(slides.length <= 12, `expected <=12 slides, got ${slides.length}`);

  const clauseSlides = slides.filter(s => s.kind === "clause");
  assert.equal(clauseSlides.length, 6, "every clause must be mapped");
  assert.deepEqual(clauseSlides.map(s => s.title), headings, "tender's own order and exact wording");
  assert.ok(cutForLength.length > 0, "13 candidate slides over a 12 limit should cut something");
});

// Test case 15: a cm-core clause with no slide covering it -> reported
// uncovered, a [GAP] slide added, and the deck is still exportable.
test("case 15: an uncovered clause is reported and gets a visible [GAP] slide", () => {
  const triage = fakeTriage([
    ["Change Management Strategy and Approach", "cm-core"],
    ["Change Agent Identification and Training", "cm-core"],
  ]);
  const { slides } = buildOutline(triage, {});
  // Simulate a hand-edited plan that dropped the second clause's slide.
  const edited = slides.filter(s => !(s.kind === "clause" && s.clauseIndex === 1));

  const result = reconcileCoverage(triage, edited);
  assert.equal(result.uncovered.length, 1);
  assert.equal(result.uncovered[0].heading, "Change Agent Identification and Training");

  const gap = result.slides.find(s => s.kind === "gap");
  assert.ok(gap, "expected a [GAP] slide to be appended");
  assert.match(gap.title, /^\[GAP\]/);
  assert.match(gap.gapNote, /Change Agent Identification and Training/);
  // Export must still be possible — reconcileCoverage never throws or
  // marks the whole run as failed, only reports and patches the slide list.
  assert.ok(Array.isArray(result.slides));
});

// Test case 16: no cm-core clauses at all -> framing-only outline, stated
// plainly, nothing fabricated.
test("case 16: no cm-core clauses produces a framing-only outline", () => {
  const triage = fakeTriage([
    ["Warranty and Indemnity", "not-cm"],
    ["Bandwidth Requirements", "not-cm"],
  ]);
  const { slides, noClauses, clauseCount } = buildOutline(triage, {});
  assert.equal(noClauses, true);
  assert.equal(clauseCount, 0);
  assert.ok(slides.every(s => s.kind === "framing"));
  assert.ok(slides.length > 0);
});
