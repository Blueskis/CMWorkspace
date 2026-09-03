"use strict";

/* =================================================================
   Outline building — a port of reference/section-library.md's three
   rules: name sections in the client's own words, size by named
   deliverable rather than invented weights, and keep the tender's
   own clause order. Operates on the triage a tender's own section 01
   already produces (splitSections + scoreSection), so a "cm-core"
   clause here is exactly what the existing page already classifies
   that way.
   ================================================================= */

const FRONT_FRAMING = [
  { id: "framing-cover", title: "Cover", layoutHint: "title-slide" },
  { id: "framing-exec-summary", title: "Executive Summary", layoutHint: "title-and-content" },
  { id: "framing-understanding", title: "Our Understanding", layoutHint: "title-and-content" },
];

// Cuttable back framing, most expendable first — this is the order
// slide_budget.cut_for_length removes from when a limit bites. Named
// clause slides are never cut: Rule 2 makes them the thing being
// scored, and a first draft that drops one silently is worse than a
// draft that runs over budget.
const BACK_FRAMING = [
  { id: "framing-why-us", title: "Why Us", layoutHint: "title-and-content" },
  { id: "framing-delivery-plan", title: "Delivery Plan and Timeline", layoutHint: "timeline" },
  { id: "framing-team", title: "Team Structure and Governance", layoutHint: "team-grid" },
  { id: "framing-experience", title: "Relevant Experience", layoutHint: "case-study" },
  { id: "framing-commercials", title: "Commercials", layoutHint: "table" },
];

const outlineSlug = v => String(v).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

function clauseSlideFrom(section, index) {
  return {
    id: `clause-${index}-${outlineSlug(section.heading || "clause")}`,
    kind: "clause",
    title: section.heading || `Clause ${index + 1}`,
    layoutHint: "title-and-content",
    clauseIndex: index,
    excerpt: section.excerpt || "",
    page: section.page || null,
  };
}

/* triage: the object triage() in the existing page already produces
   (sections[] with .verdict, .heading, .excerpt, .page, in document
   order). opts.slideLimit: from rfp constraints, e.g. a stated slide
   cap; omitted or falsy means no limit. */
function buildOutline(triage, opts = {}) {
  const clauseSections = (triage.sections || []).filter(s => s.verdict === "cm-core");
  const clauseSlides = clauseSections.map((s, i) => clauseSlideFrom(s, i));

  if (!clauseSlides.length) {
    // Nothing the tender raised is ours to answer — say so plainly rather
    // than fabricating clause content; framing sections still make sense.
    const slides = [...FRONT_FRAMING, ...BACK_FRAMING].map(f => ({ ...f, kind: "framing" }));
    return { slides, cutForLength: [], clauseCount: 0, limit: opts.slideLimit || null, noClauses: true };
  }

  let backFraming = BACK_FRAMING.map(f => ({ ...f, kind: "framing" }));
  const front = FRONT_FRAMING.map(f => ({ ...f, kind: "framing" }));
  const cutForLength = [];

  const limit = opts.slideLimit || null;
  if (limit) {
    let total = front.length + clauseSlides.length + backFraming.length;
    let cutIdx = 0; // BACK_FRAMING is already ordered most-expendable-first
    while (total > limit && cutIdx < backFraming.length) {
      cutForLength.push(backFraming[cutIdx].title);
      cutIdx++;
      total--;
    }
    backFraming = backFraming.slice(cutIdx);
  }

  const slides = [...front, ...clauseSlides, ...backFraming];
  return { slides, cutForLength, clauseCount: clauseSlides.length, limit, noClauses: false };
}

/* Coverage check — mirrors qa_deck.py's mandatory-requirement audit,
   but softened per the plan: an uncovered clause does not fail the
   run. It gets reported and a visible [GAP] slide is appended so the
   hole is visible in the deck itself, and export still proceeds. */
function reconcileCoverage(triage, slides) {
  const clauseSections = (triage.sections || []).filter(s => s.verdict === "cm-core");
  const covered = new Set(
    slides.filter(s => s.kind === "clause" && typeof s.clauseIndex === "number").map(s => s.clauseIndex)
  );
  const uncovered = [];
  const gapSlides = [];

  clauseSections.forEach((section, index) => {
    if (covered.has(index)) return;
    uncovered.push({ index, heading: section.heading });
    gapSlides.push({
      id: `gap-${index}-${outlineSlug(section.heading || "clause")}`,
      kind: "gap",
      title: `[GAP] ${section.heading || `Clause ${index + 1}`}`,
      layoutHint: "title-and-content",
      clauseIndex: index,
      gapNote: `No slide answers this tender clause: "${section.heading || "untitled"}".`,
    });
  });

  return {
    covered: [...covered],
    uncovered,
    slides: uncovered.length ? [...slides, ...gapSlides] : slides,
  };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { buildOutline, reconcileCoverage, FRONT_FRAMING, BACK_FRAMING };
}
