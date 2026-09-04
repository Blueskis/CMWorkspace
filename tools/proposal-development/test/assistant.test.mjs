import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { buildAssistantPrompt, parseAssistantReply, runAssistant, ASSISTANT_PROMPT_BUDGET_BYTES } = require("../src/assistant.js");

function fakeTriage(rows) {
  const sections = rows.map((r, i) => ({
    id: `sec-${i}`, ref: `${i + 1}`, heading: r.heading, body: r.heading, excerpt: r.heading,
    page: i + 1, verdict: r.verdict, score: 0, coverage: 0, strong: [], offTopic: 0, cues: [],
  }));
  return { sections, words: 100, crossRefs: [], counts: {} };
}

// Case 10: prompt with 3 clauses and an instruction -> contains every clause's
// id, heading, verdict, and the instruction.
test("case 10: prompt carries every clause and the instruction", () => {
  const t = fakeTriage([
    { heading: "Training Plan", verdict: "cm-core" },
    { heading: "Warranty", verdict: "not-cm" },
    { heading: "Orientation Programme", verdict: "not-cm" },
  ]);
  const prompt = buildAssistantPrompt({ triage: t, instruction: "The orientation programme is ours." });
  for (let i = 0; i < 3; i++) assert.ok(prompt.includes(`sec-${i}`), `missing sec-${i}`);
  assert.ok(prompt.includes("Training Plan"));
  assert.ok(prompt.includes("Warranty"));
  assert.ok(prompt.includes("Orientation Programme"));
  assert.ok(prompt.includes("cm-core"));
  assert.ok(prompt.includes("The orientation programme is ours."));
});

// Case 11: a 5-turn transcript -> recent turns present, oldest dropped
// first when the budget bites.
test("case 11: transcript is included, oldest turns dropped first under a tight budget", () => {
  const t = fakeTriage([{ heading: "Training Plan", verdict: "cm-core" }]);
  const transcript = [
    { role: "user", text: "TURN_ONE_OLDEST marker" },
    { role: "assistant", text: "TURN_TWO reply" },
    { role: "user", text: "TURN_THREE marker" },
    { role: "assistant", text: "TURN_FOUR reply" },
    { role: "user", text: "TURN_FIVE_NEWEST marker" },
  ];
  const roomy = buildAssistantPrompt({ triage: t, transcript, instruction: "go on" });
  assert.ok(roomy.includes("TURN_ONE_OLDEST"), "all turns fit under a generous budget");

  const tight = buildAssistantPrompt({ triage: t, transcript, instruction: "go on", budgetBytes: 900 });
  assert.ok(tight.includes("TURN_FIVE_NEWEST"), "the newest turn must survive a tight budget");
  assert.ok(!tight.includes("TURN_ONE_OLDEST"), "the oldest turn is dropped first");
});

// Case 12: a very large tender -> prompt stays under the 64 KiB sample() cap.
test("case 12: prompt stays under the 64 KiB cap for a large tender", () => {
  const rows = Array.from({ length: 300 }, (_, i) => ({
    heading: `Clause ${i} about a fairly specific and repeated change management topic`,
    verdict: "cm-core",
  }));
  const t = fakeTriage(rows);
  const prompt = buildAssistantPrompt({ triage: t, instruction: "check everything" });
  const bytes = new TextEncoder().encode(prompt).length;
  assert.ok(bytes <= 64 * 1024, `prompt is ${bytes} bytes`);
  assert.ok(bytes <= ASSISTANT_PROMPT_BUDGET_BYTES + 500);
});

// Case 13: valid JSON with a reply and two edits -> both parsed, reply preserved.
test("case 13: a valid reply with two edits parses cleanly", () => {
  const completion = JSON.stringify({
    reply: "Reclassified both as requested.",
    edits: [
      { op: "reclassify", sectionId: "sec-0", verdict: "cm-core" },
      { op: "rename", sectionId: "sec-1", heading: "New Heading" },
    ],
  });
  const { reply, edits } = parseAssistantReply(completion);
  assert.equal(reply, "Reclassified both as requested.");
  assert.equal(edits.length, 2);
});

// Case 14: fenced ```json -> parsed identically (shared with parseDraftJson).
test("case 14: a fenced json block parses the same as bare JSON", () => {
  const completion = "```json\n" + JSON.stringify({ reply: "Done.", edits: [] }) + "\n```";
  const { reply, edits } = parseAssistantReply(completion);
  assert.equal(reply, "Done.");
  assert.deepEqual(edits, []);
});

// Case 15: a reply with an empty edit list (a question, not a command).
test("case 15: a question-only reply has no edits", () => {
  const completion = JSON.stringify({ reply: "Clause 3.1.2(h) asks for a change intervention plan.", edits: [] });
  const { reply, edits } = parseAssistantReply(completion);
  assert.match(reply, /change intervention plan/);
  assert.deepEqual(edits, []);
});

// Case 16: prose instead of JSON -> one stricter retry, then a plain result; nothing applied.
test("case 16: unparseable prose retries once then degrades gracefully", async () => {
  let calls = 0;
  const sample = async () => { calls++; return { completion: "Sure, I reclassified it for you!" }; };
  const t = fakeTriage([{ heading: "A", verdict: "not-cm" }]);
  const result = await runAssistant({ triage: t, transcript: [], instruction: "fix it", sample });
  assert.equal(calls, 2, "expected exactly one retry");
  assert.equal(result.failed, true);
  assert.deepEqual(result.edits, []);
  assert.match(result.reply, /couldn't read/);
});

// Case 17: an edit citing a sectionId never in the digest -> caught by
// validateEdits downstream (triage-edit.js), not by parseAssistantReply
// itself — confirm the two modules compose correctly here.
test("case 17: a phantom sectionId from the model is dropped by validateEdits", () => {
  const { validateEdits } = require("../src/triage-edit.js");
  const t = fakeTriage([{ heading: "A", verdict: "not-cm" }]);
  const completion = JSON.stringify({
    reply: "Done.",
    edits: [{ op: "reclassify", sectionId: "sec-does-not-exist", verdict: "cm-core" }],
  });
  const { edits } = parseAssistantReply(completion);
  const { valid, errors } = validateEdits(t, edits);
  assert.equal(valid.length, 0);
  assert.equal(errors.length, 1);
  assert.match(errors[0].reason, /unknown section id/);
});

// Case 18: sample() rejects not_granted -> propagates so the caller can hide the box.
test("case 18: a not_granted rejection propagates rather than being swallowed", async () => {
  const t = fakeTriage([{ heading: "A", verdict: "not-cm" }]);
  const rejecting = async () => { const e = new Error("not granted"); e.code = "not_granted"; throw e; };
  await assert.rejects(
    () => runAssistant({ triage: t, transcript: [], instruction: "fix it", sample: rejecting }),
    err => err.code === "not_granted"
  );
});

// Case 19: sample() rejects rate_limited -> propagates, never auto-retried.
test("case 19: a rate_limited rejection is not retried internally", async () => {
  let calls = 0;
  const t = fakeTriage([{ heading: "A", verdict: "not-cm" }]);
  const rateLimited = async () => { calls++; const e = new Error("rate limited"); e.code = "rate_limited"; throw e; };
  await assert.rejects(() => runAssistant({ triage: t, transcript: [], instruction: "fix it", sample: rateLimited }));
  assert.equal(calls, 1, "must not auto-retry a rate_limited rejection");
});
