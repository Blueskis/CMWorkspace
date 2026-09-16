---
name: deck-builder-v0.1
description: Builds a consulting slide deck — steerco update, case for change, findings and recommendations, workshop pack, readiness assessment, roadmap, board paper — from a client's brand (a file, an existing .potx, or keyed in by hand), the client's approved slide template, and a folder of source documents (Word, PDF, PowerPoint, Excel, VTT/SRT transcripts, BPMN). Runs a five-stage pipeline — ingest documents and vision-read any PDFs/images into citable notes, brief the narrative and key messages, plan slide-by-slide against the template's own layouts with hard fit/variety/provenance gates, assemble the .pptx, and QA it before handover. Uses BM25 retrieval over a chunk index (never embeddings — a ranking a practitioner can't reason about can't be debugged when it pulls the wrong clause), and never builds from an unapproved or absent template. Use whenever a consultant wants a first-draft deck built from source material and an approved template — phrases like "build me a deck from these documents", "turn this FSD/workshop notes/interview transcripts into a steerco deck", "put this on our template", "draft a case for change deck". Do NOT use for an FSD-sourced learner deck with screenshot annotation and knowledge checks — that is `training-material-generator`. Do NOT use for an RFP response — that is `cm-proposal-generator`, which carries requirement-coverage QA and knowledge-bank retrieval this skill does not replicate. Do NOT use for a single-channel comms artifact (email, banner, newsletter) — that is `cm-comms-generator`. Do NOT use to review or QA a deck that already exists — that is `training-qa-agent` for training material, or a plain read for anything else.
---

# Deck builder

Takes a client's approved template, a brand (extracted from that template, from a Brand
Vault export, or keyed in by hand), and a folder of source documents, and produces a
first-draft `.pptx` on that template — never a lookalike. **The point of this skill is
that a deck built from real client documents reads like a human built it minus the final
review pass**, which in practice means three mechanical things get checked before a
single slide is assembled: layouts vary, text fits the placeholder it's actually going
into, and every claim traces to a source or is marked an explicit gap.

## MVP scope (read this before promising anything)

| In scope | Out of scope (v0.1) |
|---|---|
| `.docx`, `.pptx` (as source), `.xlsx`/`.csv`, `.vtt`/`.srt`, BPMN ingestion (via `ingest_sources.py`) | `.doc`/`.xls`/`.ppt` legacy formats |
| PDF text via `pdftotext` sidecar or poppler (via `map_source.py`) | PDF text with neither available — the run stops and names the fix |
| Vision reading of PDFs/images into citable `vision_notes.json` | OCR of scanned text — vision reading transcribes what is SEEN, not what a scanner would recognise |
| BM25 retrieval with query expansion, section-path boost, RRF fusion | Embedding/semantic search |
| Nine deck types from `lib/schemas/deck_registry.json` | A deck type outside that registry — the run stops rather than guessing a role sequence |
| Building on the client's own `.potx`/`.pptx` template, layout-mapped by placeholder signature | Building from scratch when no template is supplied — the run stops and asks |
| Native diagrams, tables and images via the shared `lib/deck/` assembler | Screenshot annotation (highlight/callout/arrow/redact/zoom) — use `training-material-generator` |
| Plan-time fit and layout-variety hard gates | Auto-shrinking text below the legibility floor to force a fit |
| Mechanical QA: plan validation, file validation, placeholder-text sweep | Automated visual QA — rendering and looking is still a human/subagent step |

## Pipeline

```
brand + template + docs ─▶ intake/            ─▶ deck_brief.json ─▶ deck_plan.json ─▶ deck.pptx ─▶ qa_report.md
        INTAKE (1)                                  BRIEF (2)         PLAN (3)       BUILD (4)      QA (5)
```

Every stage writes a file, so a run resumes or is audited from any point.

### Run workspace

```
decks/<client-slug>-<YYYYMMDD>/
├── intake/
│   ├── ingested/                 # ingest_sources.py output — text + manifest
│   ├── source_map.json           # map_source.py — the complete-coverage outline
│   ├── template_profile.json     # lib/deck/cli/profile.mjs
│   ├── assignment.json           # resolveLayoutRoles() — the layout-role mapping
│   ├── brand_profile.json        # lib/brand_profile.py
│   ├── chunk_index.json          # lib/deck_index.py — BM25 index, incl. vision chunks
│   └── vision_notes.json         # written by hand per reference/vision-reading.md, if needed
├── deck_brief.json
├── deck_plan.json
├── plan_validation.json
├── deck.pptx
└── qa_report.md
```

`decks/` is gitignored, matching `training/` and `comms/`.

## Stage 1 — Intake

```bash
python skills/deck-builder/scripts/intake.py <sources_dir> \
    --template <client>.potx --deck-type steerco-update \
    [--brand brand_profile.json] --client "Acme Water" \
    -o decks/<run>/intake/
```

Orchestrates `ingest_sources.py`, `map_source.py`, the template profile, layout
assignment, brand resolution, and the retrieval index — see `intake.py`'s own docstring
for the exact five sub-steps. `--template` is required; there is no from-scratch route.

If any source is a PDF or image, the command lists it and stops short of indexing it as
prose. Read `reference/vision-reading.md`, rasterise, write `vision_notes.json`, then
re-run the index step: `python lib/deck_index.py index intake/source_map.json
intake/vision_notes.json -o intake/chunk_index.json`.

**Report back before continuing**: the layout mapping in `assignment.json` and
`layout_notes.json` is a proposal, not a decision — review it against
`reference/layout-fidelity.md` and correct any role assignment that looks wrong for this
template before Stage 3 builds on it. If `brand_profile.json` has no `approval` block
(the normal case for a freshly extracted or from-vault profile), get it approved before
Stage 4, or the deck is a lookalike whatever its origin.

## Stage 2 — Brief

Write `deck_brief.json` (schema: `schemas/deck_brief.schema.json`) by hand or with the
model's help: the narrative spine for the chosen `deck_type` (from
`reference/deck-types.md`), and the key messages with their supporting `chunk_id`/
`vision::note_id` references. Query the index while drafting:

```bash
python lib/deck_index.py query decks/<run>/intake/chunk_index.json \
    --query "approval threshold" --brand decks/<run>/intake/brand_profile.json --top 6
```

## Stage 3 — Plan

Write `deck_plan.json` (schema: `schemas/deck_plan.schema.json`) — the native shape
`lib/deck/build-pptx.js`'s assembler consumes directly, one module per section of the
brief, one slide per key message plus structural slides (title, section headers,
closing). Every block cites a `sources[]` entry or is `gap: true` with a `gap_note`.

```bash
python skills/deck-builder/scripts/plan_deck.py decks/<run>/deck_plan.json \
    --deck-type steerco-update \
    --profile decks/<run>/intake/template_profile.json \
    --assignment decks/<run>/intake/assignment.json \
    [--vision-notes decks/<run>/intake/vision_notes.json] \
    -o decks/<run>/plan_validation.json
```

Hard fails: unknown/missing deck-type roles, text overflow, more than two consecutive
slides on one layout, missing provenance, a claim resting solely on a low-confidence
vision note. Fix the plan and re-run until it passes — see `reference/layout-fidelity.md`
and `reference/vision-reading.md` for what each failure means and how to fix it.

## Stage 4 — Build

```bash
node lib/deck/cli/assemble.mjs \
    --plan decks/<run>/deck_plan.json \
    --template <client>.potx \
    --profile decks/<run>/intake/template_profile.json \
    --assignment decks/<run>/intake/assignment.json \
    --assets-dir decks/<run>/intake/assets \
    -o decks/<run>/deck.pptx
```

There is no Python OOXML assembler in this repo — `lib/deck/build-pptx.js` (moved here
from the browser artifact, see its own header) is the only one, called from Python via
`node` exactly as `cm-comms-generator`'s `build_docx.py` already calls `node` for the
docx-js build. It strips the template's own example slides, writes speaker notes
(synthesising a notes master if the template lacks one), and aspect-fits every image —
never stretched.

## Stage 5 — QA

```bash
python skills/deck-builder/scripts/qa_deck.py decks/<run>/deck.pptx \
    --template <client>.potx --plan-validation decks/<run>/plan_validation.json \
    -o decks/<run>/qa_report.md
```

Refuses to call a deck clean if its own plan never passed. Runs the pptx skill's
`office/validate.py --original` and a `markitdown` placeholder-text sweep. **Visual QA is
not automated** — render and look at every slide per `reference/visual-qa.md` before
handover.

Two invariants, enforced mechanically:

- **Provenance** — every content block traces to a chunk_id, a vision note_id, or carries
  an explicit `gap: true` + `gap_note`. No third state.
- **Fidelity** — the deck is built on the client's own template, never a lookalike; every
  layout choice traces to `assignment.json`'s reasoning.

## Notes

- The template profiler used throughout this skill is `lib/deck/cli/profile.mjs` (the JS
  one, via pdf.js/xml.js), **not** `lib/profile_template.py` — the two are not
  interchangeable; the JS profiler carries `slide_size` and `example_slides`, which the
  assembler and fit-checker both need. See `lib/deck/cli/profile.mjs`'s own header.
- `lib/deck_index.py` and `lib/deck/retrieve.js` are independently-implemented BM25
  twins, kept in parity by `webapp/test/retrieve-parity.mjs`. Not embeddings — see that
  file's own docstring for why.
- Depends on the bundled `pptx` skill (`office/validate.py`, `thumbnail.py`,
  `soffice.py`) for file validation and rendering — never re-implemented here.
- Rasterisation uses `node lib/deck/cli/rasterise.mjs` (pdf.js), not `pdftoppm` — poppler
  is not guaranteed to be installed, and pdf.js is already a dependency for parsing.
  `soffice --convert-to pdf` is still used to turn the built `.pptx` into a PDF first.
- **Always hand the output over as a first draft for the practitioner to review, never as
  a client-ready file.** Say so explicitly at handover.

## Layout

```
skills/deck-builder/
├── SKILL.md
├── reference/          # deck-types, layout-fidelity, vision-reading, visual-qa, brand-intake
├── schemas/             # deck_brief, deck_plan (vision_notes lives in lib/schemas/)
├── scripts/             # intake.py, plan_deck.py, qa_deck.py
└── tests/               # CASES.md — the plain-language test list this build was written against
lib/
├── deck/                # shared JS core (moved from webapp/src/) — env, xml, profile-template,
│                         #   map-layouts, text-fit, render-diagram, build-pptx, parse-*, qa,
│                         #   fit-check, retrieve; cli/ — profile.mjs, assemble.mjs, check-fit.mjs,
│                         #   rasterise.mjs
├── brand_profile.py      # canonical brand adapter/validator
├── deck_index.py         # BM25 index + query (promoted from training-material-generator)
└── schemas/              # brand_profile, deck_registry, vision_notes
```
