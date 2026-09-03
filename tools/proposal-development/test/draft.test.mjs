import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { buildSectionPrompt, enforceProvenance, draftSection, PROMPT_BUDGET_BYTES } = require("../src/draft.js");

const SECTION = { id: "clause-0", title: "Training strategy", clauseExcerpt: "The Tenderer shall provide a training strategy." };
const LAYOUT_PH = [{ type: "body", idx: "1", name: "Content Placeholder 2" }];
const EXCERPTS = [
  { deck: "Deck A", slideNo: 2, text: "Our training strategy covers needs analysis and curriculum design." },
];

// Test case 20: valid JSON with sources -> blocks accepted, chips render (data present).
test("case 20: a valid response with real sources is accepted as-is", () => {
  const blocks = [
    { kind: "bullets", items: [{ text: "Needs analysis", level: 0 }], sources: ["S1"] },
  ];
  const result = enforceProvenance(blocks, ["S1"], SECTION.title);
  assert.equal(result.length, 1);
  assert.equal(result[0].gap, false);
  assert.deepEqual(result[0].sources, ["S1"]);
});

// Test case 21: a block with neither sources nor gap -> rewritten to [GAP]
// naming the clause.
test("case 21: an unattributed block is rewritten into a gap naming the clause", () => {
  const blocks = [{ kind: "paragraph", text: "We will deliver excellent training." }]; // no sources, no gap
  const result = enforceProvenance(blocks, ["S1"], SECTION.title);
  assert.equal(result[0].gap, true);
  assert.deepEqual(result[0].sources, []);
  assert.match(result[0].gap_note, /Training strategy/);
});

// Test case 22: a block citing a source ID never supplied -> same treatment as 21.
test("case 22: a block citing a phantom source is treated as unattributed", () => {
  const blocks = [{ kind: "paragraph", text: "Per S9, we will exceed all targets.", sources: ["S9"] }];
  const result = enforceProvenance(blocks, ["S1"], SECTION.title);
  assert.equal(result[0].gap, true);
  assert.deepEqual(result[0].sources, []);
});

// Test case 23: prose instead of JSON -> one stricter retry; still bad ->
// section [GAP], other sections unaffected.
test("case 23: unparseable output retries once, then degrades to a gap block", async () => {
  let calls = 0;
  const fakeSample = async () => {
    calls++;
    return { completion: "Sure! Here is a training strategy: we will do great things." };
  };
  const result = await draftSection(SECTION, LAYOUT_PH, EXCERPTS, fakeSample);
  assert.equal(calls, 2, "expected exactly one retry after the first parse failure");
  assert.equal(result.failed, true);
  assert.equal(result.blocks.length, 1);
  assert.equal(result.blocks[0].gap, true);
  assert.match(result.blocks[0].gap_note, /Training strategy/);
});

test("case 23b: a section that fails does not affect a second, independent call", async () => {
  const badSample = async () => ({ completion: "not json at all" });
  const goodSample = async () => ({
    completion: JSON.stringify({ blocks: [{ kind: "paragraph", text: "Fine.", sources: ["S1"] }] }),
  });
  const bad = await draftSection(SECTION, LAYOUT_PH, EXCERPTS, badSample);
  const good = await draftSection(SECTION, LAYOUT_PH, EXCERPTS, goodSample);
  assert.equal(bad.failed, true);
  assert.equal(good.failed, false);
  assert.equal(good.blocks[0].gap, false);
});

// Test case 24: sample() rejects not_granted -> drafting hidden; outline,
// editing and export still work end to end (this module's contract: the
// rejection propagates so the caller can branch on it, rather than being
// swallowed here).
test("case 24: a not_granted rejection propagates to the caller rather than being swallowed", async () => {
  const rejecting = async () => {
    const err = new Error("not granted");
    err.code = "not_granted";
    throw err;
  };
  await assert.rejects(
    () => draftSection(SECTION, LAYOUT_PH, EXCERPTS, rejecting),
    err => err.code === "not_granted"
  );
});

// Test case 25: rate_limited mid-run -> propagates so the caller can stop
// and keep completed sections, rather than being retried internally.
test("case 25: a rate_limited rejection is not retried internally", async () => {
  let calls = 0;
  const rateLimited = async () => {
    calls++;
    const err = new Error("rate limited");
    err.code = "rate_limited";
    throw err;
  };
  await assert.rejects(() => draftSection(SECTION, LAYOUT_PH, EXCERPTS, rateLimited));
  assert.equal(calls, 1, "must not auto-retry a rate_limited rejection");
});

test("prompt stays within the 64 KiB sample() cap, even with huge excerpts", () => {
  const hugeExcerpts = Array.from({ length: 5 }, (_, i) => ({
    deck: `Deck ${i}`, slideNo: 1, text: "training strategy content ".repeat(3000),
  }));
  const prompt = buildSectionPrompt(SECTION, LAYOUT_PH, hugeExcerpts);
  const bytes = new TextEncoder().encode(prompt).length;
  assert.ok(bytes <= PROMPT_BUDGET_BYTES, `prompt is ${bytes} bytes, budget is ${PROMPT_BUDGET_BYTES}`);
});
