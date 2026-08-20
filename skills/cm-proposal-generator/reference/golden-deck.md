# The golden deck — curated slides as the knowledge bank

The reusable content comes from **one curated deck**: the best slides we have actually
used, chosen by the people who used them, with a short tag block in each slide's speaker
notes.

This is a better source than mining whole past decks, for a reason worth stating. The hard
part of extraction is not reading a file — it is knowing where one idea stops and the next
begins. A case study spanning three slides has to be merged; a divider slide has to be
dropped; a slide that reads well only after the one before it is useless on its own.
Nothing mechanical can tell. A deck whose slides were each chosen deliberately has already
had that judgement applied, so **one slide really is one entry**.

## What a curator does

1. Assemble a deck of slides worth reusing. One idea per slide — if a point needs three
   slides, either merge them onto one or accept three entries that each stand alone.
2. Put a tag block in each slide's **speaker notes**. Invisible when presenting, and the
   only place per-slide metadata can live without cluttering the slide.
3. Nothing else. No spreadsheets, no forms, no filenames to get right.

## The tag block

```
section: methodology
tags: change-management, erp, training
clearance: anonymised
metrics: verified
outcome: won
client: Metro Transit
```

Ordinary speaker notes can sit above or below it; only recognised keys are read.

| Key | Required | What it does |
|---|---|---|
| `section` | **yes** | One of `methodology`, `case-studies`, `credentials`, `team`, `commercials`, `boilerplate`. Decides which folder the entry lands in and what it can be retrieved for. A slide without it is **skipped and reported** — not silently dropped. |
| `tags` | strongly | Comma-separated, lower-case, hyphenated. The only thing retrieval matches on, and matching is **literal**: `financial-services` and `finserv` never meet. Left blank, tags are guessed from the CM vocabulary, which is a worse guess than yours. |
| `clearance` | | `named`, `anonymised` or `internal-only`. Defaults to `internal-only`, which **excludes the entry from every deck** until someone changes it. |
| `metrics` | | `verified` if someone has checked every number on the slide is one we would still stand behind. Anything else means no figure from it ships. |
| `outcome` | | `won`, `lost`, `no-bid`, `withdrawn`, `pending`, `unknown`. Language from a losing bid reads exactly as well as language from a winning one. |
| `client` | | The client, or an anonymised handle. Only meaningful alongside `clearance`. |

**Two of these are commitments, not labels.** `clearance: named` asserts that the client
agreed to be referenced in our marketing and bids. `metrics: verified` asserts that a
number is still true and defensible in a live tender. Both default to the restrictive
value precisely because getting them wrong is expensive, and neither can be inferred from
the file. If a curator is unsure, leaving them out is the correct answer.

## Turning the deck into entries

```bash
python skills/cm-proposal-generator/scripts/ingest_source.py golden-deck.pptx \
    --golden-deck -o proposal-assets/knowledge-bank
```

One `.md` per slide, filed by its `section`, with frontmatter built from the tag block and
the slide's own text as the body. Footers, slide numbers and dates are dropped — every
slide carries them, and they are not content.

Slides that cannot become entries are named on stderr with the reason, and the command
exits non-zero. That is a worklist for the curator, not a failure: a slide nobody tagged is
a slide nobody can retrieve, which looks exactly like a slide that was never added.

Then rebuild the index and the intake page:

```bash
python skills/cm-proposal-generator/scripts/index_kb.py proposal-assets/knowledge-bank \
    -o kb_index.json
python tools/bid-intake-desk/build.py
```

Entries reach a generated deck only after that rebuild and a republish, so this is a
periodic step — run it when the golden deck has changed, not per slide.

## What this deck is not

**It is not the visual template.** Branding is separate: each tender is styled to the
client's own identity, and the generated deck's colours, fonts and master come from
whatever template it is built against — not from here. Only the words and the structure
are taken from the golden deck. When a per-client brand template exists, it plugs into
`render_pptx.py` in place of the generic one and nothing here changes.
