# presentations

Content lifted from past proposal decks and client-facing presentations. See
`../README.md` for the entry format.

## What belongs here, and what belongs elsewhere

This folder is for **slide-shaped content that worked** — a phase diagram whose framing
landed, a governance table clients keep asking to keep, an executive-summary structure
that reads well in one page. Content that happens to have come from a deck but is really
methodology, a case study, or a credential belongs in *those* folders. The section drives
retrieval, so filing by where content came from rather than what it is makes it
unfindable.

A useful test: if Stage 4 would want this while planning a methodology slide, it goes in
`methodology/`. It goes here only if its value is bound up in how it was *presented*.

## Why not just point the pipeline at a folder of .pptx files

Because a deck is not retrievable. Stage 4 pulls entries whole and adapts them to this
client, which needs prose it can rewrite — not a slide it can only copy. Copying a slide
from the last client's deck is how the last client's name ends up in this one's.

## Getting content in

```bash
python skills/cm-proposal-generator/scripts/ingest_source.py past-bids/retail-2025.pptx \
    -o proposal-assets/knowledge-bank/presentations/retail-2025.md \
    --outcome won --client-ref "anonymised: grocery retailer"
```

That writes one draft per deck, marked `internal-only` with metrics unverified. A twelve-
slide deck is not one entry — split it into single-idea entries, rewrite each as substance
rather than as pitch copy aimed at the previous client, verify every number, then clear
it. Until `clearance` changes, retrieval will not return it, which is the intended
behaviour rather than a problem to work around.
