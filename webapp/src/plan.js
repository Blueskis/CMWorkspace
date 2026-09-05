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

// slideCopyPrompt asks for full content (title + bullets + speaker_notes + any diagram
// spec) for EVERY slide in a module, in one reply — chunkSections only bounds the INPUT
// side (source section text), not this OUTPUT side. A module the module-plan stage packed
// with many slides (a dense mass-processing module, say) can still demand a reply long
// enough to hit the length limit mid-JSON, which surfaces as invalid_json's "cut short"
// variant — a real failure hit in production, not a hypothetical. Capping slides per call
// bounds the output the same way chunkSections already bounds the input.
const MAX_SLIDES_PER_CALL = 4;

// Stable marker lines around each prompt's worked example — every example block must be
// literal, JSON.parse-able JSON (see test/plan.mjs's "example blocks are valid JSON"
// guard). These markers exist purely so tests can locate and extract that block; they are
// not JSON syntax and are never mistaken for it because they sit outside the braces.
const EXAMPLE_START = "--- EXAMPLE (shape only — write real content) ---";
const EXAMPLE_END = "--- END EXAMPLE ---";

/** Pull the JSON example out of a prompt built with EXAMPLE_START/EXAMPLE_END markers. */
export function extractExample(promptText) {
  const start = promptText.indexOf(EXAMPLE_START);
  const end = promptText.indexOf(EXAMPLE_END);
  if (start === -1 || end === -1 || end <= start) return null;
  return promptText.slice(start + EXAMPLE_START.length, end).trim();
}

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

Return ONLY a JSON object shaped exactly like this example — your entire reply must be
the JSON value alone, with no explanation, preamble, or commentary before or after it.
Use the example only to see the shape; write real content drawn from the outline below.

${EXAMPLE_START}
{
  "system": "Supplier Block/Unblock",
  "process_scope": "Covers how requesters submit and approvers process supplier block and unblock requests. Does not cover supplier master data creation.",
  "audiences": [
    {"audience_id": "requester", "role_name": "AP Requester", "tasks": ["submit a block request", "attach supporting documents"]}
  ],
  "learning_objectives": [
    {"lo_id": "LO1", "text": "Submit a supplier block request with required documentation", "bloom_level": "apply", "audience_ids": ["requester"], "sources": ["doc#4.2"]}
  ],
  "out_of_scope": [
    {"section_id": "doc#7.1", "reason": "Covers supplier master creation, which is a separate training"}
  ]
}
${EXAMPLE_END}

Field notes:
- "system": name of the system/process this trains.
- "process_scope": 1-2 sentences on what this training covers and does not.
- "audiences[].audience_id": short, kebab-case.
- "learning_objectives[].lo_id": sequential "LO1", "LO2", ... "LOn".
- "learning_objectives[].text": an observable verb, not "understand".
- "learning_objectives[].bloom_level": one of "remember", "understand", "apply", "analyze", "evaluate", "create".
- "learning_objectives[].sources": must be real section_ids from the outline below.
- "out_of_scope": every section classified "procedure" below that you do NOT plan to
  teach MUST appear here with a reason — this is checked mechanically, so do not omit one.

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

Return ONLY a JSON object shaped exactly like this example — your entire reply must be
the JSON value alone, no explanation before or after it. Use the example only to see the
shape; write real modules and slides drawn from the brief and outline above.

${EXAMPLE_START}
{
  "modules": [
    {
      "module_id": "cover",
      "title": "Cover",
      "order": 1,
      "objective_ids": [],
      "slides": [
        {"slide_id": "cover-1", "role": "title-slide", "title": "Supplier Block/Unblock Training"}
      ]
    },
    {
      "module_id": "mod-lo1",
      "title": "Submitting a Block Request",
      "order": 2,
      "objective_ids": ["LO1"],
      "slides": [
        {"slide_id": "s-lo1-1", "role": "content", "title": "Submitting a Block Request"},
        {"slide_id": "s-lo1-2", "role": "diagram", "title": "Approval Workflow"}
      ]
    }
  ]
}
${EXAMPLE_END}

Field notes:
- "module_id": kebab-case, unique.
- "objective_ids": lo_id values from the brief; [] for non-LO modules like welcome/summary.
- "slides[].role": one of "title-slide", "section-header", "content", "two-content",
  "picture", "diagram".

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
     A screenshot can go two ways — pick per step, not by a blanket rule: use role "content"
     (screenshot placed beside 3-5 short bullets, composed side by side automatically) when
     the step's explanation is short enough to sit next to the image; use role "picture"
     (screenshot fills the slide) when the screenshot itself needs the room — a dense form
     with many fields, a full launchpad/worklist view, or a screen the learner must read in
     detail. Use "diagram" for any conditional/branching logic ("if X then Y") described in
     prose.
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

Return ONLY a JSON object shaped exactly like this example — your entire reply must be
the JSON value alone, no explanation before or after it. Use the example only to see the
shape; write real slide content drawn only from the source sections above.

${EXAMPLE_START}
{
  "slides": [
    {
      "slide_id": "s-lo1-1",
      "role": "content",
      "speaker_notes": "Walk through the request form field by field.",
      "blocks": [
        {"slot": "title", "kind": "text", "content": "Submitting a Block Request", "sources": ["doc#4.2"]},
        {"slot": "body", "kind": "bullets", "content": ["Open the Supplier Block form", "Enter the supplier ID", "Attach the block reason"], "sources": ["doc#4.2"]},
        {"slot": "body", "kind": "diagram", "content": {"diagram_type": "process", "spec": {"steps": ["Requester submits", "Approver reviews", "System blocks supplier"]}}, "sources": ["doc#4.2"]}
      ]
    },
    {
      "slide_id": "s-lo1-2",
      "role": "content",
      "media_position": "right",
      "blocks": [
        {"slot": "title", "kind": "text", "content": "Reviewing the Request", "sources": ["doc#4.2"]},
        {"slot": "body", "kind": "bullets", "content": ["Open the request from the worklist", "Check the reason code", "Approve or reject"], "sources": ["doc#4.2"]},
        {"slot": "picture", "kind": "image", "content": {"asset_id": "img-review-1", "caption": "Review screen"}, "sources": ["doc#4.2"]}
      ]
    }
  ]
}
${EXAMPLE_END}

One entry per slide in the module, in order. Field notes:
- "slide_id" and "role": copy from the module plan.
- "media_position": optional, top level alongside "slide_id" — "left" | "right" | "below" —
  overrides the automatic default (media on the right) for how this slide's media block
  sits beside its text block when both are present.
- "speaker_notes": optional, one line.
- "blocks[].slot": "title", "body", "body2", "picture", or "caption".
- A "content"-role slide's blocks MAY include both a "body" bullets block and a
  "picture" (or a second "body"-slotted diagram) block — these are composed side by side
  automatically, no separate placeholder needed. Keep bullets to 3-5 short items when a
  slide also carries a picture/diagram; a slide with only a body block can run longer.
  Place a "caption" block immediately after the image/diagram block it captions.
- "blocks[].kind" and "content" pair up as:
  - "text": content is a string (used for the title block).
  - "bullets": content is an array of strings, each <=10 words.
  - "table": content is {"headers": [string, ...], "rows": [[string, ...], ...]}.
  - "image": content is {"asset_id": string, "caption": string} — asset_id MUST be
    from the screenshot list above.
  - "diagram": content is {"diagram_type": ..., "spec": ...} — diagram_type is one of
    "process", "swimlane", "decision", "hierarchy", "timeline", and spec is shaped
    to match: process -> {"steps": [string, ...]}; swimlane -> {"roles": [string, ...],
    "steps": [{"step": string, "role": string}, ...]}; decision -> {"rules":
    [{"condition": string, "outcome": string}, ...]}; hierarchy -> {"root": {"name":
    string, "children": [{"name": string, "children": []}]}}; timeline -> {"milestones":
    [{"label": string, "date": string}, ...]}.

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

Return ONLY a JSON object shaped exactly like this example, with exactly ${count}
entries in "questions" — your entire reply must be the JSON value alone, no explanation
before or after it. Use the example only to see the shape; write real questions drawn
only from the source text above.

${EXAMPLE_START}
{
  "questions": [
    {
      "question_id": "Q1",
      "objective_id": "LO1",
      "type": "mcq",
      "stem": "A requester submits a block request without an attached reason. What happens next?",
      "options": [
        {"option_id": "a", "text": "The system rejects the submission"},
        {"option_id": "b", "text": "The approver is notified anyway"},
        {"option_id": "c", "text": "The request is auto-approved"},
        {"option_id": "d", "text": "The supplier is deleted"}
      ],
      "key": ["a"],
      "rationale": "Section doc#4.2 states the reason field is required before submission.",
      "bloom_level": "apply",
      "audience_ids": ["requester"],
      "sources": ["doc#4.2"]
    },
    {
      "question_id": "Q2",
      "objective_id": "LO1",
      "type": "true-false",
      "stem": "An approver can unblock a supplier without a business justification.",
      "options": [
        {"option_id": "t", "text": "True"},
        {"option_id": "f", "text": "False"}
      ],
      "key": ["f"],
      "rationale": "Section doc#4.2 requires a justification for every unblock.",
      "bloom_level": "understand",
      "audience_ids": ["requester"],
      "sources": ["doc#4.2"]
    }
  ]
}
${EXAMPLE_END}

Field notes:
- "question_id": "Q1".."Q${count}" — sequential, one per entry.
- "type": "mcq" or "true-false".
- "stem": test the task, not trivia — put the learner in the situation and ask what
  happens or what to do, not "what is X called".
- "options": mcq needs exactly 4 (one correct plus 3 plausible distractors drawn from
  adjacent content in the source, never an obviously-wrong throwaway); true-false needs
  exactly 2, with text "True"/"False".
- "key": exactly one option_id.
- "rationale": why the key is correct, citing the source.
- "bloom_level": from the matching objective.
- "sources": must be real section_ids; the answer must actually be stated there.

Mix types across the ${count} questions rather than using only one type. Spread questions
across different objectives rather than clustering on one.`;
}

// ---------------------------------------------------------------------------
// salvage — recovering a value from a reply the platform's own tolerant JSON
// reader rejected (invalid_json). Never throws; returns null when nothing usable
// can be recovered. See sample.d.ts: the platform already tries the whole reply,
// then one Markdown fence body, then first-`{`/`[`-to-last-`}`/`]` — the case this
// exists for is everything past that: two JSON values in one reply (the platform
// refuses those on purpose), or a reply cut off mid-value.
// ---------------------------------------------------------------------------

function safeJsonParse(text) {
  try {
    return JSON.parse(text);
  } catch {
    return undefined; // sentinel for "did not parse" — JSON.parse never itself yields undefined
  }
}

const FENCE_RE = /```(?:[A-Za-z0-9_-]*)?\s*\n?([\s\S]*?)```/g;

/** Every top-level balanced {...} / [...] span in `text`, string-literal-aware. */
function findBalancedSpans(text) {
  const spans = [];
  const n = text.length;
  let i = 0;
  while (i < n) {
    const c = text[i];
    if (c === "{" || c === "[") {
      let depth = 0;
      let inString = false;
      let escape = false;
      let j = i;
      for (; j < n; j++) {
        const cj = text[j];
        if (inString) {
          if (escape) escape = false;
          else if (cj === "\\") escape = true;
          else if (cj === '"') inString = false;
          continue;
        }
        if (cj === '"') { inString = true; continue; }
        if (cj === "{" || cj === "[") depth++;
        else if (cj === "}" || cj === "]") {
          depth--;
          if (depth === 0) break;
        }
      }
      if (depth === 0 && j < n) {
        spans.push(text.slice(i, j + 1));
        i = j + 1;
        continue;
      }
    }
    i++;
  }
  return spans;
}

/** String-literal-aware scan of the open-bracket stack and whether `s` ends inside a string. */
function scanBracketState(s) {
  const stack = [];
  let inString = false;
  let escape = false;
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (inString) {
      if (escape) escape = false;
      else if (c === "\\") escape = true;
      else if (c === '"') inString = false;
      continue;
    }
    if (c === '"') { inString = true; continue; }
    if (c === "{" || c === "[") stack.push(c);
    else if (c === "}" || c === "]") stack.pop();
  }
  return { stack, inString };
}

/** Last resort: the reply was cut off mid-value. Trim back a bounded amount and close
 * whatever brackets (and string) were left open. */
function tryCloseUnterminated(text) {
  const start = text.search(/[{[]/);
  if (start === -1) return undefined;
  const s = text.slice(start);

  // Only a genuinely unterminated span (still inside a string, or with brackets left
  // open at the very end) is a "cut short" case worth closing. A span that is already
  // bracket-balanced but still fails to parse is invalid JSON, not a truncated one —
  // trimming characters off a balanced-but-malformed span (e.g. a pseudo-JSON template
  // echo) can "recover" a trivial, meaningless value like `{}`, which is worse than
  // reporting no recovery at all.
  const fullState = scanBracketState(s);
  if (fullState.stack.length === 0 && !fullState.inString) return undefined;

  const maxTrim = Math.min(s.length, 500);
  for (let trim = 0; trim <= maxTrim; trim++) {
    const candidate = trim === 0 ? s : s.slice(0, s.length - trim);
    if (!candidate) break;
    const { stack, inString } = scanBracketState(candidate);
    let repaired = candidate;
    if (inString) repaired += '"';
    repaired = repaired.replace(/[,:\s]+$/, "");
    for (let k = stack.length - 1; k >= 0; k--) repaired += stack[k] === "{" ? "}" : "]";
    const attempt = safeJsonParse(repaired);
    if (attempt !== undefined) return attempt;
  }
  return undefined;
}

/**
 * Try to recover a JSON value from a raw reply the platform's own reader rejected.
 * Returns the parsed value, or `null` when nothing usable can be recovered. Never throws.
 */
export function tryRepairJson(text) {
  if (typeof text !== "string" || !text.trim()) return null;

  let attempt = safeJsonParse(text);
  if (attempt !== undefined) return attempt;

  FENCE_RE.lastIndex = 0;
  let m;
  while ((m = FENCE_RE.exec(text))) {
    attempt = safeJsonParse(m[1]);
    if (attempt !== undefined) return attempt;
  }

  const spans = findBalancedSpans(text).sort((a, b) => b.length - a.length);
  for (const span of spans) {
    attempt = safeJsonParse(span);
    if (attempt !== undefined) return attempt;
  }

  attempt = tryCloseUnterminated(text);
  if (attempt !== undefined) return attempt;

  return null;
}

/**
 * The one place every stage calls into `sample.json`. Additive only: the happy path is
 * unchanged. On an `invalid_json` rejection, attempt `tryRepairJson` on the raw reply
 * (`e.text`) before giving up — this is what recovers the "two JSON values in one reply"
 * case the platform itself refuses to parse, and the "cut short" case. Only rethrows
 * (keeping `e.text` intact) when repair also fails.
 */
async function callSampleJson(sampleJson, prompt, opts) {
  try {
    return await sampleJson(prompt, opts);
  } catch (e) {
    if (e && typeof e === "object" && e.code === "invalid_json" && typeof e.text === "string") {
      const repaired = tryRepairJson(e.text);
      if (repaired !== null) return repaired;
    }
    throw e;
  }
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
 *   resume — { brief?, moduleSkeletons?, modules?, questions? }: stages already
 *     completed by a PRIOR failed run, to skip re-asking. Every sample() failure is one
 *     independent call that costs the viewer real usage and real time (30-90s is
 *     typical); a viewer who hits a failure on, say, the questions stage should not have
 *     to re-sit through brief/module-plan/slide-copy succeeding again identically on
 *     retry. On throw, generatePlan attaches whatever it completed to `error.progress`
 *     in this same shape — callers should stash it and pass it back in as `resume` on
 *     the next attempt (see ui.js's runGenerate/renderError for the reference caller).
 */
export async function generatePlan(corpus, {
  sampleJson,
  questionCount = 5,
  onStage = () => {},
  resume = {},
} = {}) {
  if (!sampleJson) throw new Error("generatePlan requires a sampleJson function");

  let brief = resume.brief ?? null;
  let moduleSkeletons = resume.moduleSkeletons ?? null;
  const modules = resume.modules ? [...resume.modules] : [];
  let questions = resume.questions ?? null;

  try {
    if (!brief) {
      onStage("brief");
      brief = await callSampleJson(sampleJson, briefPrompt(corpus), { modelTier: MODEL_TIER });
      validateBrief(brief);
    }

    if (!moduleSkeletons) {
      onStage("module-plan");
      ({ modules: moduleSkeletons } = await callSampleJson(sampleJson, modulePlanPrompt(corpus, brief), { modelTier: MODEL_TIER }));
      if (!Array.isArray(moduleSkeletons) || moduleSkeletons.length === 0) {
        throw new Error("Module plan came back empty — try again, or check the source documents parsed correctly.");
      }
    }

    onStage("slide-copy");
    const sectionsById = Object.fromEntries(corpus.sections.map((s) => [s.section_id, s]));
    // slides already written for a module on a prior attempt (from e.progress.modules) —
    // batch-level, not just module-level, so a large module's 3rd-of-5 batch failing
    // doesn't throw away the 2 that already succeeded on retry.
    const doneSlideIdsByModule = new Map(modules.map((m) => [m.module_id, new Set(m.slides.map((s) => s.slide_id))]));
    for (const mod of moduleSkeletons) {
      if (!mod.slides.length) { // an edge case, not the common path: a module the model gave no slides at all
        if (!modules.find((m) => m.module_id === mod.module_id)) modules.push({ ...mod, slides: [] });
        continue;
      }
      const alreadyDone = doneSlideIdsByModule.get(mod.module_id) ?? new Set();
      const remaining = mod.slides.filter((s) => !alreadyDone.has(s.slide_id));
      if (!remaining.length) continue; // this module was fully completed already (or has no slides to begin with)

      // Sections this module actually needs: whatever its slides will plausibly cite —
      // approximated here as every section under the objectives it serves, which keeps
      // the call's input bounded without the model having to ask a follow-up.
      const relevant = relevantSections(mod, brief, corpus.sections);
      const inputChunks = chunkSections(relevant);
      // Cap OUTPUT per call too: batch the module's own slide list, independent of the
      // input chunking above, so a module with many slides never asks for all of their
      // content in one reply (see MAX_SLIDES_PER_CALL's own comment for why this matters).
      for (let i = 0; i < remaining.length; i += MAX_SLIDES_PER_CALL) {
        const slideBatch = remaining.slice(i, i + MAX_SLIDES_PER_CALL);
        const batchMod = { ...mod, slides: slideBatch };
        let batchSlides = [];
        for (const chunk of inputChunks) {
          const resp = await callSampleJson(sampleJson, slideCopyPrompt(batchMod, chunk, corpus), { modelTier: MODEL_TIER });
          batchSlides = batchSlides.concat(resp.slides ?? []);
        }
        batchSlides = dedupeSlides(batchSlides.length ? batchSlides : slideBatch);
        // Record this batch's slides into `modules` (the array e.progress captures on
        // throw) immediately, not after the whole module finishes — a later batch's
        // failure must not discard this one.
        let entry = modules.find((m) => m.module_id === mod.module_id);
        if (!entry) { entry = { ...mod, slides: [] }; modules.push(entry); }
        entry.slides = dedupeSlides(entry.slides.concat(batchSlides));
      }
    }

    if (!questions) {
      onStage("questions");
      questions = await generateQuestions(sampleJson, brief, corpus, questionCount);
      validateQuestions(questions, questionCount);
    }

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
  } catch (e) {
    if (e && typeof e === "object") e.progress = { brief, moduleSkeletons, modules, questions };
    throw e;
  }
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
    return callSampleJson(sampleJson, questionsPrompt(brief, procedureSections, count), { modelTier: MODEL_TIER });
  }
  const all = [];
  for (let i = 0; i < chunks.length; i++) {
    const n = Math.max(1, Math.round((count * (i + 1)) / chunks.length) - Math.round((count * i) / chunks.length));
    const resp = await callSampleJson(sampleJson, questionsPrompt(brief, chunks[i], n), { modelTier: MODEL_TIER });
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
