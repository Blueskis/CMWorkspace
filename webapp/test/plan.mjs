import {
  generatePlan, chunkSections, briefPrompt, modulePlanPrompt, slideCopyPrompt,
  questionsPrompt, tryRepairJson, extractExample,
} from "../src/plan.js";
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

// --- tryRepairJson: recovering from a reply the platform's own tolerant reader rejected ---
// This is the fix for the reported bug: a prompt whose worked example was itself invalid
// pseudo-JSON produced replies that mirrored that shape and never parsed at all. Repair
// cannot help THAT case (nothing valid to recover) but must help every other shape of
// invalid_json the platform can still hand back: two JSON values in one reply (the
// platform explicitly refuses to guess between them) and a reply cut short.
console.log("\n### tryRepairJson");

// unrepairable: a pseudo-JSON echo (bare type tokens, no real value to recover)
const pseudoJson = '{"system": string (a name), "x": 1}';
if (tryRepairJson(pseudoJson) !== null) { console.log("FAIL: expected pseudo-JSON echo to be unrepairable"); process.exit(1); }
console.log("  pseudo-JSON echo -> null (unrepairable) OK");

// genuinely hopeless input
if (tryRepairJson("") !== null) { console.log("FAIL: expected empty string to be unrepairable"); process.exit(1); }
if (tryRepairJson("not json at all, just prose.") !== null) { console.log("FAIL: expected plain prose to be unrepairable"); process.exit(1); }
if (tryRepairJson(undefined) !== null) { console.log("FAIL: expected undefined input to be unrepairable"); process.exit(1); }
console.log("  hopeless input -> null OK");

// valid JSON inside a ```json fence
const fenced = "Sure, here it is:\n```json\n{\"a\": 1, \"b\": [1, 2, 3]}\n```\nLet me know if you need changes.";
const fencedResult = tryRepairJson(fenced);
if (!fencedResult || fencedResult.a !== 1 || !Array.isArray(fencedResult.b)) { console.log("FAIL: expected fenced JSON to be recovered", fencedResult); process.exit(1); }
console.log("  fenced JSON -> recovered OK");

// valid JSON with one sentence before and after
const sentenceWrapped = 'Here you go:\n{"name": "widget", "count": 3}\nHope that helps!';
const sentenceResult = tryRepairJson(sentenceWrapped);
if (!sentenceResult || sentenceResult.name !== "widget" || sentenceResult.count !== 3) { console.log("FAIL: expected sentence-wrapped JSON to be recovered", sentenceResult); process.exit(1); }
console.log("  sentence-wrapped JSON -> recovered OK");

// two JSON values in one reply — the exact case the platform's own reader refuses
const twoValues = 'First attempt: {"name": "first", "n": 1}\nActually, better: {"name": "second", "n": 2}';
const twoValuesResult = tryRepairJson(twoValues);
if (!twoValuesResult || typeof twoValuesResult.name !== "string" || typeof twoValuesResult.n !== "number") { console.log("FAIL: expected one valid object recovered from two-value reply", twoValuesResult); process.exit(1); }
console.log("  two JSON values in one reply -> recovered one valid object OK");

// an unterminated tail (cut short mid-value)
const cutShort = '{"questions": [{"question_id": "Q1", "type": "mcq", "options": ["a", "b"';
const cutShortResult = tryRepairJson(cutShort);
if (!cutShortResult || !Array.isArray(cutShortResult.questions) || cutShortResult.questions[0].question_id !== "Q1") { console.log("FAIL: expected unterminated tail to be recovered", cutShortResult); process.exit(1); }
console.log("  unterminated tail -> recovered OK");

console.log("\nAll tryRepairJson checks passed.");

// --- every prompt's worked example must be JSON.parse-able on its own — the guard
// against this exact bug class returning ---
console.log("\n### prompt example blocks are valid JSON");
const dummyBrief = {
  system: "Test", process_scope: "test",
  audiences: [{ audience_id: "a", role_name: "A", tasks: ["x"] }],
  learning_objectives: [{ lo_id: "LO1", text: "do it", bloom_level: "apply", audience_ids: ["a"], sources: [corpus.sections[0].section_id] }],
  out_of_scope: [],
};
const dummyModule = { module_id: "m1", title: "M1", slides: [{ slide_id: "s1", role: "content", title: "M1" }] };
const dummyModuleSections = corpus.sections.slice(0, 2);
const promptsToCheck = [
  ["briefPrompt", briefPrompt(corpus)],
  ["modulePlanPrompt", modulePlanPrompt(corpus, dummyBrief)],
  ["slideCopyPrompt", slideCopyPrompt(dummyModule, dummyModuleSections, corpus)],
  ["questionsPrompt", questionsPrompt(dummyBrief, procSections.slice(0, 2), 3)],
];
for (const [name, promptText] of promptsToCheck) {
  const example = extractExample(promptText);
  if (!example) { console.log(`FAIL: ${name} has no extractable example block`); process.exit(1); }
  let parsed;
  try {
    parsed = JSON.parse(example);
  } catch (err) {
    console.log(`FAIL: ${name}'s example block is not valid JSON: ${err.message}`);
    console.log(example);
    process.exit(1);
  }
  if (parsed === null || typeof parsed !== "object") { console.log(`FAIL: ${name}'s example block did not parse to an object`); process.exit(1); }
  console.log(`  ${name}: example block parses OK (${example.length} bytes)`);
}
console.log("\nAll prompt example blocks are valid JSON.");

// --- callSampleJson salvage path, exercised through generatePlan() ---
console.log("\n### invalid_json salvage via generatePlan()");
async function repairableMock(prompt) {
  if (prompt.startsWith("You are drafting the intake brief")) {
    const err = new Error("the reply held no JSON value");
    err.code = "invalid_json";
    err.text = 'Here is the brief:\n' + JSON.stringify(bigBrief) + '\nLet me know if you need anything else.';
    throw err;
  }
  if (prompt.startsWith("You are planning the module")) {
    return { modules: [{ module_id: "m1", title: "M1", order: 1, objective_ids: ["LO1"], slides: [{ slide_id: "s1", role: "content", title: "M1" }] }] };
  }
  if (prompt.startsWith("Write the slide content")) {
    return { slides: [{ slide_id: "s1", role: "content", blocks: [{ slot: "title", kind: "text", content: "T", sources: ["proc#s0"] }] }] };
  }
  if (prompt.startsWith("Write exactly")) {
    return { questions: [{ question_id: "Q1", objective_id: "LO1", type: "mcq", stem: "s",
      options: [{ option_id: "a", text: "A" }, { option_id: "b", text: "B" }, { option_id: "c", text: "C" }, { option_id: "d", text: "D" }],
      key: ["a"], rationale: "r", bloom_level: "apply", audience_ids: ["a"], sources: ["proc#s0"] }] };
  }
  throw new Error("unrecognized prompt: " + prompt.slice(0, 80));
}
const repairedResult = await generatePlan(bigCorpus, { sampleJson: repairableMock, questionCount: 1 });
if (!repairedResult?.brief?.system) { console.log("FAIL: expected generatePlan to complete via salvaged brief"); process.exit(1); }
console.log("  repairable invalid_json -> generatePlan completed with no error surfaced OK");

async function unrepairableMock(prompt) {
  if (prompt.startsWith("You are drafting the intake brief")) {
    const err = new Error("the reply held no JSON value");
    err.code = "invalid_json";
    err.text = '{"system": string (a name), "x": 1}'; // pseudo-JSON echo — nothing to recover
    throw err;
  }
  throw new Error("unrecognized prompt: " + prompt.slice(0, 80));
}
let unrepairableCaught = null;
try {
  await generatePlan(bigCorpus, { sampleJson: unrepairableMock, questionCount: 1 });
  console.log("FAIL: expected unrepairable invalid_json to still throw");
  process.exit(1);
} catch (e) {
  unrepairableCaught = e;
}
if (unrepairableCaught.code !== "invalid_json") { console.log("FAIL: expected the rethrown error to keep .code"); process.exit(1); }
if (typeof unrepairableCaught.text !== "string") { console.log("FAIL: expected the rethrown error to keep .text"); process.exit(1); }
if (!unrepairableCaught.progress) { console.log("FAIL: expected the rethrown error to carry .progress"); process.exit(1); }
console.log("  unrepairable invalid_json -> still throws, carrying .text and .progress OK");

console.log("\nAll invalid_json salvage checks passed.");

// --- MAX_SLIDES_PER_CALL: a module with many slides must be batched into multiple
// slideCopyPrompt calls (this is the exact failure a real viewer hit — a dense module's
// full slide list in one call got cut off mid-JSON). Also confirms batch-level resume:
// a failure partway through a module's batches must not discard the batches that already
// succeeded.
console.log("\n### slide-copy output batching + batch-level resume");
const manyModuleSlides = Array.from({ length: 9 }, (_, i) => ({ slide_id: `s${i + 1}`, role: "content", title: `Slide ${i + 1}` }));
const bigModuleSkeleton = { module_id: "mass", title: "Mass Processing", order: 1, objective_ids: ["LO1"], slides: manyModuleSlides };
let slideCopyCallCount = 0;
let slideCopyBatchSizes = [];
let failOnBatch = 2; // 1-indexed call number to fail, once
async function batchingMock(prompt) {
  if (prompt.startsWith("You are drafting the intake brief")) return bigBrief;
  if (prompt.startsWith("You are planning the module")) return { modules: [bigModuleSkeleton] };
  if (prompt.startsWith("Write the slide content")) {
    slideCopyCallCount++;
    const m = /"slides":\s*(\[[\s\S]*?\])\s*}\s*,\s*"role"/.exec(prompt) || /"module_id":"mass"[\s\S]*?"slides":(\[.*?\])\}/.exec(prompt);
    // pull the requested slide_ids straight out of the embedded module JSON rather than
    // guessing the batch boundary from call count, so this test is honest about what the
    // prompt actually asked for.
    const moduleJsonMatch = /Module: (\{.*?\})\n\nSource sections/s.exec(prompt);
    const reqSlideIds = moduleJsonMatch ? JSON.parse(moduleJsonMatch[1]).slides.map((s) => s.slide_id) : [];
    slideCopyBatchSizes.push(reqSlideIds.length);
    if (slideCopyCallCount === failOnBatch) {
      const err = new Error("the reply held no JSON value");
      err.code = "invalid_json";
      err.text = "I'm sorry, I can't produce that content."; // no JSON at all — genuinely unrepairable
      throw err;
    }
    return { slides: reqSlideIds.map((id) => ({ slide_id: id, role: "content",
      blocks: [{ slot: "title", kind: "text", content: id, sources: ["proc#s0"] }] })) };
  }
  if (prompt.startsWith("Write exactly")) {
    return { questions: [{ question_id: "Q1", objective_id: "LO1", type: "mcq", stem: "s",
      options: [{ option_id: "a", text: "A" }, { option_id: "b", text: "B" }, { option_id: "c", text: "C" }, { option_id: "d", text: "D" }],
      key: ["a"], rationale: "r", bloom_level: "apply", audience_ids: ["a"], sources: ["proc#s0"] }] };
  }
  throw new Error("unrecognized prompt: " + prompt.slice(0, 80));
}

let batchingCaught = null;
try {
  await generatePlan(bigCorpus, { sampleJson: batchingMock, questionCount: 1 });
  console.log("FAIL: expected the 2nd slide-copy batch to throw");
  process.exit(1);
} catch (e) {
  batchingCaught = e;
}
console.log(`  batch sizes requested before failure: ${slideCopyBatchSizes.join(", ")}`);
if (slideCopyBatchSizes.some((n) => n > 4)) { console.log("FAIL: a slide-copy call asked for more than MAX_SLIDES_PER_CALL slides"); process.exit(1); }
const partialModule = batchingCaught.progress.modules.find((m) => m.module_id === "mass");
if (!partialModule || partialModule.slides.length !== 4) {
  console.log(`FAIL: expected e.progress to preserve exactly 4 already-completed slides (batch 1), got ${partialModule?.slides.length}`);
  process.exit(1);
}
console.log(`  e.progress preserved ${partialModule.slides.length} slides from the succeeded batch before the failure`);

slideCopyCallCount = 0;
slideCopyBatchSizes = [];
failOnBatch = -1; // don't fail again on resume
const resumedBatching = await generatePlan(bigCorpus, { sampleJson: batchingMock, questionCount: 1, resume: batchingCaught.progress });
const finalMassModule = resumedBatching.plan.modules.find((m) => m.module_id === "mass");
if (finalMassModule.slides.length !== 9) { console.log(`FAIL: expected all 9 slides after resume, got ${finalMassModule.slides.length}`); process.exit(1); }
const finalIds = finalMassModule.slides.map((s) => s.slide_id).sort();
if (new Set(finalIds).size !== 9) { console.log("FAIL: duplicate or missing slide_ids after resume:", finalIds); process.exit(1); }
console.log(`  after resume: ${slideCopyCallCount} more call(s) made, module now has all ${finalMassModule.slides.length} slides (no duplicates, no gaps)`);

console.log("\nAll slide-copy batching + resume checks passed.");
