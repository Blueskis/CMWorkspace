"use strict";

/* =================================================================
   Drafting — one sample() call per outline section, built on the
   retrieved past-deck excerpts, validated against the same provenance
   invariant proposal_plan.schema.json enforces: every block carries
   non-empty sources[] OR gap:true + gap_note. No third state. A block
   that arrives any other way — no sources, or citing a source ID that
   was never offered to it — is rewritten into a [GAP] block naming
   the clause it leaves exposed, never silently dropped or trusted.
   ================================================================= */

const PROMPT_BUDGET_BYTES = 48 * 1024; // sample()'s hard cap is 64 KiB; leave headroom
const draftByteLen = s => new TextEncoder().encode(s).length;

/* section: { id, title, kind, clauseExcerpt? } — one outline entry.
   layoutPlaceholders: [{type, idx, name}] — from the chosen layout,
   so the model is only ever asked to fill placeholders that exist.
   excerpts: [{deck, slideNo, text}] — from retrieve.js, already
   trimmed to the budget by assembleExcerpts.
   Returns the prompt string, guaranteed <= PROMPT_BUDGET_BYTES. */
function buildSectionPrompt(section, layoutPlaceholders, excerpts) {
  const sourceIds = excerpts.map((e, i) => `S${i + 1}`);
  const sourcesBlock = excerpts.length
    ? excerpts.map((e, i) => `[${sourceIds[i]}] (${e.deck}, slide ${e.slideNo})\n${e.text}`).join("\n\n")
    : "(none supplied — no past proposal covers this section)";

  const placeholderList = layoutPlaceholders.map(p => p.name || p.type).join(", ") || "text";

  const prompt = `You are drafting one slide section of a change-management proposal, `
    + `as a first draft for a human practitioner to review before submission.\n\n`
    + `SECTION: ${section.title}\n`
    + (section.clauseExcerpt ? `WHAT THE TENDER ASKS (verbatim):\n${section.clauseExcerpt}\n\n` : "\n")
    + `SLIDE PLACEHOLDERS AVAILABLE: ${placeholderList}\n\n`
    + `PAST PROPOSAL EXCERPTS (cite by their bracket ID, e.g. "S1"):\n${sourcesBlock}\n\n`
    + `RULES:\n`
    + `- Every block of content must cite the source IDs above it is drawn from, in a "sources" array.\n`
    + `- If nothing supplied covers a point the section needs, do not invent content. Instead set `
    + `"gap": true and write a one-sentence "gap_note" naming exactly what is missing.\n`
    + `- Never state a client name, metric, or date that is not present in the excerpts.\n`
    + `- Reply with ONLY a JSON object of this exact shape, no prose outside it:\n`
    + `{"blocks":[{"kind":"heading"|"bullets"|"paragraph","text":"...","items":[{"text":"...","level":0}],`
    + `"sources":["S1"],"gap":false,"gap_note":null}]}`;

  if (draftByteLen(prompt) <= PROMPT_BUDGET_BYTES) return prompt;

  // Should not happen given assembleExcerpts' own budgeting upstream, but
  // never send an oversized prompt — trim the excerpts block harder here
  // as a last resort rather than let the call fail on prompt_too_large.
  const overhead = draftByteLen(prompt) - draftByteLen(sourcesBlock);
  const allowed = Math.max(0, PROMPT_BUDGET_BYTES - overhead);
  let trimmedBlock = sourcesBlock;
  while (draftByteLen(trimmedBlock) > allowed && trimmedBlock.length > 0) {
    trimmedBlock = trimmedBlock.slice(0, Math.floor(trimmedBlock.length * 0.9));
  }
  return prompt.replace(sourcesBlock, trimmedBlock);
}

/* Parse a model completion into blocks, tolerating a fenced ```json
   wrapper (a common, harmless deviation from "ONLY a JSON object"). */
function parseDraftJson(completion) {
  let text = String(completion || "").trim();
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (fenced) text = fenced[1].trim();
  const parsed = JSON.parse(text);
  if (!parsed || !Array.isArray(parsed.blocks)) throw new Error("no blocks[] array in response");
  return parsed.blocks;
}

/* The provenance invariant, enforced client-side regardless of what
   the model actually returned. validSourceIds: the S1..Sn IDs that
   were actually offered to this section's prompt — a block citing an
   ID outside that set gets the same [GAP] treatment as citing none,
   since neither can be traced back to real material. */
function enforceProvenance(blocks, validSourceIds, clauseTitle) {
  const validSet = new Set(validSourceIds);
  return blocks.map((block, i) => {
    const sources = Array.isArray(block.sources) ? block.sources.filter(s => validSet.has(s)) : [];
    const claimedGap = block.gap === true;

    if (claimedGap) {
      return {
        kind: block.kind || "paragraph",
        text: block.text,
        items: block.items,
        sources: [],
        gap: true,
        gap_note: block.gap_note || `No source material covers this point in "${clauseTitle}".`,
      };
    }
    if (sources.length > 0) {
      return { kind: block.kind || "paragraph", text: block.text, items: block.items, sources, gap: false, gap_note: null };
    }
    // Neither a real source nor an honest gap claim: no third state allowed.
    return {
      kind: block.kind || "paragraph",
      text: block.text,
      items: block.items,
      sources: [],
      gap: true,
      gap_note: `Block ${i + 1} of "${clauseTitle}" cited no verifiable source — rewritten as a gap `
        + `rather than left unattributed.`,
    };
  });
}

/* Orchestrates one section's draft: build the prompt, call sample(),
   parse, validate provenance. `sample` is the claude.use("sample")
   function; passed in so this module has no direct window.claude
   dependency and stays testable in Node with a fake. Retries once on
   a parse failure with a stricter instruction; a second failure
   yields a single all-gap block rather than throwing, so one bad
   section never stops the run. */
async function draftSection(section, layoutPlaceholders, excerpts, sample, opts = {}) {
  const modelTier = opts.modelTier || "complex";
  const sourceIds = excerpts.map((_, i) => `S${i + 1}`);
  const prompt = buildSectionPrompt(section, layoutPlaceholders, excerpts);

  let lastError = null;
  for (let attempt = 0; attempt < 2; attempt++) {
    const thisPrompt = attempt === 0 ? prompt
      : prompt + `\n\nYour previous reply could not be parsed as JSON. Reply with ONLY the JSON object, `
        + `no markdown fencing, no commentary.`;
    let completion;
    try {
      const result = await sample({ prompt: thisPrompt, modelTier });
      completion = result.completion;
    } catch (err) {
      throw err; // sample() rejection codes are the caller's to handle (rate_limited etc.)
    }
    try {
      const blocks = parseDraftJson(completion);
      return { blocks: enforceProvenance(blocks, sourceIds, section.title), failed: false };
    } catch (err) {
      lastError = err;
    }
  }

  return {
    blocks: [{
      kind: "paragraph", text: null, items: null, sources: [], gap: true,
      gap_note: `Drafting failed for "${section.title}" (could not parse a response): `
        + `${lastError ? lastError.message : "unknown error"}.`,
    }],
    failed: true,
  };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    buildSectionPrompt, parseDraftJson, enforceProvenance, draftSection, PROMPT_BUDGET_BYTES,
  };
}
