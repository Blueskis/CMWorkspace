/**
 * Unit tests for plan.js's opt-in "annotate" stage inside generatePlan() — mocked
 * sampleJson, same style as test/plan.mjs's other generatePlan coverage. Exercises: the
 * toggle actually gating the stage, images/cache being passed to the sample call, the
 * redact-flattens-the-asset-and-repoints-the-block path, whole-set-dropped-on-validation-
 * failure, a single screenshot's failure not aborting the run, and resume skipping
 * already-annotated slides.
 *
 *   node test/plan-annotate.mjs
 */
import { readFileSync } from "node:fs";
import { generatePlan } from "../src/plan.js";

let failures = 0;
function check(label, cond, detail = "") {
  if (cond) console.log(`  ok  ${label}`);
  else { failures++; console.log(`  FAIL ${label} ${detail}`); }
}

const screenshot = readFileSync("test/fixtures/screenshot.png");

function corpusWith(assetIds) {
  return {
    documents: [{ document_id: "fsd" }],
    sections: [{ section_id: "s1", section_path: "4.2", text: "Click Approve to complete the request.", classifier: "procedure", char_count: 40 }],
    assets: assetIds.map((id) => ({ asset_id: id, bytes: screenshot, ext: "png", format: "png", role: "screenshot", section_id: "s1", alt_text: "w" })),
    notes: [],
  };
}

const BRIEF_REPLY = { audiences: [{ audience_id: "a1", name: "Requesters" }], learning_objectives: [{ lo_id: "LO1", text: "Approve a request", audience_ids: ["a1"] }], scope_notes: "" };
const QUESTIONS_REPLY = { questions: [{ question_id: "Q1", objective_id: "LO1", type: "mcq", prompt: "p", options: [{ option_id: "a", text: "x" }, { option_id: "b", text: "y" }, { option_id: "c", text: "z" }, { option_id: "d", text: "w" }], key: ["a"], sources: ["s1"] }] };

function oneSlideModulePlan(slideIds) {
  return { modules: [{ module_id: "m1", title: "t", order: 1, objective_ids: ["LO1"], slides: slideIds.map((id) => ({ slide_id: id, role: "content" })) }] };
}

function slideCopyReplyFor(slideId, assetId, bullets = ["Open the worklist", "Click Approve"]) {
  return {
    slides: [{
      slide_id: slideId, role: "content",
      blocks: [
        { slot: "title", kind: "text", content: "Approve the Request", sources: ["s1"] },
        { slot: "body", kind: "bullets", content: bullets, sources: ["s1"] },
        { slot: "picture", kind: "image", content: { asset_id: assetId, caption: "Worklist" }, sources: ["s1"] },
      ],
    }],
  };
}

// ---------------------------------------------------------------------------
// 1. Toggle off: no annotate stage, no annotate calls, no annotations on any block
// ---------------------------------------------------------------------------
{
  let annotateCalls = 0;
  const stages = [];
  const sampleJson = async (prompt) => {
    if (prompt.startsWith("You are drafting the intake brief")) return BRIEF_REPLY;
    if (prompt.startsWith("You are planning the module")) return oneSlideModulePlan(["s1"]);
    if (prompt.startsWith("Write the slide content")) return slideCopyReplyFor("s1", "img1");
    if (prompt.startsWith("Look at the attached screenshot")) { annotateCalls++; return { annotations: [], skipped: [] }; }
    if (prompt.startsWith("Write exactly")) return QUESTIONS_REPLY;
    throw new Error("unexpected prompt: " + prompt.slice(0, 60));
  };
  const result = await generatePlan(corpusWith(["img1"]), {
    sampleJson, annotate: false, questionCount: 1, onStage: (s) => stages.push(s),
  });
  check("toggle off: 'annotate' stage never runs", !stages.includes("annotate"), JSON.stringify(stages));
  check("toggle off: no annotate calls made", annotateCalls === 0);
  const imgBlock = result.plan.modules[0].slides[0].blocks.find((b) => b.kind === "image");
  check("toggle off: image block has no annotations", !imgBlock.content.annotations);
}

// ---------------------------------------------------------------------------
// 2. Toggle on: the annotate call carries images and disables caching (each screenshot is
//    unique context, so a stale replay would be wrong)
// ---------------------------------------------------------------------------
{
  let sawImages = false, sawCacheFalse = false;
  const sampleJson = async (prompt, opts) => {
    if (prompt.startsWith("You are drafting the intake brief")) return BRIEF_REPLY;
    if (prompt.startsWith("You are planning the module")) return oneSlideModulePlan(["s1"]);
    if (prompt.startsWith("Write the slide content")) return slideCopyReplyFor("s1", "img1");
    if (prompt.startsWith("Look at the attached screenshot")) {
      sawImages = !!opts.images;
      sawCacheFalse = opts.cache === false;
      return { annotations: [{ type: "callout", point: [0.5, 0.5], step: 1 }, { type: "callout", point: [0.4, 0.4], step: 2 }], skipped: [] };
    }
    if (prompt.startsWith("Write exactly")) return QUESTIONS_REPLY;
    throw new Error("unexpected prompt: " + prompt.slice(0, 60));
  };
  const result = await generatePlan(corpusWith(["img1"]), { sampleJson, annotate: true, questionCount: 1 });
  check("toggle on: sample call carries images", sawImages);
  check("toggle on: sample call passes cache:false", sawCacheFalse);
  const imgBlock = result.plan.modules[0].slides[0].blocks.find((b) => b.kind === "image");
  check("toggle on: annotations attached to the block", imgBlock.content.annotations.length === 2);
}

// ---------------------------------------------------------------------------
// 3. A "redact" annotation flattens the asset and repoints the block's asset_id
// ---------------------------------------------------------------------------
{
  const sampleJson = async (prompt) => {
    if (prompt.startsWith("You are drafting the intake brief")) return BRIEF_REPLY;
    if (prompt.startsWith("You are planning the module")) return oneSlideModulePlan(["s1"]);
    if (prompt.startsWith("Write the slide content")) return slideCopyReplyFor("s1", "img1");
    if (prompt.startsWith("Look at the attached screenshot")) {
      return { annotations: [{ type: "redact", rect: [0.05, 0.05, 0.1, 0.05], reason: "vendor code" }], skipped: [] };
    }
    if (prompt.startsWith("Write exactly")) return QUESTIONS_REPLY;
    throw new Error("unexpected prompt: " + prompt.slice(0, 60));
  };
  const result = await generatePlan(corpusWith(["img1"]), { sampleJson, annotate: true, questionCount: 1 });
  const imgBlock = result.plan.modules[0].slides[0].blocks.find((b) => b.kind === "image");
  check("redact: block repointed to a NEW flattened asset, not the original", imgBlock.content.asset_id === "img1-r1");
  check("redact: derivedAssets carries the new asset", result.derivedAssets.some((a) => a.asset_id === "img1-r1"));
  const derived = result.derivedAssets.find((a) => a.asset_id === "img1-r1");
  check("redact: derived asset records redacted_from", derived.redacted_from === "img1");
}

// ---------------------------------------------------------------------------
// 4. Invalid step binding: the whole annotation set is dropped, never partially trusted
// ---------------------------------------------------------------------------
{
  const sampleJson = async (prompt) => {
    if (prompt.startsWith("You are drafting the intake brief")) return BRIEF_REPLY;
    if (prompt.startsWith("You are planning the module")) return oneSlideModulePlan(["s1"]);
    if (prompt.startsWith("Write the slide content")) return slideCopyReplyFor("s1", "img1", ["Step A", "Step B"]);
    if (prompt.startsWith("Look at the attached screenshot")) return { annotations: [{ type: "callout", point: [0.4, 0.3], step: 5 }], skipped: [] };
    if (prompt.startsWith("Write exactly")) return QUESTIONS_REPLY;
    throw new Error("unexpected prompt: " + prompt.slice(0, 60));
  };
  const result = await generatePlan(corpusWith(["img1"]), { sampleJson, annotate: true, questionCount: 1 });
  const imgBlock = result.plan.modules[0].slides[0].blocks.find((b) => b.kind === "image");
  check("invalid step binding: annotations NOT attached", !imgBlock.content.annotations);
  check("invalid step binding: a warning was recorded", result.warnings.some((w) => w.includes("failed validation")));
}

// ---------------------------------------------------------------------------
// 5. One screenshot's call failure doesn't abort the whole run
// ---------------------------------------------------------------------------
{
  let annotateCalls = 0;
  const sampleJson = async (prompt) => {
    if (prompt.startsWith("You are drafting the intake brief")) return BRIEF_REPLY;
    if (prompt.startsWith("You are planning the module")) return oneSlideModulePlan(["sA", "sB"]);
    if (prompt.startsWith("Write the slide content")) {
      return { slides: [
        { slide_id: "sA", role: "content", blocks: [{ slot: "body", kind: "bullets", content: ["Step A"], sources: ["s1"] }, { slot: "picture", kind: "image", content: { asset_id: "img1" }, sources: ["s1"] }] },
        { slide_id: "sB", role: "content", blocks: [{ slot: "body", kind: "bullets", content: ["Step B"], sources: ["s1"] }, { slot: "picture", kind: "image", content: { asset_id: "img2" }, sources: ["s1"] }] },
      ] };
    }
    if (prompt.startsWith("Look at the attached screenshot")) {
      annotateCalls++;
      if (annotateCalls === 2) { const err = new Error("rate limited"); err.code = "rate_limited"; throw err; }
      return { annotations: [{ type: "callout", point: [0.4, 0.3], step: 1 }], skipped: [] };
    }
    if (prompt.startsWith("Write exactly")) return QUESTIONS_REPLY;
    throw new Error("unexpected prompt: " + prompt.slice(0, 60));
  };
  const result = await generatePlan(corpusWith(["img1", "img2"]), { sampleJson, annotate: true, questionCount: 1 });
  check("one screenshot failing: run still reaches 'done' (no throw)", !!result.plan);
  check("one screenshot failing: a warning was recorded for it", result.warnings.some((w) => w.includes("rate_limited")));
}

// ---------------------------------------------------------------------------
// 6. Resume: an already-annotated slide is skipped, no re-call
// ---------------------------------------------------------------------------
{
  let annotateCalls = 0;
  const resume = {
    brief: BRIEF_REPLY,
    moduleSkeletons: oneSlideModulePlan(["s1"]).modules,
    modules: [{ module_id: "m1", title: "t", order: 1, objective_ids: ["LO1"], slides: slideCopyReplyFor("s1", "img1").slides }],
    annotatedSlideIds: ["s1"],
  };
  const sampleJson = async (prompt) => {
    if (prompt.startsWith("Look at the attached screenshot")) { annotateCalls++; return { annotations: [], skipped: [] }; }
    if (prompt.startsWith("Write exactly")) return QUESTIONS_REPLY;
    throw new Error("unexpected prompt: " + prompt.slice(0, 60));
  };
  await generatePlan(corpusWith(["img1"]), { sampleJson, annotate: true, questionCount: 1, resume });
  check("resume: already-annotated slide is not re-called", annotateCalls === 0);
}

console.log(failures ? `\n${failures} FAILURE(S)` : "\nAll plan.js annotate-stage checks passed.");
process.exit(failures ? 1 : 0);
