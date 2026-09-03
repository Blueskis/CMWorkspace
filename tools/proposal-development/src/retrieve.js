"use strict";

/* =================================================================
   Retrieval — same shape as scripts/retrieve.py's scorer (a shortlist
   generator, not a decision), applied to past-deck slides instead of
   knowledge-bank entries. There are no tags on a past deck's slides,
   so the query is the section's own words (its title plus the
   tender's clause text): literal, explainable overlap, exactly like
   the knowledge-bank retriever and the existing page's tag matching.
   ================================================================= */

const RETRIEVE_STOPWORDS = new Set([
  "and", "or", "the", "of", "a", "to", "in", "for", "with", "on", "is", "are", "this",
  "that", "will", "shall", "must", "should", "may", "an", "as", "by", "at", "be", "it",
]);

function tokenize(text) {
  const words = String(text || "").toLowerCase().match(/[a-z0-9]+/g) || [];
  const out = [];
  const seen = new Set();
  for (const w of words) {
    if (w.length <= 3 || RETRIEVE_STOPWORDS.has(w) || seen.has(w)) continue;
    seen.add(w);
    out.push(w);
  }
  return out;
}

function countOccurrences(haystack, word) {
  const re = new RegExp("\\b" + word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\b", "gi");
  const m = haystack.match(re);
  return m ? m.length : 0;
}

/* query: a string (typically the section title plus the tender's own
   clause excerpt). deckSlides: [{ deck, slideNo, text }] — as produced
   by splitting an uploaded past deck into per-slide text. Returns the
   same array, each entry carrying .score and .matched, sorted by
   score descending, ties broken by original order for determinism. */
function rankSlides(query, deckSlides) {
  const tokens = tokenize(query);
  return deckSlides
    .map((slide, i) => {
      const lower = (slide.text || "").toLowerCase();
      let score = 0;
      const matched = [];
      for (const token of tokens) {
        const hits = Math.min(countOccurrences(lower, token), 3);
        if (hits) { score += hits; matched.push(token); }
      }
      return { ...slide, score, matched, __order: i };
    })
    .sort((a, b) => b.score - a.score || a.__order - b.__order)
    .map(({ __order, ...rest }) => rest);
}

const retrieveByteLen = s => new TextEncoder().encode(s).length;

/* Assemble ranked slides into a prompt-ready excerpt bundle under a
   byte budget. Slides that don't fit are truncated from the
   lowest-ranked end first — the retrieval order already put the most
   relevant material first, so if anything has to give it should be
   the material that mattered least to begin with. */
function assembleExcerpts(ranked, budgetBytes) {
  const items = ranked.map(r => ({ ...r }));
  let total = items.reduce((sum, it) => sum + retrieveByteLen(it.text || ""), 0);
  let truncated = false;

  let i = items.length - 1;
  while (total > budgetBytes && i >= 0) {
    const it = items[i];
    const text = it.text || "";
    if (!text.length) { i--; continue; }
    const before = retrieveByteLen(text);
    const target = Math.max(0, text.length - Math.ceil(text.length * 0.2) - 1);
    const newText = text.slice(0, target);
    total -= before - retrieveByteLen(newText);
    it.text = newText;
    truncated = true;
    if (!newText.length) i--;
  }

  const excerpts = items.filter(it => (it.text || "").length > 0);
  return { excerpts, truncated, usedBytes: excerpts.reduce((sum, it) => sum + retrieveByteLen(it.text), 0) };
}

/* Split a past deck's raw text (already extracted via readDocument /
   the .pptx slide-splitting path) into per-slide entries tagged with
   their deck name, for rankSlides to work over. Mirrors the existing
   page's .pptx reading, which already joins slides with "\n" — this
   just re-splits on the same boundary the extractor used. */
function slidesFromDeckText(deckName, rawText) {
  return String(rawText || "")
    .split(/\n(?=\S)/)
    .map(t => t.trim())
    .filter(Boolean)
    .map((text, i) => ({ deck: deckName, slideNo: i + 1, text }));
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { tokenize, rankSlides, assembleExcerpts, slidesFromDeckText };
}
