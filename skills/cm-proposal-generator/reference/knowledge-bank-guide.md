# Knowledge Bank Guide

The knowledge bank is the firm's reusable proposal content. Stage 3 retrieves from it;
nothing in a generated deck should come from anywhere else.

## Layout

```
proposal-assets/knowledge-bank/
├── methodology/     # CM approach, phases, activities, deliverables, artifacts
├── case-studies/    # past engagements with outcomes and metrics
├── credentials/     # firm-level proof points, accreditations, differentiators
├── team/            # practitioner bios and role profiles
├── commercials/     # engagement models, rate-card structure, assumption boilerplate
├── boilerplate/     # standard clauses — data protection, D&I, exec-summary scaffolds
│
│                    # read by cm-comms-generator, not by this skill:
├── comms-collateral/    # past comms that landed well, tagged by channel
├── comms-tone/          # voice and style guidance
└── comms-boilerplate/   # help routes, accessibility statements, reassurance scaffolds
```

One entry per Markdown file. The folder is the entry's `section`, which is how Stage 3
retrieval scopes a query. Nested subfolders are allowed and don't affect the section.

**The bank is shared between both skills, and `--strict-section` is what keeps them apart.**
Passing `--section` alone only adds +2 to an entry's score, so a comms entry tagged `erp` can
outrank a weakly-tagged methodology entry and surface in a live bid. Always pass the flag.

## Entry format

YAML frontmatter, then Markdown body. Validated against
`skills/cm-proposal-generator/schemas/kb_entry.schema.json`.

```markdown
---
id: cs-globalbank-workday          # unique, kebab-case, stable — plan files reference it
title: Workday HR transformation, global retail bank
tags: [workday, hris, financial-services, emea, 10k-plus]
clearance: named                   # named | anonymised | internal-only
last_reviewed: 2026-05-14
owner: j.okafor
metrics_verified: true             # required true for any entry stating a number
---

## Situation
...

## What we did
...

## Outcome
Adoption reached 87% of the target population within 90 days of go-live.
```

### Field notes

- **`id`** — referenced by `sources` in `proposal_plan.json`, so renaming one breaks the
  provenance trail of every past run. Treat as immutable once used.
- **`tags`** — the retrieval surface. Tag generously and consistently: sector, system,
  region, population size, change type. Retrieval is literal tag matching in v0.1, so
  `financial-services` and `finserv` are two different tags and only one will match.
- **`clearance`** — governs whether the client's real name can appear in a deck:
  - `named` — client agreed to be referenced; use the name.
  - `anonymised` — describe as "a global retail bank"; **never** name them.
  - `internal-only` — do not use in client-facing material at all. Retrieval excludes
    these by default.
- **`last_reviewed`** — entries older than 24 months are flagged stale in retrieval
  output. Stale isn't unusable, but the practitioner should confirm before it ships.
- **`metrics_verified`** — must be `true` for any entry whose body states a number.
  Unverified metrics are the single most dangerous content in a bid: they're specific,
  quotable, and contractually awkward when wrong.

## Writing entries that retrieve well

**Write self-contained entries.** Stage 3 pulls entries individually, so one that starts
"Building on the approach above…" arrives without the above and lands in the deck broken.

**One idea per entry.** A single file covering methodology *and* a case study *and* a bio
can't be retrieved for one without dragging in the others.

**Write the substance, not the pitch.** Stage 3 adapts entries to the client's language
and context. An entry pre-written as marketing copy for a different client adapts badly;
one that plainly states what we do and what happened adapts well.

**Include the specifics.** Numbers, durations, population sizes, system versions. Generic
content produces generic slides, which is the failure mode evaluators punish hardest.

## Maintenance

Gaps are visible by design: every `[GAP]` in a generated deck names knowledge the bank
doesn't hold. The QA report from Stage 5 is, read another way, a prioritised backlog for
the bank. Feed it back — a bank maintained from real bid gaps beats one maintained from
guesses about what future bids might need.
