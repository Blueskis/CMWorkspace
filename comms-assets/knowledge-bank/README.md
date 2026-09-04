# Knowledge Bank

Reusable change-communications content. Stage 3 of `cm-comms-generator` retrieves from
here, and nothing in a drafted comms pack should come from anywhere else.

Format and field rules: `skills/cm-proposal-generator/reference/knowledge-bank-guide.md`
(shared unchanged — the schema and field rules are identical, only the folder set below
differs from the proposal bank's).
Schema: `skills/cm-proposal-generator/schemas/kb_entry.schema.json`.

## Folders

| Folder | Holds |
|---|---|
| `narrative/` | The change narrative — framing, the case for change, what stays the same |
| `channel-examples/` | Structures and worked examples per channel (deck outlines, email shapes) |
| `tone-and-style/` | House voice defaults — tense, person, acronym handling, confirmed/unconfirmed phrasing |
| `faqs/` | Real and anticipated questions with answer shapes, reused across runs |
| `glossary/` | Domain and system terms with plain-language glosses for first use |

## Contents

The `*-EXAMPLE.md` files show the entry format. **They are format exemplars with invented
content — delete them before real use**, or they'll be retrieved into a real comms pack.
Every other file should be genuine firm content.

## Indexing

```bash
python skills/cm-proposal-generator/scripts/index_kb.py comms-assets/knowledge-bank -o kb_index.json
python skills/cm-proposal-generator/scripts/retrieve.py kb_index.json --section narrative --tags payroll
```

The indexer and retriever are `cm-proposal-generator`'s scripts, reused unchanged — the
indexer derives `section` from the top-level folder under the bank root, so it indexes
this bank with no code change. Re-index after adding or editing entries — retrieval reads
the index, not the files.
