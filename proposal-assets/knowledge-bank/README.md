# Knowledge Bank

Reusable content for every `cm-workspace` skill. `cm-proposal-generator` retrieves from here
at its Stage 3 and `cm-comms-generator` at its Stage 3, and nothing in a generated deck or
draft should come from anywhere else.

Named `proposal-assets/` for the first skill that used it; it is now the shared asset root.

Format and field rules: `skills/cm-proposal-generator/reference/knowledge-bank-guide.md`.
Schema: `skills/cm-proposal-generator/schemas/kb_entry.schema.json` — one schema, used by both
skills unchanged.

## Folders

| Folder | Holds | Read by |
|---|---|---|
| `methodology/` | CM approach, phases, activities, deliverables, artifacts | proposal |
| `case-studies/` | Past engagements with outcomes and metrics | proposal |
| `credentials/` | Firm-level proof points, accreditations, differentiators | proposal |
| `team/` | Practitioner bios and role profiles | proposal |
| `commercials/` | Engagement models, rate-card structure, assumption boilerplate | proposal |
| `boilerplate/` | Standard clauses — data protection, D&I, exec-summary scaffolds | proposal |
| `comms-collateral/` | Past comms that landed well, tagged by channel | comms |
| `comms-tone/` | Voice and style guidance, house and per-client | comms |
| `comms-boilerplate/` | Help routes, accessibility statements, sign-offs, reassurance scaffolds | comms |

## Isolation — always pass `--strict-section`

The section is the boundary between the two skills' content, and **`--strict-section` is what
enforces it**. Without the flag, `--section` merely adds +2 to an entry's score: a comms entry
tagged `erp` can outrank a weakly-tagged methodology entry and surface in a live bid.

Every retrieval call in both skills passes it. The section is the boundary; the tag is the
ranking.

## Contents

The `*-EXAMPLE.md` files show the entry format. **They are format exemplars with invented
content — delete them before real use**, or they'll be retrieved into a real bid. Every
other file should be genuine firm content.

## Indexing

```bash
python skills/cm-proposal-generator/scripts/index_kb.py proposal-assets/knowledge-bank -o kb_index.json
python skills/cm-proposal-generator/scripts/retrieve.py kb_index.json --section methodology --tags erp --strict-section
```

Re-index after adding or editing entries — retrieval reads the index, not the files.
