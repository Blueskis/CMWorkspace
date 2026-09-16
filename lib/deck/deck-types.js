/**
 * Deck-type registry — a JS-importable copy of lib/schemas/deck_registry.json,
 * kept byte-identical in content (checked by test/deck-types-parity.mjs against
 * the JSON file directly) since a browser artifact cannot fetch a local repo file
 * at runtime. lib/schemas/deck_registry.json remains the source of truth — edit
 * there first, then re-run the generator this file is a comment away from.
 */

export const DECK_TYPES = {
  "steerco-update": {
    "label": "Steering committee update",
    "narrative": "chronological",
    "description": "Status since last steerco: progress, risks, decisions needed. Recipients already know the programme; this is a delta, not a re-pitch.",
    "required_roles": [
      "title-slide",
      "metric-row",
      "content",
      "content",
      "closing"
    ],
    "optional_roles": [
      "comparison",
      "table",
      "timeline",
      "two-content",
      "quote"
    ],
    "coverage_mode": "full"
  },
  "case-for-change": {
    "label": "Case for change",
    "narrative": "situation-complication-resolution",
    "description": "Persuasive: why the status quo fails, what changes, what it costs to wait. First deck a sceptical audience sees.",
    "required_roles": [
      "title-slide",
      "section-header",
      "content",
      "comparison",
      "content",
      "closing"
    ],
    "optional_roles": [
      "quote",
      "metric-row",
      "timeline",
      "picture"
    ],
    "coverage_mode": "full"
  },
  "findings-and-recommendations": {
    "label": "Findings and recommendations",
    "narrative": "pyramid",
    "description": "Lead with the answer, then the evidence. Built from workshop notes, interview transcripts, process design material.",
    "required_roles": [
      "title-slide",
      "content",
      "section-header",
      "content",
      "table",
      "closing"
    ],
    "optional_roles": [
      "comparison",
      "metric-row",
      "picture",
      "quote",
      "timeline"
    ],
    "coverage_mode": "full"
  },
  "workshop-pack": {
    "label": "Workshop pack",
    "narrative": "chronological",
    "description": "Agenda-led working session material: ground rules, exercises, capture templates. Built to be presented live, not read cold.",
    "required_roles": [
      "title-slide",
      "section-header",
      "content",
      "two-content",
      "closing"
    ],
    "optional_roles": [
      "comparison",
      "table",
      "picture",
      "timeline"
    ],
    "coverage_mode": "signpost"
  },
  "readiness-assessment": {
    "label": "Readiness assessment",
    "narrative": "pyramid",
    "description": "A scored view of go-live or adoption readiness against defined criteria, by dimension and by stakeholder group.",
    "required_roles": [
      "title-slide",
      "metric-row",
      "table",
      "content",
      "closing"
    ],
    "optional_roles": [
      "comparison",
      "timeline",
      "picture"
    ],
    "coverage_mode": "full"
  },
  "roadmap": {
    "label": "Roadmap",
    "narrative": "chronological",
    "description": "Phased plan over time: waves, milestones, dependencies. The timeline slide carries the deck.",
    "required_roles": [
      "title-slide",
      "timeline",
      "content",
      "closing"
    ],
    "optional_roles": [
      "metric-row",
      "table",
      "comparison"
    ],
    "coverage_mode": "full"
  },
  "board-paper": {
    "label": "Board paper deck",
    "narrative": "pyramid",
    "description": "Governance-level: decision requested, options considered, recommendation, risk. Terse, one message per slide.",
    "required_roles": [
      "title-slide",
      "content",
      "comparison",
      "metric-row",
      "closing"
    ],
    "optional_roles": [
      "table",
      "timeline",
      "quote"
    ],
    "coverage_mode": "full"
  },
  "training-module": {
    "label": "Training module",
    "narrative": "chronological",
    "description": "The training-material-generator's own deck type, listed here so plan_deck.py's registry lookup is total. Prefer the training-material-generator skill directly for FSD-sourced learner decks \u2014 its screenshot annotation and knowledge-check pipeline are specific to that skill and not duplicated here.",
    "required_roles": [
      "title-slide",
      "section-header",
      "content",
      "picture",
      "closing"
    ],
    "optional_roles": [
      "two-content",
      "table",
      "timeline"
    ],
    "coverage_mode": "full"
  },
  "proposal": {
    "label": "Proposal / bid deck",
    "narrative": "situation-complication-resolution",
    "description": "Listed for registry completeness. Prefer the cm-proposal-generator skill for an actual RFP response \u2014 it carries requirement-coverage QA and knowledge-bank retrieval this registry entry does not replicate.",
    "required_roles": [
      "title-slide",
      "content",
      "comparison",
      "table",
      "closing"
    ],
    "optional_roles": [
      "metric-row",
      "quote",
      "timeline",
      "picture"
    ],
    "coverage_mode": "full"
  }
};

export const DECK_TYPE_ORDER = ["steerco-update", "case-for-change", "findings-and-recommendations", "workshop-pack", "readiness-assessment", "roadmap", "board-paper", "training-module", "proposal"];
