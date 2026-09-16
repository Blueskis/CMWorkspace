/**
 * Turn a parsed document corpus into a deck plan, via two staged calls to Claude —
 * brief (key messages) then plan (slide-by-slide) — parameterised by the chosen deck
 * type's narrative spine and required role sequence (lib/deck/deck-types.js).
 *
 * Deliberately simpler than webapp/'s training-material-generator plan.js: a consulting
 * deck from this pipeline is typically 8-20 slides (a handful of key messages, each
 * landing on one or two slides), not a 40+ slide FSD-driven training course, so this
 * does not need per-module chunked generation with cross-call resume. One brief call,
 * one plan call, each within sample's 64 KiB input cap. If that stops being true for a
 * real corpus, chunking should be added the way plan.js's chunkSections/MAX_SLIDES_PER_CALL
 * already do it — not reinvented from scratch.
 *
 * Output is deck_plan.json's native shape — the same shape lib/deck/build-pptx.js's
 * buildPptx() and skills/deck-builder/scripts/plan_deck.py both consume — so a plan from
 * here, from the Python skill, or hand-edited are all interchangeable.
 */

const MAX_INPUT_BYTES = 48 * 1024; // leaves headroom under sample's 64 KiB cap for instructions
const MODEL_TIER = "complex";

function byteLength(s) {
  return new TextEncoder().encode(s).length;
}

/** Compact outline: section_id, path, and a short excerpt — enough to cite and write from
 * without shipping full section text (which is what would blow the byte budget). */
function compactOutline(sections, maxBytes = MAX_INPUT_BYTES) {
  const lines = [];
  let used = 0;
  for (const s of sections) {
    const excerpt = (s.text ?? "").slice(0, 220).replace(/\s+/g, " ").trim();
    const line = `[${s.section_id}] ${s.section_path}\n  ${excerpt}`;
    const size = byteLength(line) + 1;
    if (used + size > maxBytes) break;
    lines.push(line);
    used += size;
  }
  return lines.join("\n");
}

function roleGuide(roleLabels) {
  return Object.entries(roleLabels).map(([role, label]) => `  - "${role}": ${label}`).join("\n");
}

const ROLE_LABELS = {
  "title-slide": "Cover slide — deck title only, no body content",
  "section-header": "Section divider — a short title, optionally a one-line strapline",
  picture: "A slide built around one screenshot/image with a caption",
  "two-content": "Two roughly equal text columns",
  content: "Title + one body area of bullets or a short paragraph",
  comparison: "Title + 2-3 side-by-side content areas (before/after, options)",
  table: "Title + a table of rows/columns",
  "metric-row": "Title + 3+ stat callouts (a number and a label each)",
  quote: "A single pull-quote or callout statement, no title",
  timeline: "Title + a sequence of phases/steps (rendered as text bullets for now — no diagram generation yet)",
  closing: "Closing/thank-you slide — reuses the title-slide shape",
};

const JSON_HYGIENE = `Escape every double quote inside a text value as \\" and keep the whole
reply as a single JSON object with no prose before or after it, no markdown code fence.`;

export function briefPrompt(corpus, deckType, brand) {
  const outline = compactOutline(corpus.sections);
  const terms = (brand?.messaging?.terminology ?? [])
    .map((t) => `${t.term}: ${t.definition}`).join("; ");
  return `You are drafting the narrative for a "${deckType.label}" consulting deck.
Narrative spine: ${deckType.narrative} — ${deckType.description}

Below is a compact outline of the source documents (section id, path, short excerpt).
Read it and produce 4-8 KEY MESSAGES that this deck should make, each one a single clear
statement a consultant would say out loud, each backed by specific section_id(s) from the
outline below. A message with no real support in the source material must not be invented —
mark it {"gap": true, "gap_note": "..."} instead of citing a source that doesn't exist.
${terms ? `\nUse the client's own terminology where the source text supports it: ${terms}` : ""}

${JSON_HYGIENE}

Reply with exactly this JSON shape:
{"key_messages": [
  {"message_id": "m1", "statement": "...", "sources": ["section_id", ...]},
  {"message_id": "m2", "statement": "...", "gap": true, "gap_note": "why no source supports this"}
]}

--- SOURCE OUTLINE ---
${outline}`;
}

export function planPrompt(brief, deckType, corpus, brand) {
  const required = deckType.required_roles;
  const optional = deckType.optional_roles ?? [];
  const messages = brief.key_messages
    .map((m) => `[${m.message_id}] ${m.statement}${m.gap ? " (GAP: " + m.gap_note + ")" : ""}`)
    .join("\n");
  const voice = (brand?.tone?.voice ?? []).join(", ");

  return `Turn these key messages into a slide-by-slide plan for a "${deckType.label}" deck.

REQUIRED ROLE SEQUENCE (must appear in this order as a subsequence of your slides' roles —
other slides may appear between them, but these must occur, in order):
${JSON.stringify(required)}

Optional roles you may also use where they fit: ${JSON.stringify(optional)}

Role meanings:
${roleGuide(ROLE_LABELS)}

Each slide's blocks must use slot "title" (the slide title text), "body" or "body2" (bullet
or paragraph text), or "picture"/"caption" (only if you have no actual image — do not
invent one; skip picture-shaped content unless a source explicitly describes an image to
place). Every non-gap block needs "sources": [a real section_id from the source material
these key messages were built from, or a key_message's own message_id]. A block with
neither sources nor gap:true is invalid.
${voice ? `\nVoice: ${voice}. Write slide titles and bullets in this voice.` : ""}

${JSON_HYGIENE}

Reply with exactly this JSON shape (one module is fine for a deck this size):
{"modules": [{"module_id": "m1", "slides": [
  {"slide_id": "s1", "role": "title-slide", "title": "...",
   "blocks": [{"slot": "title", "kind": "text", "content": "...", "sources": ["m1"]}]},
  {"slide_id": "s2", "role": "content", "title": "...",
   "blocks": [
     {"slot": "title", "kind": "text", "content": "...", "sources": ["m2"]},
     {"slot": "body", "kind": "text", "content": "bullet one\\nbullet two", "sources": ["fsd#4.2"]}
   ],
   "speaker_notes": "..."}
]}]}

--- KEY MESSAGES ---
${messages}`;
}

function stripFence(text) {
  const m = text.match(/```(?:json)?\s*\n?([\s\S]*?)```/);
  return m ? m[1] : text;
}

function tryParseJson(text) {
  const stripped = stripFence(text).trim();
  try {
    return JSON.parse(stripped);
  } catch (e1) {
    // one repair attempt: strip trailing commas before } or ]
    const repaired = stripped.replace(/,(\s*[}\]])/g, "$1");
    try {
      return JSON.parse(repaired);
    } catch (e2) {
      const err = new Error(`Could not parse the model's reply as JSON: ${e2.message}`);
      err.rawText = text;
      throw err;
    }
  }
}

async function callSampleJson(sampleJson, prompt) {
  const result = await sampleJson(prompt, { modelTier: MODEL_TIER });
  const text = typeof result === "string" ? result : result.text;
  return tryParseJson(text);
}

/**
 * @param corpus  { documents, sections, assets, notes } from lib/deck/parse.js's parseSources()
 * @param deckType  one entry from lib/deck/deck-types.js's DECK_TYPES
 * @param opts  { sampleJson, brand, onStage }
 */
export async function generateDeckPlan(corpus, deckType, { sampleJson, brand = null, onStage = () => {} } = {}) {
  if (!sampleJson) throw new Error("generateDeckPlan requires a sampleJson function");

  onStage("brief");
  const brief = await callSampleJson(sampleJson, briefPrompt(corpus, deckType, brand));
  if (!Array.isArray(brief.key_messages) || brief.key_messages.length === 0) {
    throw new Error("The model's brief had no key_messages — try again, or check the source documents have enough content.");
  }

  onStage("plan");
  const plan = await callSampleJson(sampleJson, planPrompt(brief, deckType, corpus, brand));
  if (!Array.isArray(plan.modules) || plan.modules.length === 0) {
    throw new Error("The model's plan had no modules/slides — try again.");
  }

  return { brief, plan };
}
