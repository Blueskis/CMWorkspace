# Knowledge Bank Guide

The knowledge bank is the firm's reusable proposal content. Stage 4 retrieves from it;
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
├── past-rfps/       # what previous tenders taught us: recurring requirements, client
│                    #   vocabulary, response text and whether it won
└── presentations/   # slide-shaped content that worked, from past decks
```

One entry per Markdown file. The folder is the entry's `section`, which is how Stage 4
retrieval scopes a query. Nested subfolders are allowed and don't affect the section.

**File by what content *is*, not where it came from.** A case study that happens to have
been lifted from a deck belongs in `case-studies/`, not `presentations/`. Retrieval scopes
by section, so an entry filed by provenance is an entry nobody finds.

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
  region, population size, change type. Retrieval is literal tag matching, so
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
- **`bid`** — for `past-rfps` and `presentations` entries: what this was bid for and how
  it went. `outcome` is the field that earns those folders their place. Language from a
  losing bid reads exactly as well as language from a winning one, and reusing it without
  knowing which is which is the specific hazard of keeping past bids at all. `unknown` is
  a legitimate value; a guess is not. Where a debrief named the sections that scored, put
  them in `sections_that_scored` — it's the most transferable thing a past bid holds.
- **`source_document`** — set by `ingest_source.py`. An entry drafted from a real artifact
  should be traceable to it, so a claim can be checked against its origin later.

## Ingesting past decks and tenders

```bash
python skills/cm-proposal-generator/scripts/ingest_source.py past-bids/retail-2025.pptx \
    -o proposal-assets/knowledge-bank/presentations/retail-2025.md --outcome won
```

Reads `.pptx`, `.docx`, `.md` and `.txt` (for a PDF, extract with the `pdf` skill first),
and writes a **draft**: frontmatter filled as far as it can honestly be, body extracted
verbatim, nothing summarised or invented.

Three defaults are deliberately inconvenient, and should stay that way:

| Field | Ingest default | Why |
|---|---|---|
| `clearance` | `internal-only` | Retrieval excludes it. A past bid cannot reach a live proposal until somebody decides it may. |
| `metrics_verified` | `false` | The numbers were true of *that* engagement. Carrying them forward is a claim, made by a person. |
| `bid.outcome` | `unknown` | The file never says whether it won. Only a human knows. |

**A drafted entry is a source to split, not a finished entry.** One idea per entry is the
rule below, and a twelve-slide deck is a dozen ideas — ingested whole, it retrieves whole
and lands in the deck as a lump.

## Writing entries that retrieve well

**Write self-contained entries.** Stage 4 pulls entries individually, so one that starts
"Building on the approach above…" arrives without the above and lands in the deck broken.

**One idea per entry.** A single file covering methodology *and* a case study *and* a bio
can't be retrieved for one without dragging in the others.

**Write the substance, not the pitch.** Stage 4 adapts entries to the client's language
and context. An entry pre-written as marketing copy for a different client adapts badly;
one that plainly states what we do and what happened adapts well.

**Include the specifics.** Numbers, durations, population sizes, system versions. Generic
content produces generic slides, which is the failure mode evaluators punish hardest.

## Maintenance

Gaps are visible by design: every `[GAP]` in a generated deck names knowledge the bank
doesn't hold. The QA report from Stage 6 is, read another way, a prioritised backlog for
the bank. Feed it back — a bank maintained from real bid gaps beats one maintained from
guesses about what future bids might need.
