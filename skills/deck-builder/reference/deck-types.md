# Deck types

`lib/schemas/deck_registry.json` is the source of truth — this is the narrative rationale
behind it, not a duplicate of the data.

Eleven types, each with a narrative spine, a required slide-role sequence, and a
`coverage_mode` (`full` — every key message must land on a slide or be explicitly waived;
`signpost` — a workshop pack or discussion deck is agenda, not argument, so it is scored
as a lighter touch).

**Generic by default.** This skill was originally scoped to change-management decks; it
now covers any consulting engagement — strategy, ops, tech delivery, M&A, whatever the
practitioner works on day to day. Only `case-for-change` and `findings-and-recommendations`
carry a CM-specific default framing (below); every other type applies as-is to any
engagement.

| Type | Spine | When |
|---|---|---|
| `status-update` | chronological | Recurring progress update to a sponsor or steering group; recipients already know the engagement |
| `discussion-deck` | pyramid | Working-session material to prompt a decision, not announce one — options and trade-offs, no closed recommendation |
| `proposal-bid-deck` | situation-complication-resolution | A from-scratch pitch for new work, no RFP to answer against — the deck itself has to build the case |
| `case-for-change` **(CM-specific)** | situation-complication-resolution | First deck a sceptical audience sees ahead of a change |
| `findings-and-recommendations` **(CM-specific default framing)** | pyramid | Built from workshop/interview material; lead with the answer — the shape suits any diagnostic engagement |
| `workshop-pack` | chronological | Presented live, not read cold |
| `readiness-assessment` | pyramid | Scored view against defined criteria — go-live, operational, adoption, whatever the engagement is scoring |
| `roadmap` | chronological | Phased plan; the timeline slide carries the deck |
| `board-paper` | pyramid | Governance-level, terse, one message per slide |
| `training-module` | chronological | Prefer the `training-material-generator` skill directly for FSD-sourced learner decks |
| `rfp-response` | situation-complication-resolution | Prefer the `cm-proposal-generator` skill for an actual RFP response |

`proposal-bid-deck` and `rfp-response` are deliberately two different types, not one with
an optional field: a bid deck built without a client-issued scope has to construct its own
argument for why the work matters, where an RFP response is answering someone else's
stated requirements and evaluation criteria — different narrative jobs, different QA
(`rfp-response` routes to `cm-proposal-generator`'s requirement-coverage checking;
`proposal-bid-deck` is built and QA'd entirely within this skill).

Requesting a type not in the registry is a hard error at Stage 3 (`plan_deck.py`) — never
a silent default to the closest match. `training-module` and `rfp-response` are listed for
registry completeness and route explicitly to the skill that actually carries their
specific QA (screenshot annotation / knowledge checks for training; requirement-coverage
and knowledge-bank retrieval for RFP responses) rather than duplicating it here.

A plan's roles must include every `required_roles` entry from the registry, **in order**
(a subsequence check — other roles may appear between them). `optional_roles` may appear
anywhere and are not checked. Both lists draw from `lib/deck/map-layouts.js`'s `ROLES`
vocabulary; a role outside that list is a schema error, not a deck-type error.
