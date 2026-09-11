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
// side (source section text), not this OUTPUT side, so a module packed with many slides
// can demand an unboundedly long reply. Capping slides per call bounds the output the
// same way chunkSections bounds the input, and makes each call's failure cheaper to retry.
//
// Honest history: this was originally added believing it fixed a reported invalid_json
// failure, on the evidence of a raw reply that looked cut off mid-JSON. It was not — that
// reply only LOOKED truncated because the error screen sliced it to 600 characters for
// display (see describeJsonFailure, which exists so that misreading can't recur). The real
// cause was malformed JSON in a complete reply. This cap is kept because bounding the
// output is right on its own merits, not because it fixed that bug.
const MAX_SLIDES_PER_CALL = 4;

// Stable marker lines around each prompt's worked example — every example block must be
// literal, JSON.parse-able JSON (see test/plan.mjs's "example blocks are valid JSON"
// guard). These markers exist purely so tests can locate and extract that block; they are
// not JSON syntax and are never mistaken for it because they sit outside the braces.
const EXAMPLE_START = "--- EXAMPLE (shape only — write real content) ---";
const EXAMPLE_END = "--- END EXAMPLE ---";

// The source documents genuinely contain quoted labels (BL99 "Legacy block - reason not
// recorded", the "Procurement" space) and multi-line passages. Copying one into a value
// without escaping it makes the whole reply unparseable and fails the run, so say so
// explicitly rather than relying on the model to get it right by default.
const JSON_HYGIENE = `Two rules about the JSON itself, because the source text below contains both:
- Escape every double quote inside a text value as \\" — the source quotes things like
  BL99 "Legacy block - reason not recorded", and an unescaped quote breaks the whole reply.
- Never put a real line break inside a value. Replace it with a space.`;

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

${JSON_HYGIENE}

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

${JSON_HYGIENE}

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

${JSON_HYGIENE}

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
- Field, screen, and role names come from the source text verbatim — never paraphrase a name.
- A "diagram" block's "content" is the deepest nesting in this whole reply — close it out
  fully before moving on: content -> spec -> its array(s) -> back out. For a "decision"
  diagram this closing sequence looks exactly like \`...]}},"sources":[...]}\` — three
  closes (array, spec, content) before "sources", which sits on the BLOCK, not inside
  "content". Finish one slide object completely, brace by brace, before starting the next
  one — a single missed "}" anywhere in this reply invalidates the entire batch.`;
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

${JSON_HYGIENE}

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

/**
 * Index of the matching close for the {/[ at text[i], scanning LOCALLY (depth starts
 * fresh at i) and string/escape-aware — or -1 if depth never returns to 0 before EOF.
 * "Locally" matters: a global brace deficit earlier in the text does not stop a
 * well-formed span starting after it from being found (see harvestSlides).
 */
function findSpanEnd(text, i) {
  const n = text.length;
  let depth = 0;
  let inString = false;
  let escape = false;
  for (let j = i; j < n; j++) {
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
      if (depth === 0) return j;
    }
  }
  return -1;
}

/** Every top-level balanced {...} / [...] span in `text`, string-literal-aware. */
function findBalancedSpans(text) {
  const spans = [];
  const n = text.length;
  let i = 0;
  while (i < n) {
    const c = text[i];
    if (c === "{" || c === "[") {
      const j = findSpanEnd(text, i);
      if (j !== -1) {
        spans.push(text.slice(i, j + 1));
        i = j + 1;
        continue;
      }
    }
    i++;
  }
  return spans;
}

function looksLikeSlide(v) {
  return !!v && typeof v === "object" && typeof v.slide_id === "string" && Array.isArray(v.blocks);
}

/** Parse a single candidate span as a slide, escalating through the sanitize passes
 * before giving up — a span damaged only by an unescaped quote or raw newline is still
 * harvestable, same as a whole-reply repair would recover it. */
function parseCandidateSlide(span) {
  let v = safeJsonParse(span);
  if (v !== undefined) return v;
  for (const pass of SANITIZE_PASSES) {
    v = safeJsonParse(sanitizeJsonText(span, pass));
    if (v !== undefined) return v;
  }
  return undefined;
}

/**
 * Recover individual slide objects out of a raw reply that failed to parse as a whole —
 * one dropped brace deep inside a diagram spec must not destroy every OTHER slide in the
 * same reply. De-duplicated by slide_id; when `wantedIds` is given, only slides matching
 * one of those ids are kept (guards against grabbing a slide-shaped object that belongs to
 * a different batch entirely, in the rare case a reply echoes stray content).
 *
 * Scanning rule, verified empirically: when a balanced span at `i` fails to parse (or
 * parses but isn't slide-shaped, or isn't a wanted id), resume scanning at i+1 — NOT at
 * the end of that span. A single dropped brace makes the span starting at the damaged
 * slide's own "{" swallow everything after it (looking for the depth-0 point it now
 * finds only near EOF); skipping past that swallowed span would skip every later slide
 * too. Continuing one character at a time instead lets the scan dive past the corrupted
 * span and pick up the next slide's own "{" directly.
 */
export function harvestSlides(text, wantedIds) {
  if (typeof text !== "string" || !text) return [];
  const wanted = wantedIds ? new Set(wantedIds) : null;
  const bySlideId = new Map();
  const n = text.length;
  let i = 0;
  while (i < n) {
    if (text[i] === "{") {
      const j = findSpanEnd(text, i);
      if (j !== -1) {
        const value = parseCandidateSlide(text.slice(i, j + 1));
        if (looksLikeSlide(value) && (!wanted || wanted.has(value.slide_id))) {
          if (!bySlideId.has(value.slide_id)) bySlideId.set(value.slide_id, value);
          i = j + 1;
          continue;
        }
      }
    }
    i++;
  }
  return [...bySlideId.values()];
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

/** Index of the next non-whitespace character at or after `i`, or text.length at EOF. */
function nextNonSpaceIndex(text, i) {
  while (i < text.length && /\s/.test(text[i])) i++;
  return i;
}
function nextNonSpace(text, i) {
  const j = nextNonSpaceIndex(text, i);
  return j < text.length ? text[j] : "";
}

/** Characters a JSON value may legally begin with. */
const VALUE_STARTS = /[-0-9"{[tfn]/;

/**
 * Decide whether the quote at `i` really ends the string, or is an unescaped quote inside
 * it. `stack` is the enclosing container chain ("{" or "[").
 *
 * A purely local rule ("closes if followed by , : } ]") is not good enough on the real
 * source text: the FSD contains `space "Procurement", page "Supplier Governance"`, where an
 * inner quote sits immediately before a comma and a local rule ends the string in the wrong
 * place. So for a comma, look past it — inside an object the next token must be the next
 * key (a quote), and inside an array it must be the start of a value. In that sentence the
 * comma is followed by ` page`, which is neither, so the quote is correctly read as content.
 */
function quoteClosesString(text, i, stack) {
  const nIdx = nextNonSpaceIndex(text, i + 1);
  const n = nIdx < text.length ? text[nIdx] : "";
  if (n === "" || n === ":" || n === "}" || n === "]") return true;
  if (n !== ",") return false; // a letter, digit or punctuation follows: an inner quote
  const after = nextNonSpace(text, nIdx + 1);
  if (after === "") return true;
  return stack[stack.length - 1] === "{"
    ? after === '"' // the next thing in an object must be a key
    : VALUE_STARTS.test(after);
}

/**
 * Re-emit `text` with the malformations a model actually produces repaired, string-aware.
 *
 * Each flag is a separate, escalating repair so the least invasive fix that works wins —
 * `quotes` in particular is a heuristic that can misfire (an inner quote that happens to
 * sit right before a comma reads as a closing quote), so it is only ever reached after
 * the safe passes have failed.
 *
 *  - controls: a raw newline or tab inside a string literal. The source FSD has 60 line
 *    breaks in its section text; copying a passage verbatim into a value produces these.
 *  - commas: a trailing comma before } or ].
 *  - quotes: an unescaped double quote inside a string value. The source text really does
 *    contain quoted labels (`BL99 "Legacy block - reason not recorded"`, the "Procurement"
 *    space), and quoting one into a value without escaping it breaks the whole reply.
 */
function sanitizeJsonText(text, { controls = false, commas = false, quotes = false } = {}) {
  let out = "";
  let inString = false;
  const stack = []; // enclosing containers, so the quote rule knows what may follow a comma

  for (let i = 0; i < text.length; i++) {
    const c = text[i];

    if (!inString) {
      if (c === '"') { inString = true; out += c; continue; }
      if (c === "{" || c === "[") stack.push(c);
      else if (c === "}" || c === "]") stack.pop();
      if (commas && c === ",") {
        const n = nextNonSpace(text, i + 1);
        if (n === "}" || n === "]") continue; // drop it
      }
      out += c;
      continue;
    }

    if (c === "\\") {
      const n = text[i + 1];
      if (n === undefined) { out += "\\\\"; continue; }
      if ('"\\/bfnrtu'.includes(n)) { out += c + n; i++; continue; } // a valid escape, keep it
      out += "\\\\" + n; i++; continue; // an invalid one, so the backslash was literal
    }
    if (c === '"') {
      if (quotes && !quoteClosesString(text, i, stack)) { out += '\\"'; continue; }
      inString = false; out += c; continue;
    }
    if (c < " ") {
      if (!controls) { out += c; continue; }
      out += c === "\n" ? "\\n" : c === "\r" ? "\\r" : c === "\t" ? "\\t"
        : "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0");
      continue;
    }
    out += c;
  }
  return out;
}

// Least invasive first: never apply the risky quote heuristic to a reply a safer pass fixes.
const SANITIZE_PASSES = [
  { controls: true },
  { controls: true, commas: true },
  { controls: true, commas: true, quotes: true },
];

/**
 * Describe WHY a reply would not parse, for the error screen.
 *
 * This exists because of a real misdiagnosis: the error screen previously showed a bare
 * `text.slice(0, 600)`, so every failing reply looked cut off mid-JSON whether it was or
 * not, and two rounds of fixes chased a truncation that was never happening. Report the
 * true length, say plainly whether the reply actually ends mid-value, and show the text
 * AROUND the parse error rather than the first 600 characters of a reply whose problem
 * may be 4000 characters in.
 *
 * @returns {{length:number, truncated:boolean, message:string, position:number|null,
 *            snippet:string, caretOffset:number, recoveredSlides:string[]}|null}
 */
export function describeJsonFailure(text) {
  if (typeof text !== "string" || !text) return null;
  let message = "";
  try {
    JSON.parse(text);
    return { length: text.length, truncated: false, message: "This reply parses as JSON.", position: null, snippet: text.slice(0, 600), caretOffset: -1, recoveredSlides: [] };
  } catch (e) {
    message = e.message;
  }

  const posMatch = /at position (\d+)/.exec(message);
  const position = posMatch ? Number(posMatch[1]) : null;
  const { stack, inString } = scanBracketState(text);
  // A missing brace deep inside the reply leaves the same open bracket stack at EOF as a
  // genuinely truncated reply does — that conflation is what sent two rounds of fixes
  // after a truncation that was never happening. The real signal is WHERE the parse
  // failed: a truncated reply's error sits at (or right at) the end of the text; a
  // structural error — like the one dropped brace this fix targets — sits well before
  // it, with a complete document's worth of (malformed) text still following.
  const nearEnd = position !== null && position >= text.length - 2;
  const truncated = position === null ? (stack.length > 0 || inString) : nearEnd && (stack.length > 0 || inString);

  const centre = position ?? text.length;
  const from = Math.max(0, centre - 220);
  const snippet = text.slice(from, Math.min(text.length, centre + 220));
  // Slide-shaped objects still recoverable from this reply, regardless of the overall
  // parse failure — lets the error screen say how much of the reply wasn't a total loss.
  const recoveredSlides = harvestSlides(text).map((s) => s.slide_id);
  return { length: text.length, truncated, message, position, snippet, caretOffset: centre - from, recoveredSlides };
}

/**
 * Try to recover a JSON value from a raw reply the platform's own reader rejected.
 * Returns the parsed value, or `null` when nothing usable can be recovered. Never throws.
 */
/**
 * Does `candidate` look like a "slides" reply that is silently missing slides the raw
 * text promised? Every repair pass below finds SOME balanced, parseable value inside a
 * damaged reply — the danger is a pass succeeding on a fragment that stops short of one
 * damaged slide and quietly returns fewer slides than the batch actually asked for, with
 * no error to signal the loss. Observed for real: a single dropped brace deep in one
 * slide's diagram spec let the balanced-span pass parse a "valid" object spanning only
 * the slides *before* the damage, silently dropping every slide after it, AND misplacing
 * that slide's own "sources" field a level too deep in the process (semantically wrong,
 * not just short) — while still returning a value that looks like total success. Reject
 * any candidate like that so the caller falls through to null, letting the slide-copy
 * loop's own harvestSlides(e.text, ...) do a proper per-slide salvage instead — verified
 * to recover every UNDAMAGED slide byte-exact rather than truncating the batch.
 */
function isIncompleteSlideBatch(rawText, candidate) {
  if (!candidate || typeof candidate !== "object" || !Array.isArray(candidate.slides)) return false;
  const promised = (rawText.match(/"slide_id"\s*:/g) ?? []).length;
  return promised > 1 && candidate.slides.length < promised;
}

export function tryRepairJson(text) {
  if (typeof text !== "string" || !text.trim()) return null;

  // Every candidate below funnels through this so no pass — present or future — can
  // silently accept a slides reply that dropped slides the raw text promised.
  const accept = (value) => (value !== undefined && !isIncompleteSlideBatch(text, value) ? value : undefined);

  let attempt = accept(safeJsonParse(text));
  if (attempt !== undefined) return attempt;

  FENCE_RE.lastIndex = 0;
  let m;
  while ((m = FENCE_RE.exec(text))) {
    attempt = accept(safeJsonParse(m[1]));
    if (attempt !== undefined) return attempt;
  }

  const spans = findBalancedSpans(text).sort((a, b) => b.length - a.length);
  for (const span of spans) {
    attempt = accept(safeJsonParse(span));
    if (attempt !== undefined) return attempt;
  }

  attempt = accept(tryCloseUnterminated(text));
  if (attempt !== undefined) return attempt;

  // Everything above assumes the reply is well-formed JSON somewhere inside a wrapper, or
  // simply cut short. The remaining case is a COMPLETE reply whose JSON is malformed — a
  // raw line break or an unescaped quote inside a string value. Escalate through the
  // sanitize passes, over the whole reply and over each balanced span, and take the first
  // that parses. Least invasive pass first, so a reply that only needed its control
  // characters escaped never has the riskier quote heuristic applied to it.
  const candidates = [text, ...spans];
  for (const pass of SANITIZE_PASSES) {
    for (const candidate of candidates) {
      attempt = accept(safeJsonParse(sanitizeJsonText(candidate, pass)));
      if (attempt !== undefined) return attempt;
      // A malformed reply can also be a cut-short one; close it after sanitizing.
      attempt = accept(tryCloseUnterminated(sanitizeJsonText(candidate, pass)));
      if (attempt !== undefined) return attempt;
    }
  }

  // Targeted last resort: JSON.parse's own error names the spot precisely ("Expected ','
  // or '}' after property value ... at position N") when N lands on a }/] that should
  // have been preceded by one more }. Gated on that exact message so it never fires on a
  // pseudo-JSON echo or plain prose (see the tests) — those fail with a different message
  // ("Unexpected token") and are correctly left to return null, not coerced into `{}`.
  //
  // isIncompleteSlideBatch above already rejects this pass's most dangerous failure mode
  // (silently dropping trailing slides) the same as every other pass, but a multi-slide
  // batch is still skipped here entirely: inserting the brace at the position JSON.parse
  // names closes whatever object is still open THERE, one object short of where the drop
  // actually happened, which can misplace a field (a block's "sources" ends up nested
  // inside its own "content") without changing the slide COUNT — a corruption the count
  // check can't see. harvestSlides is what exists to avoid that for a slide-copy batch.
  const isSlideBatch = (text.match(/"slide_id"\s*:/g) ?? []).length > 1;
  if (!isSlideBatch) {
    attempt = accept(tryInsertMissingBraces(text));
    if (attempt !== undefined) return attempt;
    for (const span of spans) {
      attempt = accept(tryInsertMissingBraces(span));
      if (attempt !== undefined) return attempt;
    }
  }

  return null;
}

const MISSING_BRACE_RE = /^Expected ',' or '}' after property value in JSON at position (\d+)/;

/** See tryRepairJson's last pass: insert one `}` at each such error position, up to a
 * few times, and stop the moment the message no longer matches this exact shape. */
function tryInsertMissingBraces(text, maxInsertions = 3) {
  let candidate = text;
  for (let n = 0; n < maxInsertions; n++) {
    try {
      return JSON.parse(candidate);
    } catch (e) {
      const m = MISSING_BRACE_RE.exec(e.message);
      if (!m) return undefined;
      const pos = Number(m[1]);
      const ch = candidate[pos];
      if (ch !== "}" && ch !== "]") return undefined;
      candidate = candidate.slice(0, pos) + "}" + candidate.slice(pos);
    }
  }
  return undefined;
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
        const batchIds = slideBatch.map((s) => s.slide_id);
        const batchMod = { ...mod, slides: slideBatch };
        let batchSlides = [];
        for (const chunk of inputChunks) {
          try {
            const resp = await callSampleJson(sampleJson, slideCopyPrompt(batchMod, chunk, corpus), { modelTier: MODEL_TIER });
            batchSlides = batchSlides.concat(resp.slides ?? []);
          } catch (e) {
            // A single dropped brace deep in one slide's diagram spec must not cost the
            // whole batch — salvage whatever else in this call's own raw reply still
            // parses as a slide before deciding whether to give up on it. Only surface
            // the failure to the viewer when NOTHING here was recoverable; a partial
            // recovery is kept and the run continues — whatever's still missing becomes
            // a placeholder slide below, never silence (see the deleted `slideBatch`
            // fallback this replaces: skeleton slides have no `blocks`, so that fallback
            // was substituting content-free slides that render blank and pass QA clean).
            const harvested = e && typeof e === "object" && e.code === "invalid_json" && typeof e.text === "string"
              ? harvestSlides(e.text, batchIds)
              : [];
            if (!harvested.length) throw e;
            batchSlides = batchSlides.concat(harvested);
          }
        }
        batchSlides = dedupeSlides(batchSlides);
        // Record this batch's slides into `modules` (the array e.progress captures on
        // throw) immediately, not after the whole module finishes — a later batch's
        // failure must not discard this one.
        let entry = modules.find((m) => m.module_id === mod.module_id);
        if (!entry) { entry = { ...mod, slides: [] }; modules.push(entry); }
        entry.slides = dedupeSlides(entry.slides.concat(batchSlides));
      }
    }

    // Any planned slide nobody ever actually wrote content for — a batch that could only
    // be partially harvested above, or a reply that simply returned fewer slides than it
    // was asked for without erroring at all — gets a real, visibly-flagged placeholder
    // slide instead of silently having no `blocks` (which renders blank and passes every
    // mechanical QA check, since qa.js iterates `slide.blocks ?? []`).
    for (const mod of moduleSkeletons) {
      if (!mod.slides.length) continue;
      let entry = modules.find((m) => m.module_id === mod.module_id);
      if (!entry) { entry = { ...mod, slides: [] }; modules.push(entry); }
      const gotIds = new Set(entry.slides.map((s) => s.slide_id));
      for (const skeleton of mod.slides) {
        if (!gotIds.has(skeleton.slide_id)) entry.slides.push(makePlaceholderSlide(skeleton));
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

// Exported so qa.js and tests can recognize a placeholder slide (and the exact wording it
// carries) without duplicating the string.
export const PLACEHOLDER_TEXT = "[content not generated — please complete]";

/** A real, renderable slide for a planned slide the model never actually produced content
 * for — gap:true on both blocks so qa.js's provenance check (sources or gap:true) treats
 * it the same as any other flagged gap, not a hard-fail missing-provenance defect. */
function makePlaceholderSlide(skeleton) {
  return {
    slide_id: skeleton.slide_id,
    role: skeleton.role,
    _placeholder: true,
    blocks: [
      { slot: "title", kind: "text", content: skeleton.title ?? skeleton.slide_id, gap: true, gap_note: PLACEHOLDER_TEXT },
      { slot: "body", kind: "text", content: PLACEHOLDER_TEXT, gap: true, gap_note: PLACEHOLDER_TEXT },
    ],
  };
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
