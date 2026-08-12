# Knowledge Bank

Reusable proposal content. Stage 3 of `cm-proposal-generator` retrieves from here, and
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
