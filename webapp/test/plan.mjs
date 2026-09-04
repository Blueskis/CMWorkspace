import { generatePlan, chunkSections, briefPrompt, modulePlanPrompt, slideCopyPrompt, questionsPrompt } from "../src/plan.js";
import { parseDocx } from "../src/parse-docx.js";
import { readFileSync } from "node:fs";

const bytes = readFileSync("../training/supplier-block-unblock-20260829/inputs/FSD_MMWA014_Supplier_Block_Unblock.docx");
const parsed = await parseDocx(bytes, "FSD_MMWA014_Supplier_Block_Unblock.docx");
const corpus = { documents: [parsed.document], sections: parsed.sections, assets: parsed.assets, notes: [] };

console.log(`corpus: ${corpus.sections.length} sections, ${corpus.assets.length} assets`);

// --- byte budgets ---
const bp = briefPrompt(corpus);
console.log(`brief prompt: ${new TextEncoder().encode(bp).length} bytes`);
if (new TextEncoder().encode(bp).length > 60000) { console.log("FAIL: brief prompt over budget"); process.exit(1); }

const chunks = chunkSections(corpus.sections);
console.log(`full-corpus chunking: ${chunks.length} chunk(s)`, chunks.map(c => c.length));
for (const c of chunks) {
  const size = new TextEncoder().encode(JSON.stringify(c)).length;
  if (size > 61440) { console.log("FAIL: chunk over budget", size); process.exit(1); }
}

// --- mock sampler with realistic shapes, driven off the REAL corpus ---
const procSections = corpus.sections.filter(s => s.classifier === "procedure");
let brief;
async function mockSample(prompt, opts) {
  const bytes = new TextEncoder().encode(prompt).length;
  if (bytes > 65536) throw new Error(`prompt exceeds sample's 64KiB cap: ${bytes} bytes`);
  if (prompt.startsWith("You are drafting the intake brief")) {
    brief = {
      system: "Supplier Block/Unblock", process_scope: "test scope",
      audiences: [{ audience_id: "requester", role_name: "Requester", tasks: ["submit"] }],
      learning_objectives: procSections.slice(0, 4).map((s, i) => ({
        lo_id: `LO${i+1}`, text: `Do the thing in ${s.title}`, bloom_level: "apply",
        audience_ids: ["requester"], sources: [s.section_id],
      })),
      out_of_scope: procSections.slice(4).map(s => ({ section_id: s.section_id, reason: "test" })),
    };
    return brief;
  }
  if (prompt.startsWith("You are planning the module")) {
    return { modules: [
      { module_id: "cover", title: "Cover", order: 1, objective_ids: [], slides: [{ slide_id: "cover-1", role: "title-slide", title: "Cover" }] },
      ...brief.learning_objectives.map((lo, i) => ({
        module_id: `mod-${lo.lo_id.toLowerCase()}`, title: lo.text, order: i + 2,
        objective_ids: [lo.lo_id], slides: [{ slide_id: `s-${lo.lo_id}`, role: "content", title: lo.text }],
      })),
    ] };
  }
  if (prompt.startsWith("Write the slide content")) {
    return { slides: [{ slide_id: "x", role: "content", speaker_notes: "note",
      blocks: [{ slot: "title", kind: "text", content: "T", sources: [procSections[0].section_id] }] }] };
  }
  if (prompt.startsWith("Write exactly")) {
    return { questions: [1,2,3,4,5].map((n, i) => ({
      question_id: `Q${n}`, objective_id: brief.learning_objectives[i % brief.learning_objectives.length].lo_id,
      type: i % 2 === 0 ? "mcq" : "true-false",
      stem: "stem", options: i % 2 === 0
        ? [{option_id:"a",text:"A"},{option_id:"b",text:"B"},{option_id:"c",text:"C"},{option_id:"d",text:"D"}]
        : [{option_id:"t",text:"True"},{option_id:"f",text:"False"}],
      key: [i % 2 === 0 ? "b" : "t"], rationale: "because", bloom_level: "apply",
      audience_ids: ["requester"], sources: [procSections[0].section_id],
    })) };
  }
  throw new Error("unrecognized prompt shape: " + prompt.slice(0, 100));
}

const stages = [];
const result = await generatePlan(corpus, { sampleJson: mockSample, onStage: (s) => stages.push(s) });
console.log("stages:", stages.join(" -> "));
console.log("modules:", result.plan.modules.length, "questions:", result.questions.questions.length);
console.log("\nAll plan.js orchestration checks passed.");

// --- force the chunker to split: a module whose sections exceed one call's budget ---
console.log("\n### oversized-module chunking");
const bigSections = Array.from({length: 20}, (_, i) => ({
  section_id: `big#s${i}`, section_path: `Section ${i}`, text: "x".repeat(6000),
}));
const bigChunks = chunkSections(bigSections);
console.log(`  20 sections x 6000 chars -> ${bigChunks.length} chunks, sizes: ${bigChunks.map(c=>c.length).join(",")}`);
if (bigChunks.length < 2) { console.log("FAIL: expected >1 chunk"); process.exit(1); }
const total = bigChunks.flat().length;
if (total !== 20) { console.log("FAIL: lost sections while chunking:", total); process.exit(1); }
for (const c of bigChunks) {
  const size = new TextEncoder().encode(JSON.stringify(c)).length;
  if (size > 61440) { console.log("FAIL: chunk still over budget:", size); process.exit(1); }
}

// a single section bigger than the whole budget
const huge = [{ section_id: "huge#s1", section_path: "Huge", text: "y".repeat(200000) }];
const hugeChunks = chunkSections(huge);
console.log(`  one 200KB section -> ${hugeChunks.length} chunk(s), truncated=${hugeChunks[0][0]._truncated}`);
if (!hugeChunks[0][0]._truncated) { console.log("FAIL: expected truncation flag"); process.exit(1); }
const hugeSize = new TextEncoder().encode(JSON.stringify(hugeChunks[0])).length;
if (hugeSize > 61440) { console.log("FAIL: truncated section still over budget:", hugeSize); process.exit(1); }

console.log("\nAll chunking edge cases passed.");

// --- questions call must chunk too: an FSD with enough procedure text to cross the
// 64 KiB cap used to go into ONE unbounded call (the actual bug this section guards
// against) — now it should split, merge, and renumber to exactly `count` questions.
console.log("\n### oversized questions chunking");
const manyProcSections = Array.from({ length: 10 }, (_, i) => ({
  section_id: `proc#s${i}`, section_path: `Procedure ${i}`, classifier: "procedure",
  text: "z".repeat(9000),
}));
const bigBrief = {
  system: "Test", process_scope: "test",
  audiences: [{ audience_id: "a", role_name: "A", tasks: ["x"] }],
  learning_objectives: [{ lo_id: "LO1", text: "do it", bloom_level: "apply", audience_ids: ["a"], sources: ["proc#s0"] }],
  out_of_scope: [],
};
const bigCorpus = { documents: [{ document_id: "big" }], sections: manyProcSections, assets: [], notes: [] };
let qCallCount = 0;
async function chunkedMock(prompt) {
  const bytes = new TextEncoder().encode(prompt).length;
  if (bytes > 65536) throw new Error(`prompt exceeds cap: ${bytes} bytes`);
  if (prompt.startsWith("You are drafting the intake brief")) return bigBrief;
  if (prompt.startsWith("You are planning the module")) {
    return { modules: [{ module_id: "m1", title: "M1", order: 1, objective_ids: ["LO1"], slides: [{ slide_id: "s1", role: "content", title: "M1" }] }] };
  }
  if (prompt.startsWith("Write the slide content")) {
    return { slides: [{ slide_id: "s1", role: "content", blocks: [{ slot: "title", kind: "text", content: "T", sources: ["proc#s0"] }] }] };
  }
  if (prompt.startsWith("Write exactly")) {
    qCallCount++;
    const m = /"question_id": "Q1"\.\."Q(\d+)"/.exec(prompt);
    const n = m ? parseInt(m[1], 10) : 1;
    return { questions: Array.from({ length: n }, (_, i) => ({
      question_id: `Q${i + 1}`, objective_id: "LO1", type: "mcq", stem: `stem ${qCallCount}-${i}`,
      options: [{ option_id: "a", text: "A" }, { option_id: "b", text: "B" }, { option_id: "c", text: "C" }, { option_id: "d", text: "D" }],
      key: ["a"], rationale: "because", bloom_level: "apply", audience_ids: ["a"], sources: ["proc#s0"],
    })) };
  }
  throw new Error("unrecognized prompt: " + prompt.slice(0, 80));
}
const bigResult = await generatePlan(bigCorpus, { sampleJson: chunkedMock, questionCount: 5 });
console.log(`  questions calls made: ${qCallCount}, final question count: ${bigResult.questions.questions.length}`);
if (qCallCount < 2) { console.log("FAIL: expected the questions stage to split into multiple calls"); process.exit(1); }
if (bigResult.questions.questions.length !== 5) { console.log("FAIL: expected exactly 5 merged questions"); process.exit(1); }
const ids = bigResult.questions.questions.map((q) => q.question_id);
if (new Set(ids).size !== 5 || ids.join(",") !== "Q1,Q2,Q3,Q4,Q5") { console.log("FAIL: question ids not renumbered cleanly:", ids); process.exit(1); }
console.log("\nAll questions-chunking checks passed.");

// --- resumable retry: a failure partway through must expose e.progress, and passing
// that back in as `resume` must skip re-asking whatever already succeeded ---
console.log("\n### resumable retry");
let briefCalls = 0, modulePlanCalls = 0, slideCopyCalls = 0, questionsCalls = 0;
let failModulePlanOnce = true;
async function partialFailMock(prompt) {
  if (prompt.startsWith("You are drafting the intake brief")) {
    briefCalls++;
    return bigBrief;
  }
  if (prompt.startsWith("You are planning the module")) {
    modulePlanCalls++;
    if (failModulePlanOnce) {
      failModulePlanOnce = false;
      const err = new Error("the reply held no JSON value");
      err.code = "invalid_json";
      throw err;
    }
    return { modules: [{ module_id: "m1", title: "M1", order: 1, objective_ids: ["LO1"], slides: [{ slide_id: "s1", role: "content", title: "M1" }] }] };
  }
  if (prompt.startsWith("Write the slide content")) {
    slideCopyCalls++;
    return { slides: [{ slide_id: "s1", role: "content", blocks: [{ slot: "title", kind: "text", content: "T", sources: ["proc#s0"] }] }] };
  }
  if (prompt.startsWith("Write exactly")) {
    questionsCalls++;
    return { questions: [{ question_id: "Q1", objective_id: "LO1", type: "mcq", stem: "s",
      options: [{ option_id: "a", text: "A" }, { option_id: "b", text: "B" }, { option_id: "c", text: "C" }, { option_id: "d", text: "D" }],
      key: ["a"], rationale: "r", bloom_level: "apply", audience_ids: ["a"], sources: ["proc#s0"] }] };
  }
  throw new Error("unrecognized prompt: " + prompt.slice(0, 80));
}

let caught = null;
try {
  await generatePlan(bigCorpus, { sampleJson: partialFailMock, questionCount: 1 });
  console.log("FAIL: expected the module-plan call to throw");
  process.exit(1);
} catch (e) {
  caught = e;
}
if (!caught.progress || !caught.progress.brief) {
  console.log("FAIL: expected e.progress to carry the already-completed brief");
  process.exit(1);
}
if (caught.progress.moduleSkeletons) {
  console.log("FAIL: module-plan failed — its result should NOT be in progress");
  process.exit(1);
}
console.log(`  first attempt: brief=${briefCalls} modulePlan=${modulePlanCalls} (failed) — e.progress.brief present: ${!!caught.progress.brief}`);

const resumed = await generatePlan(bigCorpus, { sampleJson: partialFailMock, questionCount: 1, resume: caught.progress });
if (briefCalls !== 1) { console.log(`FAIL: brief should not be re-asked on resume, got ${briefCalls} calls`); process.exit(1); }
if (modulePlanCalls !== 2) { console.log(`FAIL: expected module-plan retried exactly once more, got ${modulePlanCalls}`); process.exit(1); }
if (!resumed.plan.modules.length) { console.log("FAIL: resumed run produced no modules"); process.exit(1); }
console.log(`  after resume: brief=${briefCalls} (not re-asked) modulePlan=${modulePlanCalls} slideCopy=${slideCopyCalls} questions=${questionsCalls}`);
console.log("\nResumable retry works correctly.");
