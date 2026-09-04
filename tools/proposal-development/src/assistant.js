"use strict";

/* =================================================================
   The section-01 correction assistant. One prompt in, a reply plus a
   proposed edit list out — the same shape a person's own reclassify
   click produces (triage-edit.js's edit objects), so both paths share
   one apply function and one visible "who changed this" marker.

   sample() is one-shot and memory-less (sample.d.ts), so a follow-up
   like "the one below it too" only resolves because the recent
   conversation is re-sent as part of the prompt every time.

   Edits are never auto-applied. The page shows the proposed batch and
   the consultant accepts or discards it — correcting a classifier's
   guess by silently trusting a second model's guess would just move
   the same risk up one level.
   ================================================================= */

const ASSISTANT_PROMPT_BUDGET_BYTES = 60 * 1024; // sample()'s cap is 64 KiB; leave headroom

function getSectionDigest() {
  if (typeof sectionDigest !== "undefined") return sectionDigest;
  return require("./triage-edit.js").sectionDigest;
}

function getStripJsonFence() {
  if (typeof stripJsonFence !== "undefined") return stripJsonFence;
  return require("./draft.js").stripJsonFence;
}

const byteLen = s => new TextEncoder().encode(s).length;

/* triage: the current (possibly already-edited) triage object.
   transcript: [{role: "user"|"assistant", text}], oldest first —
   the recent exchange, so a follow-up instruction can refer back to
   what was just said. instruction: the consultant's latest message.
   Returns a prompt string guaranteed <= ASSISTANT_PROMPT_BUDGET_BYTES,
   trimming the oldest transcript turns first when it doesn't fit. */
function buildAssistantPrompt({ triage, transcript = [], instruction, budgetBytes = ASSISTANT_PROMPT_BUDGET_BYTES }) {
  const digestFn = getSectionDigest();

  const header = `You are helping a change-management consultant review an automatic classifier's `
    + `read of a tender document. Each clause below was scored by a keyword classifier into `
    + `cm-core (ours to answer), cm-adjacent (related, not core), or not-cm (not ours). The `
    + `classifier is simple and can be wrong — that is exactly why you are here.\n\n`
    + `You may propose edits, answer a question, or both. An edit is one of:\n`
    + `  {"op":"reclassify","sectionId":"...","verdict":"cm-core"|"cm-adjacent"|"not-cm"}\n`
    + `  {"op":"rename","sectionId":"...","heading":"..."}\n`
    + `  {"op":"add","heading":"...","verdict":"cm-core"|"cm-adjacent"|"not-cm","excerpt":"..."}\n`
    + `  {"op":"remove","sectionId":"..."}\n\n`
    + `RULES:\n`
    + `- Only propose an edit for a sectionId that appears in the CLAUSES list below. Never invent one.\n`
    + `- If the consultant is only asking a question, answer in "reply" and leave "edits" empty — do `
    + `not propose an edit unless one was actually asked for.\n`
    + `- Keep "reply" to one or two sentences.\n`
    + `- Reply with ONLY a JSON object of this exact shape, no prose outside it:\n`
    + `  {"reply":"...","edits":[...]}\n\n`;

  const instructionBlock = `CONSULTANT'S LATEST MESSAGE:\n${instruction}\n\n`;
  const clausesLabel = "CLAUSES:\n";
  const transcriptLabel = "CONVERSATION SO FAR:\n";

  const fixedOverhead = byteLen(header) + byteLen(instructionBlock) + byteLen(clausesLabel) + byteLen("\n\n");
  const digestBudget = Math.max(1000, budgetBytes - fixedOverhead);
  const digest = digestFn(triage, digestBudget);

  let turns = transcript.slice();
  const budgetForTranscript = () => budgetBytes - fixedOverhead - byteLen(digest) - byteLen(transcriptLabel + "\n\n");
  let transcriptBlock = "";
  while (turns.length) {
    transcriptBlock = turns.map(t => `${t.role}: ${t.text}`).join("\n");
    if (byteLen(transcriptBlock) <= budgetForTranscript()) break;
    turns = turns.slice(1); // drop the oldest turn first
  }

  return header
    + clausesLabel + digest + "\n\n"
    + (transcriptBlock ? transcriptLabel + transcriptBlock + "\n\n" : "")
    + instructionBlock;
}

/* Parses a model completion into {reply, edits}. Throws on anything
   that isn't a JSON object with at least a "reply" string — an "edits"
   array is optional (a question needs none). Validity of the EDITS
   themselves (real sectionIds, real verdicts) is triage-edit.js's
   validateEdits job, called separately once these are proposed. */
function parseAssistantReply(completion) {
  const strip = getStripJsonFence();
  const text = strip(completion);
  const parsed = JSON.parse(text);
  if (!parsed || typeof parsed.reply !== "string") throw new Error("no reply string in response");
  const edits = Array.isArray(parsed.edits) ? parsed.edits : [];
  return { reply: parsed.reply, edits };
}

/* Orchestrates one assistant turn: build the prompt, call sample(),
   parse, retry once on a parse failure with a stricter instruction.
   Mirrors draft.js's draftSection so the two features share one
   failure model. sample() rejections (not_granted, rate_limited, …)
   propagate uncaught — the caller decides whether to hide the
   assistant box or stop, never retried in a loop here. */
async function runAssistant({ triage, transcript, instruction, sample, opts = {} }) {
  const modelTier = opts.modelTier || "complex";
  const prompt = buildAssistantPrompt({ triage, transcript, instruction });

  let lastError = null;
  for (let attempt = 0; attempt < 2; attempt++) {
    const thisPrompt = attempt === 0 ? prompt
      : prompt + `\n\nYour previous reply could not be parsed as JSON. Reply with ONLY the JSON `
        + `object, no markdown fencing, no commentary.`;
    const result = await sample({ prompt: thisPrompt, modelTier }); // rejections propagate
    try {
      return { ...parseAssistantReply(result.completion), failed: false };
    } catch (err) {
      lastError = err;
    }
  }

  return {
    reply: `Sorry, I couldn't read that as a usable response (${lastError ? lastError.message : "unknown error"}). Nothing was changed.`,
    edits: [],
    failed: true,
  };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { buildAssistantPrompt, parseAssistantReply, runAssistant, ASSISTANT_PROMPT_BUDGET_BYTES };
}
