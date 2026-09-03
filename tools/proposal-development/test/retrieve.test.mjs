import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { rankSlides, assembleExcerpts } = require("../src/retrieve.js");

// Test case 17: section "Training strategy" against 3 decks -> ranked
// slides, each tagged {deck, slideNo}.
test("case 17: ranks slides from three decks by relevance to a section", () => {
  const deckSlides = [
    { deck: "Deck A", slideNo: 1, text: "Cover slide, client logo, engagement title." },
    { deck: "Deck A", slideNo: 2, text: "Our training strategy: needs analysis, curriculum, instructor-led delivery, training materials." },
    { deck: "Deck B", slideNo: 1, text: "Commercial terms and pricing assumptions." },
    { deck: "Deck B", slideNo: 2, text: "Training strategy and curriculum design, training strategy revisited for superusers." },
    { deck: "Deck C", slideNo: 1, text: "Stakeholder engagement plan and communications cadence." },
  ];
  const ranked = rankSlides("Training strategy", deckSlides);

  assert.equal(ranked.length, deckSlides.length);
  for (const slide of ranked) {
    assert.ok(slide.deck, "each ranked slide carries its source deck");
    assert.ok(typeof slide.slideNo === "number");
  }
  // The two slides that actually discuss training strategy should outrank
  // the unrelated commercial/cover/stakeholder slides.
  const top2 = ranked.slice(0, 2).map(s => `${s.deck}#${s.slideNo}`);
  assert.ok(top2.includes("Deck A#2"));
  assert.ok(top2.includes("Deck B#2"));
  assert.ok(ranked[0].score >= ranked[ranked.length - 1].score);
});

// Test case 18: no decks uploaded -> empty result; caller states it plainly.
test("case 18: no decks produces an empty ranked list, not an error", () => {
  const ranked = rankSlides("Training strategy", []);
  assert.deepEqual(ranked, []);
  const { excerpts, truncated, usedBytes } = assembleExcerpts(ranked, 48000);
  assert.deepEqual(excerpts, []);
  assert.equal(truncated, false);
  assert.equal(usedBytes, 0);
});

// Test case 19: 3 large decks -> assembled prompt stays under budget,
// lowest-ranked excerpts truncated first.
test("case 19: assembly stays under the byte budget, truncating the weakest matches first", () => {
  const big = (label, n) => `${label} ${"change management training strategy ".repeat(n)}`;
  const deckSlides = [
    { deck: "Deck A", slideNo: 1, text: big("strongest match on training strategy", 400) },
    { deck: "Deck B", slideNo: 1, text: big("second best training strategy content", 400) },
    { deck: "Deck C", slideNo: 1, text: big("weakest, barely relevant filler text about logistics", 400) },
  ];
  const ranked = rankSlides("training strategy curriculum", deckSlides);
  const budget = 2000; // bytes — forces truncation across ~3.6KB of raw text
  const { excerpts, truncated, usedBytes } = assembleExcerpts(ranked, budget);

  assert.ok(usedBytes <= budget, `usedBytes ${usedBytes} exceeds budget ${budget}`);
  assert.equal(truncated, true);

  const topRankedDeck = ranked[0].deck;
  const bottomRankedDeck = ranked[ranked.length - 1].deck;
  const topAfter = excerpts.find(e => e.deck === topRankedDeck);
  const bottomAfter = excerpts.find(e => e.deck === bottomRankedDeck);

  assert.ok(topAfter, "top-ranked excerpt should survive assembly");
  if (bottomAfter) {
    assert.ok(topAfter.text.length >= bottomAfter.text.length,
      "top-ranked excerpt should be truncated no more than the weakest match");
  }
});
