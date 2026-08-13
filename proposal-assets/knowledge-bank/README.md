# Knowledge Bank

Reusable proposal content. Stage 4 of `cm-proposal-generator` retrieves from here, and
nothing in a generated deck should come from anywhere else.

Format and field rules: `skills/cm-proposal-generator/reference/knowledge-bank-guide.md`.
Schema: `skills/cm-proposal-generator/schemas/kb_entry.schema.json`.

## Folders

| Folder | Holds |
|---|---|
| `methodology/` | CM approach, phases, activities, deliverables, artifacts |
| `case-studies/` | Past engagements with outcomes and metrics |
| `credentials/` | Firm-level proof points, accreditations, differentiators |
| `team/` | Practitioner bios and role profiles |
| `commercials/` | Engagement models, rate-card structure, assumption boilerplate |
| `boilerplate/` | Standard clauses — data protection, D&I, exec-summary scaffolds |
| `past-rfps/` | What previous tenders taught us: recurring requirements, the client's own vocabulary, and whether the response won |
| `presentations/` | Slide-shaped content that worked, drawn from past decks |

File by what the content **is**, not where it came from: a case study lifted from a deck
belongs in `case-studies/`. Retrieval scopes by folder, so filing by provenance hides it.

## Contents

The `*-EXAMPLE.md` files show the entry format. **They are format exemplars with invented
content — delete them before real use**, or they'll be retrieved into a real bid. Every
other file should be genuine firm content.

## Indexing

```bash
python skills/cm-proposal-generator/scripts/index_kb.py proposal-assets/knowledge-bank -o kb_index.json
python skills/cm-proposal-generator/scripts/retrieve.py kb_index.json --section methodology --tags erp
```

Re-index after adding or editing entries — retrieval reads the index, not the files.

## Ingesting a past deck or tender

```bash
python skills/cm-proposal-generator/scripts/ingest_source.py past-bids/retail-2025.pptx \
    -o proposal-assets/knowledge-bank/presentations/retail-2025.md --outcome won
```

Handles `.pptx`, `.docx`, `.md`, `.txt`. Writes a **draft** marked `internal-only` with
metrics unverified, so it cannot be retrieved into a bid until somebody splits it into
single-idea entries, checks the numbers, and clears it.
