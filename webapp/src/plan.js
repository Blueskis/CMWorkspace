/**
 * Turn a parsed document corpus into a deck plan, via four staged calls to Claude.
 *
 * There is no Python equivalent to port: in a Claude Code session, planning and writing
 * IS the model working directly over the whole document in its own context. Here that
 * has to become explicit, bounded API calls, because `sample` caps input at 64 KiB per
 * call (see sample.d.ts) and the model has no memory between calls. So the FSD's own
 * stage boundaries (brief -> module plan -> slide content -> questions) become the
 * staging boundaries: each call gets only what it needs, never the whole document.
 *
 * Every prompt-building function here is pure and independently testable (test/plan.mjs
 * mocks the sampler and checks each prompt's byte budget and each response's shape). Only
 * `sample.json` itself cannot run outside a published artifact.
 *
 * The provenance rule carries over unchanged: every prompt requires every content block
 * to cite real section_ids, and qa.js — not this file — is the enforcement, exactly as
 * qa_training.py enforces it downstream of the Python pipeline's own writing stage.
 */

const MAX_INPUT_BYTES = 60 * 1024; // sample's cap is 64 KiB; leave headroom for instructions
const MODEL_TIER = "complex"; // this is drafting work, not a quick lookup

function byteLength(s) {
  return new TextEncoder().encode(s).length;
}

/** Split a module's sections into <=maxBytes chunks without splitting a section in two. */
export function chunkSections(sections, maxBytes = MAX_INPUT_BYTES) {
  const chunks = [];
  let current = [];
  let currentBytes = 0;
  for (const s of sections) {
    const size = byteLength(JSON.stringify(s));
    if (size > maxBytes) {
      // A single section bigger than the whole budget: truncate its text and flag it —
      // never silently drop it, per the plan's own stated risk-handling.
      const truncated = { ...s, text: s.text.slice(0, Math.floor(maxBytes * 0.6)) + " …[truncated]", _truncated: true };
      if (current.length) { chunks.push(current); current = []; currentBytes = 0; }
      chunks.push([truncated]);
      continue;
    }
    if (currentBytes + size > maxBytes && current.length) {
      chunks.push(current);
      current = [];
      currentBytes = 0;
    }
    current.push(s);
    currentBytes += size;
  }
  if (current.length) chunks.push(current);
  return chunks;
}

// ---------------------------------------------------------------------------
// Stage 1 — brief
// ---------------------------------------------------------------------------

function compactOutline(sections) {
  return sections.map((s) => ({
    section_id: s.section_id,
    section_path: s.section_path,
    classifier: s.classifier,
    preview: s.text.slice(0, 200),
  }));
}

export function briefPrompt(corpus) {
  const outline = compactOutline(corpus.sections);
  return `You are drafting the intake brief for a training deck, built from a functional
specification document (or similar). Below is the document's complete outline —
every section's id, path, classifier, and a short preview (not the full text).

Return ONLY a JSON object with this exact shape:
{
  "system": string (name of the system/process this trains),
  "process_scope": string (1-2 sentences: what this training covers and does not),
  "audiences": [{"audience_id": string (short, kebab-case), "role_name": string, "tasks": [string]}],
  "learning_objectives": [{"lo_id": "LO1"..."LOn", "text": string (observable verb, not "understand"),
    "bloom_level": "remember"|"understand"|"apply"|"analyze"|"evaluate"|"create",
    "audience_ids": [string], "sources": [section_id, ...] (must be real ids from the outline below)}],
  "out_of_scope": [{"section_id": string, "reason": string}]
    (every section classified "procedure" below that you do NOT plan to teach MUST appear here
     with a reason — this is checked mechanically, so do not omit one)
}

Rules:
- Never invent a procedure, field, or rule the outline doesn't support — if a section's
  preview is unclear, treat it cautiously rather than guessing at its content.
- Every "procedure"-classified section below must end up cited in some learning_objective's
  sources, or listed in out_of_scope with a reason. There is no third option.
- 4-7 learning objectives is a reasonable range for a single training deck; do not pad.

Document outline (${outline.length} sections):
${JSON.stringify(outline, null, 0)}`;
}

// ---------------------------------------------------------------------------
// Stage 2 — module plan
// ---------------------------------------------------------------------------

export function modulePlanPrompt(corpus, brief) {
  const outline = compactOutline(corpus.sections);
  const screenshotSections = corpus.assets
    .filter((a) => a.role === "screenshot")
    .map((a) => ({ asset_id: a.asset_id, section_id: a.section_id, caption: a.caption_candidate }));

  return `You are planning the module and slide outline for a training deck. You already
wrote this brief:
${JSON.stringify(brief, null, 0)}

The document outline (unchanged from the brief stage):
${JSON.stringify(outline, null, 0)}

Screenshots available to place, each already tied to the section it illustrates:
${JSON.stringify(screenshotSections, null, 0)}

Return ONLY a JSON object: {"modules": [...]}. Each module:
{
  "module_id": string (kebab-case), "title": string, "order": integer,
  "objective_ids": [lo_id, ...] (from the brief; [] for non-LO modules like welcome/summary),
  "slides": [{"slide_id": string, "role": one of
      "title-slide" | "section-header" | "content" | "two-content" | "picture" | "diagram",
    "title": string}]
}

Follow this canonical arc, using only the modules that earn their place (skip any whose
entry criteria the outline doesn't support — do not pad):
  1. cover (title-slide, always)
  2. welcome / why this is changing (content, if the outline shows a change driver)
  3. learning objectives (content, always, one slide listing every LO)
  4. process overview (diagram, if any procedure spans more than ~3 steps or multiple roles)
  5. key terms (content, only if the outline uses vocabulary a newcomer wouldn't have)
  6. roles and responsibilities (content or two-content, if more than one role touches the process)
  7. one task-walkthrough module PER named procedure, sized by how much the outline dwells on
     it — a section mentioned once earns a bullet inside a broader module, not its own module.
     Use "picture" slides for steps a screenshot is available for (see the list above); use
     "diagram" for any conditional/branching logic ("if X then Y") described in prose.
  8. exceptions and common errors (content or picture, if the outline documents error states)
  9. where to get help (content, always, one slide)
  10. summary and next steps (section-header, always)

Every "procedure" section from the brief's coverage (the ones NOT in out_of_scope) must be
reachable from some module's slides — this is checked mechanically.`;
}

// ---------------------------------------------------------------------------
// Stage 3 — slide copy (one call per module)
// ---------------------------------------------------------------------------

export function slideCopyPrompt(module, moduleSections, corpus) {
  const screenshots = corpus.assets.filter(
    (a) => a.role === "screenshot" && moduleSections.some((s) => s.section_id === a.section_id)
  );
  return `Write the slide content for one training module. Do not use anything you know
generally about this kind of system — write ONLY from the source text given below, and
cite the section_id every fact came from.

Module: ${JSON.stringify({ module_id: module.module_id, title: module.title, slides: module.slides })}

Source sections available to this module (their FULL text):
${JSON.stringify(moduleSections.map((s) => ({ section_id: s.section_id, section_path: s.section_path, text: s.text })), null, 0)}

Screenshots available for this module's "picture"-role slides:
${JSON.stringify(screenshots.map((a) => ({ asset_id: a.asset_id, section_id: a.section_id, caption: a.caption_candidate })), null, 0)}

Return ONLY a JSON object: {"slides": [...]} — one entry per slide in the module, in order:
{
  "slide_id": string, "role": (copy from the module plan),
  "speaker_notes": string (optional, one line),
  "blocks": [
    {"slot": "title", "kind": "text", "content": string, "sources": [section_id]},
    {"slot": "body"|"body2", "kind": "bullets", "content": [string, ...] (each <=10 words), "sources": [section_id,...]},
    {"slot": "body", "kind": "table", "content": {"headers": [string], "rows": [[string]]}, "sources": [...]},
    {"slot": "picture", "kind": "image", "content": {"asset_id": string, "caption": string}, "sources": [section_id]}
      (asset_id MUST be from the screenshot list above),
    {"slot": "body", "kind": "diagram", "content": {"diagram_type": "process"|"swimlane"|"decision"|"hierarchy"|"timeline",
      "spec": {...}}, "sources": [...]}
  ]
}

Diagram spec shapes:
  process:   {"steps": [string, ...]}
  swimlane:  {"roles": [string,...], "steps": [{"step": string, "role": string}, ...]}
  decision:  {"rules": [{"condition": string, "outcome": string}, ...]}
  hierarchy: {"root": {"name": string, "children": [{"name": string, "children": [...]}]}}
  timeline:  {"milestones": [{"label": string, "date": string}, ...]}

Rules:
- EVERY block must carry a non-empty "sources" array of real section_ids from the list
  above. If the source text genuinely does not answer something a slide needs, use
  {"gap": true, "gap_note": "what's missing"} on that block instead of guessing — never
  invent content to fill a gap.
- Bullets are terse (<=10 words); put the elaboration in speaker_notes instead.
- Field, screen, and role names come from the source text verbatim — never paraphrase a name.`;
}

// ---------------------------------------------------------------------------
// Stage 4 — questions
// ---------------------------------------------------------------------------

/**
 * @param {object[]} procedureSections  the procedure-classified sections to draw
 *   questions from — the caller's responsibility to chunk if this would exceed the
 *   byte budget (see generatePlan, which is the only real caller).
 */
export function questionsPrompt(brief, procedureSections, count) {
  return `Write exactly ${count} knowledge-check questions for this training, mixing
multiple-choice and true/false. Write ONLY from the source text below — every question's
answer must be stated in the section you cite as its source.

Learning objectives:
${JSON.stringify(brief.learning_objectives, null, 0)}

Procedure sections (their full text) to draw questions from:
${JSON.stringify(procedureSections.map((s) => ({ section_id: s.section_id, text: s.text })), null, 0)}

Return ONLY a JSON object: {"questions": [...]}, exactly ${count} entries:
{
  "question_id": "Q1".."Q${count}", "objective_id": lo_id, "type": "mcq"|"true-false",
  "stem": string (test the task, not trivia — put the learner in the situation and ask
    what happens or what to do, not "what is X called"),
  "options": [{"option_id": string, "text": string}]
    (mcq: exactly 4, one correct plus 3 plausible distractors drawn from adjacent content
     in the source, never an obviously-wrong throwaway; true-false: exactly 2, "True"/"False"),
  "key": [option_id] (exactly one entry),
  "rationale": string (why the key is correct, citing the source),
  "bloom_level": (from the matching objective), "audience_ids": [string],
  "sources": [section_id] (must be real ids; the answer must actually be stated there)
}

Mix types across the ${count} questions rather than using only one type. Spread questions
across different objectives rather than clustering on one.`;
}

// ---------------------------------------------------------------------------
// orchestration
// ---------------------------------------------------------------------------

/**
 * @param {object} corpus  { documents, sections, assets, notes } from parseSources()
 * @param {object} opts
 *   sampleJson(prompt, options) -> Promise<any>   — injected so tests can mock it;
 *     defaults to the real `sample.json` from claude.use("sample")
 *   questionCount, onStage(stageName)
 */
export async function generatePlan(corpus, {
  sampleJson,
  questionCount = 5,
  onStage = () => {},
} = {}) {
  if (!sampleJson) throw new Error("generatePlan requires a sampleJson function");

  onStage("brief");
  const brief = await sampleJson(briefPrompt(corpus), { modelTier: MODEL_TIER });
  validateBrief(brief);

  onStage("module-plan");
  const { modules: moduleSkeletons } = await sampleJson(modulePlanPrompt(corpus, brief), { modelTier: MODEL_TIER });
  if (!Array.isArray(moduleSkeletons) || moduleSkeletons.length === 0) {
    throw new Error("Module plan came back empty — try again, or check the source documents parsed correctly.");
  }

  onStage("slide-copy");
  const sectionsById = Object.fromEntries(corpus.sections.map((s) => [s.section_id, s]));
  const modules = [];
  for (const mod of moduleSkeletons) {
    // Sections this module actually needs: whatever its slides will plausibly cite —
    // approximated here as every section under the objectives it serves, which keeps
    // the call's input bounded without the model having to ask a follow-up.
    const relevant = relevantSections(mod, brief, corpus.sections);
    const chunks = chunkSections(relevant);
    let slides = [];
    for (const chunk of chunks) {
      const resp = await sampleJson(slideCopyPrompt(mod, chunk, corpus), { modelTier: MODEL_TIER });
      slides = slides.concat(resp.slides ?? []);
    }
    modules.push({ ...mod, slides: dedupeSlides(slides.length ? slides : mod.slides) });
  }

  onStage("questions");
  const questions = await generateQuestions(sampleJson, brief, corpus, questionCount);
  validateQuestions(questions, questionCount);

  onStage("done");
  return {
    brief,
    plan: {
      run_id: (corpus.documents[0]?.document_id ?? "run") + "-" + new Date().toISOString().slice(0, 10),
      brief_ref: "brief", modules, unused_assets: [],
    },
    questions,
    sectionsById,
  };
}

/**
 * Unlike every other stage, the original questions call had no chunking at all — it
 * dumped every procedure section's FULL text into one prompt. Harmless on the FSD this
 * was tested against (~11 KB), but any FSD with enough procedure content to cross the
 * 64 KiB cap would fail this call outright, with no fallback. Chunk the same way
 * slide-copy does, split the question count proportionally across chunks (at least one
 * each), then merge and renumber. Known tradeoff: trimming down to exactly `count` after
 * merging favours earlier chunks, so a very large FSD split across many chunks could
 * under-cover objectives whose only sources land in a later chunk — qa.js's coverage
 * check will surface that if it happens, rather than it failing silently.
 */
async function generateQuestions(sampleJson, brief, corpus, count) {
  const procedureSections = corpus.sections.filter((s) => s.classifier === "procedure");
  const chunks = chunkSections(procedureSections);
  if (chunks.length <= 1) {
    return sampleJson(questionsPrompt(brief, procedureSections, count), { modelTier: MODEL_TIER });
  }
  const all = [];
  for (let i = 0; i < chunks.length; i++) {
    const n = Math.max(1, Math.round((count * (i + 1)) / chunks.length) - Math.round((count * i) / chunks.length));
    const resp = await sampleJson(questionsPrompt(brief, chunks[i], n), { modelTier: MODEL_TIER });
    all.push(...(resp.questions ?? []));
  }
  return { questions: all.slice(0, count).map((q, i) => ({ ...q, question_id: `Q${i + 1}` })) };
}

function relevantSections(mod, brief, sections) {
  const los = new Set(mod.objective_ids ?? []);
  const wantedIds = new Set();
  for (const lo of brief.learning_objectives ?? []) {
    if (los.has(lo.lo_id)) (lo.sources ?? []).forEach((s) => wantedIds.add(s));
  }
  const matched = sections.filter((s) => wantedIds.has(s.section_id));
  return matched.length ? matched : sections.slice(0, 3); // non-LO modules (welcome, etc.)
}

function dedupeSlides(slides) {
  const seen = new Set();
  return slides.filter((s) => (seen.has(s.slide_id) ? false : (seen.add(s.slide_id), true)));
}

function validateBrief(brief) {
  if (!brief || !Array.isArray(brief.learning_objectives) || brief.learning_objectives.length === 0) {
    throw new Error("The brief came back without any learning objectives — try again.");
  }
  if (!Array.isArray(brief.audiences) || brief.audiences.length === 0) {
    throw new Error("The brief came back without any audiences — try again.");
  }
}

function validateQuestions(questions, count) {
  const qs = questions?.questions;
  if (!Array.isArray(qs) || qs.length !== count) {
    throw new Error(`Expected exactly ${count} questions, got ${qs?.length ?? 0}.`);
  }
  const types = new Set(qs.map((q) => q.type));
  if (types.size < 2 && count > 1) {
    // Not a hard failure — surfaced to the UI as a warning instead, since a genuinely
    // thin source document might not support a good true/false question everywhere.
    questions._warning = "All questions came back the same type despite the mixed-type instruction.";
  }
}
