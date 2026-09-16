# Deck types

`lib/schemas/deck_registry.json` is the source of truth — this is the narrative rationale
behind it, not a duplicate of the data.

Nine types, each with a narrative spine, a required slide-role sequence, and a
`coverage_mode` (`full` — every key message must land on a slide or be explicitly waived;
`signpost` — a workshop pack is agenda, not argument, so it is scored as a lighter touch).

| Type | Spine | When |
|---|---|---|
| `steerco-update` | chronological | Recurring status; recipients already know the programme |
| `case-for-change` | situation-complication-resolution | First deck a sceptical audience sees |
| `findings-and-recommendations` | pyramid | Built from workshop/interview material; lead with the answer |
| `workshop-pack` | chronological | Presented live, not read cold |
| `readiness-assessment` | pyramid | Scored view against defined criteria |
| `roadmap` | chronological | Phased plan; the timeline slide carries the deck |
| `board-paper` | pyramid | Governance-level, terse, one message per slide |
| `training-module` | chronological | Prefer the `training-material-generator` skill directly for FSD-sourced learner decks |
| `proposal` | situation-complication-resolution | Prefer the `cm-proposal-generator` skill for an actual RFP response |

Requesting a type not in the registry is a hard error at Stage 3 (`plan_deck.py`) — never
a silent default to the closest match. `training-module` and `proposal` are listed for
registry completeness and route explicitly to the skill that actually carries their
specific QA (screenshot annotation / knowledge checks for training; requirement-coverage
and knowledge-bank retrieval for proposals) rather than duplicating it here.

A plan's roles must include every `required_roles` entry from the registry, **in order**
(a subsequence check — other roles may appear between them). `optional_roles` may appear
anywhere and are not checked. Both lists draw from `lib/deck/map-layouts.js`'s `ROLES`
vocabulary; a role outside that list is a schema error, not a deck-type error.
