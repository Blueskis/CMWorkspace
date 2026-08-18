# presentations — moved to Airtable

Past proposal decks live in **Airtable**:
`CM Knowledge Bank → Proposals and Tenders`. Nothing belongs in this folder any more.

Keeping a Markdown copy alongside would make two sources of truth for one section, and
they would drift. `index_kb.py` warns if it finds an entry here for exactly that reason.

## What Airtable holds, and what it does not

An Airtable row is a **past project**: the tender document, the proposal deck, the
location, the price. Those are documents.

The generator does not write slides from documents. Stage 4 retrieves an entry and adapts
its *prose* to the new client, so a PDF attachment cannot become a slide — someone has to
extract what the bid taught us first:

```bash
python skills/cm-proposal-generator/scripts/ingest_source.py <downloaded-deck>.pptx \
    -o proposal-assets/knowledge-bank/methodology/<name>.md
```

The extracted entries land in `methodology/`, `case-studies/`, `credentials/`, `team/`,
`commercials/` and `boilerplate/` — filed by what the content **is**, not by which past bid
it came from. That is what the deck is written from.

So the relationship is: **Airtable is the input to the bank, not the bank itself.**
