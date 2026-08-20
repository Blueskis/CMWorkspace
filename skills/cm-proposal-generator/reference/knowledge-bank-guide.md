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
└── boilerplate/     # standard clauses — data protection, D&I, exec-summary scaffolds
```

Past tenders and past decks are **not** here — they live in Airtable
(`CM Knowledge Bank → Proposals and Tenders`). That table holds documents; these folders
hold the prose extracted from them, which is what Stage 4 actually writes slides from.
`ingest_source.py` is the bridge, and it files entries by what the content **is** rather
than which bid it came from. See `reference/airtable-source.md`.

**How a past bid becomes entries.** A colleague adds the bid to Airtable and attaches its
deck — that is the whole of what they do. Extraction is somebody else's job, and a
deliberate one: `ingest_source.py` pulls the deck's text, the draft is split into
single-idea entries, the three judgement fields are set, and the result is committed here.
The intake page bakes this folder in at build time, so entries reach a deck only after that
review, and only after a republish.

One entry per Markdown file. The folder is the entry's `section`, which is how Stage 4
retrieval scopes a query. Nested subfolders are allowed and don't affect the section.

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
- **`bid`** — optional, for an entry extracted from a past bid: what it was bid for and
  how it went. Language from a losing bid reads exactly as well as language from a winning
  one, so carry `outcome` across from the Airtable record rather than losing it in the
  extraction. `unknown` is a legitimate value; a guess is not. Where a debrief named the
  sections that scored, put them in `sections_that_scored` — the most transferable thing a
  past bid holds.
- **`source_document`** — set by `ingest_source.py`. An entry drafted from a real artifact
  should be traceable to it, so a claim can be checked against its origin later.

## Ingesting past proposal decks

The **deck** is what's worth extracting — our own past response, not the client's
tender. Download it from its Airtable record, then:

```bash
python skills/cm-proposal-generator/scripts/ingest_source.py ~/Downloads/retail-2025.pptx \
    -o proposal-assets/knowledge-bank/methodology/retail-phasing.md --outcome won
```

If the deck arrived via the intake page's Stage 03 handoff instead of a manual save,
`selection.json` already carries a direct link for it
(`source_material[].proposal_deck`, each `{name, url}`) — pull it with `curl` before
running `ingest_source.py`. The link is an Airtable attachment URL and is only valid for
a couple of hours from when the page read the record:

```bash
curl -sSL -o retail-2025.pptx "<the url from selection.json>"
python skills/cm-proposal-generator/scripts/ingest_source.py retail-2025.pptx \
    -o proposal-assets/knowledge-bank/methodology/retail-phasing.md --outcome won
```

The RFP attached to the same record is the client's own tender — read it for context if
it helps judge how closely that past bid resembles the current one, but never ingest it:
its text is not ours to reuse. See `reference/airtable-source.md` for the full flow.

The destination folder is chosen by what the extracted content **is** — a phase model goes
to `methodology/`, an outcome story to `case-studies/`, a proof point to `credentials/`.

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

## Refreshing the index

Retrieval reads `kb_index.json`, never the files. Rebuild it whenever the bank changes:

```bash
python skills/cm-proposal-generator/scripts/index_kb.py proposal-assets/knowledge-bank \
    -o proposals/<run>/kb_index.json
```

The intake page needs the same records with their bodies, which `build.py` produces via
`--with-body` — an excerpt is enough to rank an entry but not to put its prose on a slide.
`index_kb.py` exits
non-zero when any entry fails to index; that is a report to read, not a failure to ignore,
because an entry that does not index is invisible to retrieval and surfaces later as an
unexplained `[GAP]`.

## Maintenance

Gaps are visible by design: every `[GAP]` in a generated deck names knowledge the bank
doesn't hold. The QA report from Stage 6 is, read another way, a prioritised backlog for
the bank. Feed it back — a bank maintained from real bid gaps beats one maintained from
guesses about what future bids might need.
