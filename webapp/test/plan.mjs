import {
  generatePlan, chunkSections, briefPrompt, modulePlanPrompt, slideCopyPrompt,
  questionsPrompt, tryRepairJson, extractExample, describeJsonFailure,
  harvestSlides, PLACEHOLDER_TEXT,
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

// --- malformed-but-COMPLETE replies. These are the cases the real FSD provokes: its
// section text contains literal quoted labels (BL99 "Legacy block - reason not recorded",
// the "Procurement" space) and 60 line breaks, and a model copying one into a value
// verbatim emits JSON that is finished but unparseable. All four were unrepairable until
// the sanitize passes were added.
const innerQuotes = '{"slides":[{"slide_id":"s1","blocks":[{"slot":"body","kind":"bullets","content":["Reason code BL99 "Legacy block - reason not recorded" applies","Use the "Procurement" space"],"sources":["d#3.3"]}]}]}';
const innerQuotesResult = tryRepairJson(innerQuotes);
if (!innerQuotesResult) { console.log("FAIL: expected unescaped inner quotes to be repaired"); process.exit(1); }
const recoveredBullets = innerQuotesResult.slides[0].blocks[0].content;
// the quoted label must survive as CONTENT, not be silently dropped or mangled
if (recoveredBullets[0] !== 'Reason code BL99 "Legacy block - reason not recorded" applies'
  || recoveredBullets[1] !== 'Use the "Procurement" space') {
  console.log("FAIL: inner-quote repair lost or mangled the text", recoveredBullets); process.exit(1);
}
console.log("  unescaped inner quotes -> repaired, quoted labels preserved verbatim OK");

const rawNewline = '{"slides":[{"slide_id":"s1","speaker_notes":"First line.\nSecond line.","blocks":[]}]}';
const rawNewlineResult = tryRepairJson(rawNewline);
if (!rawNewlineResult || rawNewlineResult.slides[0].speaker_notes !== "First line.\nSecond line.") {
  console.log("FAIL: expected raw line break in a string to be repaired", rawNewlineResult); process.exit(1);
}
console.log("  raw line break inside a string -> repaired OK");

const trailingComma = '{"slides":[{"slide_id":"s1","blocks":[],}]}';
if (!tryRepairJson(trailingComma)) { console.log("FAIL: expected trailing comma to be repaired"); process.exit(1); }
console.log("  trailing comma -> repaired OK");

// The sentence that defeats a naive "a quote before a comma closes the string" rule —
// taken verbatim from the real FSD's section 5.3. Keep this exact case: it is why
// quoteClosesString has to look PAST the comma at what the container expects next.
const sec53 = 'All user entry runs through the SAP Fiori launchpad space "Procurement", page "Supplier Governance". Classic GUI access is retained only for the mass job.';
const sec53Reply = '{"slides":[{"slide_id":"s1","speaker_notes":"' + sec53 + '","blocks":[]}]}';
const sec53Result = tryRepairJson(sec53Reply);
if (!sec53Result || sec53Result.slides[0].speaker_notes !== sec53) {
  console.log("FAIL: expected the real 5.3 sentence to be recovered verbatim", sec53Result?.slides?.[0]?.speaker_notes);
  process.exit(1);
}
console.log("  quote-before-comma (real FSD 5.3 sentence) -> repaired verbatim OK");

const bothAtOnce = '{"a":"he said "hi"\nthen left","b":1}';
const bothResult = tryRepairJson(bothAtOnce);
if (!bothResult || bothResult.a !== 'he said "hi"\nthen left' || bothResult.b !== 1) {
  console.log("FAIL: expected quotes+newline together to be repaired", bothResult); process.exit(1);
}
console.log("  unescaped quote AND line break together -> repaired OK");

console.log("\nAll tryRepairJson checks passed.");

// --- describeJsonFailure: the error screen must distinguish a genuinely cut-short reply
// from a complete-but-malformed one. Conflating them (a bare slice(0,600) made every
// reply look truncated) is what sent two rounds of fixes after the wrong root cause.
console.log("\n### describeJsonFailure");

const dTruncated = describeJsonFailure('{"slides":[{"slide_id":"s1","role":"picture","blocks":[{"slot":"title"');
if (!dTruncated.truncated) { console.log("FAIL: a cut-short reply must report truncated=true"); process.exit(1); }
console.log(`  cut-short reply -> truncated=true, length=${dTruncated.length} OK`);

const dMalformed = describeJsonFailure(innerQuotes);
if (dMalformed.truncated) { console.log("FAIL: a complete-but-malformed reply must NOT report truncated=true"); process.exit(1); }
if (dMalformed.length !== innerQuotes.length) { console.log("FAIL: reported length must be the true reply length"); process.exit(1); }
console.log(`  complete-but-malformed reply -> truncated=false, length=${dMalformed.length} OK`);

// the snippet must show the text AROUND the parse error, not just the start of the reply
const longPrefix = '{"pad":"' + "x".repeat(3000) + '","bad":"he said "hi""}';
const dLong = describeJsonFailure(longPrefix);
if (dLong.position === null || dLong.position < 3000) { console.log("FAIL: expected the parse error position deep in the reply", dLong.position); process.exit(1); }
if (!dLong.snippet.includes("he said")) { console.log("FAIL: snippet must show the text around the error, not the first 600 chars"); process.exit(1); }
console.log(`  error 3000+ chars in -> position=${dLong.position}, snippet centred on the fault OK`);

console.log("\nAll describeJsonFailure checks passed.");

// --- tryRepairJson must never silently return a slides reply short of what the raw text
// promised. Caught during independent verification of this fix, not in the original
// design: the pre-existing "largest balanced span" pass can find a technically-valid
// object that happens to end right before a damaged slide, silently dropping every slide
// after it — AND, in this exact case, misplacing the damaged slide's own "sources" field
// a level too deep in the bargain. That is worse than an error: it looks like success.
// tryRepairJson must return null here so the slide-copy loop's own harvestSlides(e.text)
// does a proper per-slide salvage instead (verified above to recover the 3 undamaged
// slides byte-exact) rather than silently shipping a 2-slide, partially-corrupted result.
console.log("\n### tryRepairJson must not silently drop trailing slides from a batch");

const mkBatchSlide = (id) => `{"slide_id":"${id}","role":"content","speaker_notes":"n","blocks":[{"slot":"title","kind":"text","content":"T ${id}","sources":["fsd#7.6"]},{"slot":"body","kind":"bullets","content":["a","b"],"sources":["fsd#7.6"]}]}`;
const diagBatchSlide = `{"slide_id":"s-ex-2","role":"content","speaker_notes":"n","blocks":[{"slot":"title","kind":"text","content":"T","sources":["fsd#7.6"]},{"slot":"body","kind":"diagram","content":{"diagram_type":"decision","spec":{"branches":[{"condition":"All suppliers succeeded","outcome":"Return code 0"},{"condition":"Any supplier failed","outcome":"Return code 8, evaluated by job chain"}]}},"sources":["fsd#7.6"]}]}`;
const goodBatch = `{"slides":[${mkBatchSlide("s-ex-1")},${diagBatchSlide},${mkBatchSlide("s-ex-3")},${mkBatchSlide("s-ex-4")}]}`;
const brokenBatch = goodBatch.replace(`}]}},"sources":["fsd#7.6"]}]},{"slide_id":"s-ex-3"`, `}]},"sources":["fsd#7.6"]}]},{"slide_id":"s-ex-3"`);
if (goodBatch === brokenBatch) { console.log("FAIL: test setup didn't actually corrupt the reply"); process.exit(1); }
const batchRepairResult = tryRepairJson(brokenBatch);
if (batchRepairResult !== null) {
  console.log("FAIL: expected tryRepairJson to refuse a slides reply short of what the raw text promised, got", JSON.stringify(batchRepairResult));
  process.exit(1);
}
console.log("  4-slide batch with one damaged diagram slide -> tryRepairJson correctly returns null (defers to harvestSlides)");

// And the fallback it defers to must actually deliver: end-to-end through generatePlan.
console.log("\n### generatePlan recovers undamaged slides and placeholders only the damaged one");
const batchModuleSkeleton = { module_id: "m-batch", title: "Batch", order: 1, objective_ids: ["LO1"],
  slides: ["s-ex-1", "s-ex-2", "s-ex-3", "s-ex-4"].map((id) => ({ slide_id: id, role: "content", title: id })) };
async function batchCorruptionMock(prompt) {
  if (prompt.startsWith("You are drafting the intake brief")) return bigBrief;
  if (prompt.startsWith("You are planning the module")) return { modules: [batchModuleSkeleton] };
  if (prompt.startsWith("Write the slide content")) {
    const err = new Error("the reply held no JSON value");
    err.code = "invalid_json"; err.text = brokenBatch;
    throw err;
  }
  if (prompt.startsWith("Write exactly")) {
    return { questions: [{ question_id: "Q1", objective_id: "LO1", type: "mcq", stem: "s",
      options: [{ option_id: "a", text: "A" }, { option_id: "b", text: "B" }, { option_id: "c", text: "C" }, { option_id: "d", text: "D" }],
      key: ["a"], rationale: "r", bloom_level: "apply", audience_ids: ["a"], sources: ["proc#s0"] }] };
  }
  throw new Error("unrecognized prompt: " + prompt.slice(0, 80));
}
const batchCorruptionResult = await generatePlan(bigCorpus, { sampleJson: batchCorruptionMock, questionCount: 1 });
const batchMod = batchCorruptionResult.plan.modules.find((m) => m.module_id === "m-batch");
const gotIds = batchMod.slides.map((s) => s.slide_id).sort();
if (JSON.stringify(gotIds) !== JSON.stringify(["s-ex-1", "s-ex-2", "s-ex-3", "s-ex-4"])) {
  console.log("FAIL: expected all 4 planned slides present (3 real + 1 placeholder), got", gotIds); process.exit(1);
}
const placeholders = batchMod.slides.filter((s) => s._placeholder).map((s) => s.slide_id);
if (placeholders.length !== 1 || placeholders[0] !== "s-ex-2") {
  console.log("FAIL: expected exactly s-ex-2 (the damaged slide) to be a placeholder, got", placeholders); process.exit(1);
}
const s1 = batchMod.slides.find((s) => s.slide_id === "s-ex-1");
if (s1._placeholder || !s1.blocks.some((b) => b.kind === "bullets")) {
  console.log("FAIL: expected s-ex-1 (undamaged) to keep its real bullet content, got", JSON.stringify(s1)); process.exit(1);
}
console.log("  3 undamaged slides kept real content, only the damaged diagram slide became a placeholder");

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

// --- harvestSlides: recovering individual slides out of a reply that fails to parse as a
// whole. This is the fix for the real reported bug: a diagram spec closed one brace short
// destroyed all four slides in the batch. See harvestSlides' own docstring for why the
// scan must resume at i+1 (not past the failed span) on a rejected candidate.
console.log("\n### harvestSlides");

function makeSlideReply(id, extra = "") {
  return `{"slide_id":"${id}","role":"content","speaker_notes":"Notes for ${id}.","blocks":[{"slot":"title","kind":"text","content":"Title ${id}","sources":["fsd#7.6"]},{"slot":"body","kind":"bullets","content":["Point one for ${id}","Point two"],"sources":["fsd#7.6"]}${extra}]}`;
}
const diagramBlock = `,{"slot":"body","kind":"diagram","content":{"diagram_type":"decision","spec":{"branches":[{"condition":"All suppliers succeeded","outcome":"Return code 0"},{"condition":"Any failed","outcome":"Return code 8"}]}},"sources":["fsd#7.6"]}`;
const goodReply = `{"slides":[${makeSlideReply("s1")},${makeSlideReply("s2", diagramBlock)},${makeSlideReply("s3")},${makeSlideReply("s4")}]}`;
// the model's actual mistake: one dropped "}" inside the diagram spec's "content"
const brokenReply = goodReply.replace(`}]}},"sources"`, `}]},"sources"`);
const goodParsed = JSON.parse(goodReply);

const harvested = harvestSlides(brokenReply, ["s1", "s2", "s3", "s4"]);
const harvestedIds = harvested.map((s) => s.slide_id).sort();
if (harvestedIds.join(",") !== "s1,s3,s4") {
  console.log("FAIL: expected exactly s1, s3, s4 recovered (s2 damaged and lost)", harvestedIds);
  process.exit(1);
}
for (const id of ["s1", "s3", "s4"]) {
  const got = JSON.stringify(harvested.find((s) => s.slide_id === id));
  const want = JSON.stringify(goodParsed.slides.find((s) => s.slide_id === id));
  if (got !== want) { console.log(`FAIL: ${id} not byte-exact after harvest`, got, want); process.exit(1); }
}
console.log("  reproduction reply -> recovered s1, s3, s4 byte-exact, s2 correctly lost OK");

// a reply cut off mid-slide must still yield every slide completed before the cut
const cutIndex = goodReply.indexOf(makeSlideReply("s3")) + 40; // partway into s3
const truncatedReply = goodReply.slice(0, cutIndex);
const harvestedTruncated = harvestSlides(truncatedReply, ["s1", "s2", "s3", "s4"]).map((s) => s.slide_id).sort();
if (harvestedTruncated.join(",") !== "s1,s2") {
  console.log("FAIL: expected s1, s2 recovered from a reply cut off partway into s3", harvestedTruncated);
  process.exit(1);
}
console.log("  reply cut off mid-slide -> recovered every slide completed before the cut OK");

// plain prose has nothing to harvest
if (harvestSlides("Sorry, I can't help with that.").length !== 0) {
  console.log("FAIL: expected no slides harvested from plain prose");
  process.exit(1);
}
console.log("  plain prose -> nothing harvested OK");

console.log("\nAll harvestSlides checks passed.");

// --- describeJsonFailure: an interior brace deficit must not be misreported as truncated.
// A missing brace deep in the reply leaves the same open-bracket stack at EOF a genuinely
// truncated reply would — the fix is to also check WHERE the parse failed: well before the
// end means structural, not cut short.
console.log("\n### describeJsonFailure — interior imbalance is not truncation");
const dInterior = describeJsonFailure(brokenReply);
if (dInterior.truncated) {
  console.log("FAIL: an interior dropped brace must report truncated=false, not read as cut short");
  process.exit(1);
}
console.log(`  dropped brace deep inside a complete reply -> truncated=false (position=${dInterior.position}, length=${dInterior.length}) OK`);
if (!dInterior.recoveredSlides.includes("s1") || !dInterior.recoveredSlides.includes("s3") || !dInterior.recoveredSlides.includes("s4")) {
  console.log("FAIL: expected describeJsonFailure to report the recoverable slides too", dInterior.recoveredSlides);
  process.exit(1);
}
console.log(`  recoveredSlides reports the salvageable slides: ${dInterior.recoveredSlides.join(", ")} OK`);

console.log("\nAll describeJsonFailure interior-imbalance checks passed.");

// --- generatePlan: a slide-copy batch that only partially harvests must not fail the run —
// the good slides are kept, the run continues, and the one slide that couldn't be read
// becomes a real placeholder slide, not a silent content-free skeleton.
console.log("\n### generatePlan — partial slide-copy salvage completes the run with a placeholder");
const fourSlideModule = {
  module_id: "mod-diagram", title: "Diagram Module", order: 1, objective_ids: ["LO1"],
  slides: [
    { slide_id: "s1", role: "content", title: "Slide One" },
    { slide_id: "s2", role: "content", title: "Slide Two" },
    { slide_id: "s3", role: "content", title: "Slide Three" },
    { slide_id: "s4", role: "content", title: "Slide Four" },
  ],
};
async function partialHarvestMock(prompt) {
  if (prompt.startsWith("You are drafting the intake brief")) return bigBrief;
  if (prompt.startsWith("You are planning the module")) return { modules: [fourSlideModule] };
  if (prompt.startsWith("Write the slide content")) {
    const err = new Error("the reply held no JSON value");
    err.code = "invalid_json";
    err.text = brokenReply;
    throw err;
  }
  if (prompt.startsWith("Write exactly")) {
    return { questions: [{ question_id: "Q1", objective_id: "LO1", type: "mcq", stem: "s",
      options: [{ option_id: "a", text: "A" }, { option_id: "b", text: "B" }, { option_id: "c", text: "C" }, { option_id: "d", text: "D" }],
      key: ["a"], rationale: "r", bloom_level: "apply", audience_ids: ["a"], sources: ["proc#s0"] }] };
  }
  throw new Error("unrecognized prompt: " + prompt.slice(0, 80));
}
const partialResult = await generatePlan(bigCorpus, { sampleJson: partialHarvestMock, questionCount: 1 });
const partialMod = partialResult.plan.modules.find((m) => m.module_id === "mod-diagram");
if (!partialMod) { console.log("FAIL: expected the module to be present in the completed plan"); process.exit(1); }
const bySlideId = Object.fromEntries(partialMod.slides.map((s) => [s.slide_id, s]));
if (!bySlideId.s1 || !bySlideId.s3 || !bySlideId.s4) {
  console.log("FAIL: expected s1, s3, s4 to keep their real generated content", Object.keys(bySlideId));
  process.exit(1);
}
if (bySlideId.s1.blocks[0].content !== "Title s1") { console.log("FAIL: s1's real content was not preserved"); process.exit(1); }
if (!bySlideId.s2 || !bySlideId.s2._placeholder) {
  console.log("FAIL: expected s2 (the one damaged slide) to be a placeholder", bySlideId.s2);
  process.exit(1);
}
const s2Body = bySlideId.s2.blocks.find((b) => b.slot === "body");
if (s2Body.gap_note !== PLACEHOLDER_TEXT) { console.log("FAIL: placeholder body block should carry the placeholder text", s2Body); process.exit(1); }
console.log("  run completed with no error surfaced: s1/s3/s4 real, s2 is a flagged placeholder OK");

console.log("\nAll partial-salvage generatePlan checks passed.");

// --- generatePlan: when NOTHING in a batch's raw reply is harvestable, the failure must
// still reach the caller, and e.progress must still carry whatever earlier batches (or
// modules) already completed — this is unchanged from before harvesting was added.
console.log("\n### generatePlan — nothing harvestable still throws, still preserves earlier progress");
let sawSecondModule = false;
async function nothingHarvestableMock(prompt) {
  if (prompt.startsWith("You are drafting the intake brief")) return bigBrief;
  if (prompt.startsWith("You are planning the module")) {
    return { modules: [
      { module_id: "mod-a", title: "A", order: 1, objective_ids: ["LO1"], slides: [{ slide_id: "a1", role: "content", title: "A1" }] },
      { module_id: "mod-b", title: "B", order: 2, objective_ids: ["LO1"], slides: [{ slide_id: "b1", role: "content", title: "B1" }] },
    ] };
  }
  if (prompt.startsWith("Write the slide content")) {
    if (prompt.includes('"module_id":"mod-a"')) {
      return { slides: [{ slide_id: "a1", role: "content", blocks: [{ slot: "title", kind: "text", content: "A1", sources: ["proc#s0"] }] }] };
    }
    sawSecondModule = true;
    const err = new Error("the reply held no JSON value");
    err.code = "invalid_json";
    err.text = "I'm sorry, I can't produce that content."; // genuinely nothing to harvest
    throw err;
  }
  throw new Error("unrecognized prompt: " + prompt.slice(0, 80));
}
let nothingHarvestableCaught = null;
try {
  await generatePlan(bigCorpus, { sampleJson: nothingHarvestableMock, questionCount: 1 });
  console.log("FAIL: expected mod-b's unrecoverable batch to throw");
  process.exit(1);
} catch (e) {
  nothingHarvestableCaught = e;
}
if (!sawSecondModule) { console.log("FAIL: test setup didn't reach mod-b as expected"); process.exit(1); }
if (nothingHarvestableCaught.code !== "invalid_json") { console.log("FAIL: expected the rethrown error to keep .code"); process.exit(1); }
const modA = nothingHarvestableCaught.progress?.modules?.find((m) => m.module_id === "mod-a");
if (!modA || modA.slides.length !== 1 || modA.slides[0].slide_id !== "a1") {
  console.log("FAIL: expected e.progress to preserve mod-a's already-completed slide", nothingHarvestableCaught.progress);
  process.exit(1);
}
console.log("  nothing harvestable in mod-b's reply -> still throws, mod-a's earlier progress preserved OK");

console.log("\nAll nothing-harvestable checks passed.");

// --- generatePlan: a reply returning FEWER slides than requested — no error at all, just
// a short reply — must never leave a blocks-less slide in the plan (the deleted
// `batchSlides.length ? batchSlides : slideBatch` fallback used to do exactly that, since
// module-plan skeleton slides carry no `blocks` array and render blank).
console.log("\n### generatePlan — a short (but valid) reply gets a placeholder, never a blocks-less slide");
async function shortReplyMock(prompt) {
  if (prompt.startsWith("You are drafting the intake brief")) return bigBrief;
  if (prompt.startsWith("You are planning the module")) {
    return { modules: [{ module_id: "mod-short", title: "Short", order: 1, objective_ids: ["LO1"], slides: [
      { slide_id: "x1", role: "content", title: "X1" },
      { slide_id: "x2", role: "content", title: "X2" },
    ] }] };
  }
  if (prompt.startsWith("Write the slide content")) {
    // only ever writes the first slide it was asked for — no error, just short
    return { slides: [{ slide_id: "x1", role: "content", blocks: [{ slot: "title", kind: "text", content: "X1", sources: ["proc#s0"] }] }] };
  }
  if (prompt.startsWith("Write exactly")) {
    return { questions: [{ question_id: "Q1", objective_id: "LO1", type: "mcq", stem: "s",
      options: [{ option_id: "a", text: "A" }, { option_id: "b", text: "B" }, { option_id: "c", text: "C" }, { option_id: "d", text: "D" }],
      key: ["a"], rationale: "r", bloom_level: "apply", audience_ids: ["a"], sources: ["proc#s0"] }] };
  }
  throw new Error("unrecognized prompt: " + prompt.slice(0, 80));
}
const shortResult = await generatePlan(bigCorpus, { sampleJson: shortReplyMock, questionCount: 1 });
const shortMod = shortResult.plan.modules.find((m) => m.module_id === "mod-short");
for (const slide of shortMod.slides) {
  if (!Array.isArray(slide.blocks) || slide.blocks.length === 0) {
    console.log(`FAIL: slide ${slide.slide_id} has no blocks — a content-free slide leaked through`, slide);
    process.exit(1);
  }
}
const x2 = shortMod.slides.find((s) => s.slide_id === "x2");
if (!x2._placeholder) { console.log("FAIL: expected the never-returned x2 to be a placeholder", x2); process.exit(1); }
console.log("  short reply -> x1 real, x2 is a flagged placeholder with real blocks (never blocks-less) OK");

console.log("\nAll short-reply checks passed.");
