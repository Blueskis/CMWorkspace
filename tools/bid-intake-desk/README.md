# Bid Intake Desk

A browser front end for the first half of `cm-proposal-generator`: read a tender, see
which clauses are change management's to answer, and choose the knowledge-bank entries
the proposal should be written from.

**It is the intake half only.** It does not build the deck — it produces a selection and
the commands to carry on with in the repo.

## Why it exists

The two decisions this page supports are the two that are genuinely a person's:

1. **Which parts of a 200-page tender are ours.** The page runs the same triage as
   `triage_rfp.py` and shows both lists — CM-relevant and set aside — because a section
   in neither was never read.
2. **Which past work this bid should be written from.** It ranks the bank the way
   `retrieve.py` ranks it and shows the matched tags, so the ranking can be argued with.

## It runs the real logic, not a mock-up

The lexicon, the clause splitter, the verdict thresholds and the retrieval weights are
ported line-for-line from `triage_rfp.py` and `retrieve.py`. On the sample tender the
page and the CLI agree exactly: 33 cm-core, 19 cm-adjacent, the same four cross-
references. If the Python changes, this has to change with it.

Files are read in the browser and never uploaded. `.txt`, `.md`, `.docx` and `.pptx` are
read directly — OOXML is a ZIP of XML, and `DecompressionStream` opens it without a
library. **PDFs cannot be read in a browser**; extract the text first and drop the `.txt`.

## The one thing it does differently

Retrieval tags are seeded from **the bank's own vocabulary found in the tender**, not
from the CM lexicon. Deriving them from the lexicon looks reasonable and retrieves
nothing: the lexicon names the work (`change-readiness`) while a bank is tagged by sector
and system (`erp`, `public-sector`), so the two namespaces never meet. Only a tag the
bank already uses can ever match.

## Build

```bash
python skills/cm-proposal-generator/scripts/index_kb.py proposal-assets/knowledge-bank \
    -o tools/bid-intake-desk/kb_index.json
python tools/bid-intake-desk/build.py
```

`index.src.html` is the source; `index.html` is it with the bank and the sample tender
baked in, which is what gets published as the artifact. Never edit `index.html` — the
next build overwrites it.

The embedded bank is a starting point so the page opens with something to show. A viewer
can load their own `kb_index.json` from the page without rebuilding.
