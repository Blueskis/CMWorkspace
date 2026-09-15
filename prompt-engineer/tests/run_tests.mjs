#!/usr/bin/env node
// Runs the full test suite against every copy of the PE logic in this repo:
// the LOGIC block inside prompt-engineer.html (the claude.ai artifact) and
// the standalone webapp/public/pe-logic.js (the self-hosted version). They
// must stay behaviorally identical, so one suite runs against both sources
// and fails loudly the moment they drift apart.
//
// Node stdlib only. Run with: node prompt-engineer/tests/run_tests.mjs

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import vm from "node:vm";
import assert from "node:assert/strict";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function loadFromHtml(relPath) {
  const htmlPath = path.join(__dirname, "..", relPath);
  const html = readFileSync(htmlPath, "utf8");
  const START = "// ===== LOGIC START =====";
  const END = "// ===== LOGIC END =====";
  const startIdx = html.indexOf(START);
  const endIdx = html.indexOf(END);
  if (startIdx === -1 || endIdx === -1 || endIdx <= startIdx) {
    throw new Error(`Could not find LOGIC START/END markers in ${relPath}`);
  }
  return html.slice(startIdx, endIdx);
}

function loadFromJs(relPath) {
  return readFileSync(path.join(__dirname, "..", relPath), "utf8");
}

const SOURCES = [
  { label: "prompt-engineer.html (artifact)", code: loadFromHtml("prompt-engineer.html") },
  { label: "webapp/public/pe-logic.js (self-hosted)", code: loadFromJs("webapp/public/pe-logic.js") },
];

const BLOCK_ORDER = [
  "Role",
  "Task",
  "Context",
  "Inputs",
  "Method",
  "Output format",
  "Constraints",
  "Success criteria",
];

function answerAll(PE, archetypeId, value = (id) => `answer for ${id}`) {
  const qs = PE.getQuestions(archetypeId);
  const answers = {};
  for (const q of qs) answers[q.id] = value(q.id);
  return { qs, answers };
}

function skipAll(PE, archetypeId) {
  const qs = PE.getQuestions(archetypeId);
  const answers = {};
  for (const q of qs) answers[q.id] = "";
  return { qs, answers };
}

function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// Returns the text of one block ("Heading:\n<content>" up to the next blank
// line or end of string), or null if the heading is not present at all.
function getBlockContent(prompt, heading) {
  const re = new RegExp(escapeRegex(heading) + ":\\n([\\s\\S]*?)(?:\\n\\n|$)");
  const m = prompt.match(re);
  return m ? m[1] : null;
}

// Registers and runs the full suite against one loaded `PE` object.
function runSuite(PE, test) {
  // ---------- Classification ----------

  test("1. write archetype from a comms email brief", () => {
    const r = PE.classify("Write a comms email to staff about a system go-live");
    assert.equal(r.archetype, "write");
  });

  test("2. summarize archetype from an extraction brief", () => {
    const r = PE.classify("Pull the key risks out of this 40-page report");
    assert.equal(r.archetype, "summarize");
  });

  test("3. analyze archetype from a decision brief", () => {
    const r = PE.classify("Should we run the pilot in one department or three?");
    assert.equal(r.archetype, "analyze");
  });

  test("4. code archetype from a bug-fix brief", () => {
    const r = PE.classify("Fix this Python script that keeps timing out");
    assert.equal(r.archetype, "code");
  });

  test("5. teach archetype from an explain brief", () => {
    const r = PE.classify("Explain what an API is to a non-technical audience");
    assert.equal(r.archetype, "teach");
  });

  test("6. fallback to write on no keyword match, no crash", () => {
    const r = PE.classify("asdfgh");
    assert.equal(r.archetype, "write");
  });

  test('7. empty brief ("") returns an error state, not an archetype', () => {
    const r = PE.classify("");
    assert.ok(r.error, "expected an error field");
    assert.equal(r.archetype, undefined);
  });

  test("7b. whitespace-only brief also returns an error state", () => {
    const r = PE.classify("   \n\t  ");
    assert.ok(r.error, "expected an error field");
    assert.equal(r.archetype, undefined);
  });

  // ---------- Question selection ----------

  test("8. every archetype returns 6-9 questions, no duplicate ids", () => {
    assert.ok(Array.isArray(PE.ARCHETYPES) && PE.ARCHETYPES.length === 8);
    for (const a of PE.ARCHETYPES) {
      const qs = PE.getQuestions(a.id);
      assert.ok(
        qs.length >= 6 && qs.length <= 9,
        `${a.id} has ${qs.length} questions, expected 6-9`,
      );
      const ids = qs.map((q) => q.id);
      assert.equal(new Set(ids).size, ids.length, `${a.id} has duplicate question ids`);
    }
  });

  test("9. archetype-specific questions differ between code and write", () => {
    const codeIds = new Set(PE.getQuestions("code").map((q) => q.id));
    const writeIds = new Set(PE.getQuestions("write").map((q) => q.id));
    const onlyInCode = [...codeIds].some((id) => !writeIds.has(id));
    const onlyInWrite = [...writeIds].some((id) => !codeIds.has(id));
    assert.ok(onlyInCode && onlyInWrite);
  });

  test("10. every question carries a non-empty default assumption string", () => {
    for (const a of PE.ARCHETYPES) {
      for (const q of PE.getQuestions(a.id)) {
        assert.equal(typeof q.default, "string");
        assert.ok(q.default.trim().length > 0, `${a.id}/${q.id} has an empty default`);
      }
    }
  });

  // ---------- Prompt assembly ----------

  test("11. all questions answered -> all eight blocks present, in fixed order", () => {
    // Use "code", which has a Method-tagged question, so every block can be populated.
    const brief = "Fix this Python script that keeps timing out";
    const { answers } = answerAll(PE, "code");
    const prompt = PE.assemble({ archetypeId: "code", brief, answers });
    let lastIndex = -1;
    for (const heading of BLOCK_ORDER) {
      const idx = prompt.indexOf(heading + ":");
      assert.ok(idx !== -1, `missing heading: ${heading}`);
      assert.ok(idx > lastIndex, `heading out of order: ${heading}`);
      lastIndex = idx;
      const content = getBlockContent(prompt, heading);
      assert.ok(content !== null, `could not parse content for heading: ${heading}`);
      assert.ok(content.trim().length > 0, `empty content for heading: ${heading}`);
    }
  });

  test("12. all optional questions skipped -> valid prompt, defaults substituted, no empty headings", () => {
    const brief = "Write a comms email to staff about a system go-live";
    const { answers } = skipAll(PE, "write");
    const prompt = PE.assemble({ archetypeId: "write", brief, answers });
    assert.ok(prompt.length > 0);
    for (const heading of ["Role", "Context", "Output format", "Constraints", "Success criteria"]) {
      const content = getBlockContent(prompt, heading);
      assert.ok(content !== null, `missing always-shown heading: ${heading}`);
      assert.ok(content.trim().length > 0, `heading ${heading} has empty content`);
    }
    // Any heading that does appear at all must have non-empty content beneath it.
    for (const heading of BLOCK_ORDER) {
      if (prompt.includes(heading + ":")) {
        const content = getBlockContent(prompt, heading);
        assert.ok(content !== null && content.trim().length > 0, `empty heading found: ${heading}`);
      }
    }
  });

  test("13. a skipped question's block is omitted rather than rendered blank", () => {
    const brief = "Fix this Python script that keeps timing out";
    const { answers } = answerAll(PE, "code");
    answers.inputs = ""; // skip the only question feeding Inputs
    answers.code_testing = ""; // skip the only question feeding Method for code
    const prompt = PE.assemble({ archetypeId: "code", brief, answers });
    assert.ok(!prompt.includes("Inputs:"), "Inputs heading should be omitted");
    assert.ok(!prompt.includes("Method:"), "Method heading should be omitted");
    // Other blocks that were answered still show up
    assert.ok(prompt.includes("Role:"));
    assert.ok(prompt.includes("Constraints:"));
  });

  test("14. markdown and backticks in answers appear literally", () => {
    const brief = "Write a comms email to staff about a system go-live";
    const { answers } = answerAll(PE, "write");
    const tricky = "Use **bold** and `code` spans, and a\nnewline";
    answers.must_avoid = tricky;
    const prompt = PE.assemble({ archetypeId: "write", brief, answers });
    assert.ok(prompt.includes(tricky), "tricky answer text was altered");
  });

  test("15. a 5000-character brief is never truncated in the Task block", () => {
    const sentence = "This is one sentence in a very long brief about a rollout plan. ";
    let brief = "";
    while (brief.length < 5000) brief += sentence;
    brief = brief.slice(0, 5000);
    const { answers } = skipAll(PE, "write");
    const prompt = PE.assemble({ archetypeId: "write", brief, answers });
    // Only whitespace normalization (trimming outer whitespace, collapsing runs of
    // spaces/tabs) is allowed; no character of actual content may be dropped or the
    // text cut mid-sentence.
    assert.ok(
      prompt.includes(brief.trim()),
      "full 5000-char brief must appear verbatim (aside from outer whitespace trimming)",
    );
  });

  test("16. same inputs twice -> byte-identical output", () => {
    const brief = "Should we run the pilot in one department or three?";
    const { answers } = answerAll(PE, "analyze");
    const args = () => ({ archetypeId: "analyze", brief, answers: { ...answers } });
    const out1 = PE.assemble(args());
    const out2 = PE.assemble(args());
    assert.equal(out1, out2);
  });

  test("17. sample unavailable -> assembly runs on static answers alone", () => {
    const brief = "Explain what an API is to a non-technical audience";
    const { answers } = answerAll(PE, "teach");
    const prompt = PE.assemble({ archetypeId: "teach", brief, answers, aiAnswers: undefined });
    assert.ok(prompt.length > 0);
    assert.ok(prompt.includes("Role:"));
  });

  test("18. Claude follow-up answers append to Context and Constraints, never replace", () => {
    const brief = "Pull the key risks out of this 40-page report";
    const { answers } = answerAll(PE, "summarize");
    const staticAudience = answers.audience;
    const staticAvoid = answers.must_avoid;
    const prompt = PE.assemble({
      archetypeId: "summarize",
      brief,
      answers,
      aiAnswers: {
        context: ["a tailored context line"],
        constraints: ["a tailored constraint line"],
      },
    });
    assert.ok(prompt.includes(staticAudience), "static Context content must remain");
    assert.ok(prompt.includes(staticAvoid), "static Constraints content must remain");
    assert.ok(prompt.includes("a tailored context line"));
    assert.ok(prompt.includes("a tailored constraint line"));
  });
}

// ---------- Run the suite once per source ----------

let totalPassed = 0;
let totalFailed = 0;
const allFailures = [];

for (const source of SOURCES) {
  const context = vm.createContext({ console });
  vm.runInContext(source.code, context, { filename: source.label });
  const PE = context.PE;

  if (!PE) {
    console.error(`Logic in "${source.label}" did not expose a global \`PE\` object.`);
    process.exit(1);
  }

  let passed = 0;
  let failed = 0;
  function test(name, fn) {
    try {
      fn();
      passed++;
    } catch (e) {
      failed++;
      allFailures.push({ source: source.label, name, error: e });
    }
  }

  runSuite(PE, test);

  console.log(`${source.label}: ${passed} passed, ${failed} failed (of ${passed + failed})`);
  totalPassed += passed;
  totalFailed += failed;
}

console.log(`\nTOTAL: ${totalPassed} passed, ${totalFailed} failed (of ${totalPassed + totalFailed})\n`);
if (totalFailed > 0) {
  for (const f of allFailures) {
    console.log(`FAIL [${f.source}]: ${f.name}`);
    console.log(`      ${f.error.message}`);
  }
  process.exit(1);
}
