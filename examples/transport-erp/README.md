# Sample Input — Transport company, ERP transformation (CM requirements)

The second standing sample. `examples/cfs-ch8/` is a public-sector chapter written in
"shall"; this is a commercial ERP tender written in **"should"**, and the contrast is the
point — the two exercise different parts of the pipeline.

## Anonymisation

Verified before committing, not assumed:

- **No party is named.** Every reference is generic — *the Tenderers* (16), *the Client*
  (7). No company, no department, no individual.
- **No emails, URLs, phone numbers, prices or dates** anywhere in the text.
- Every multi-word proper noun is a domain term: *Change Management Plan*, *Power User*,
  *Stakeholder Impact Assessment*, *Invoice Verification*.
- **Word metadata was stripped.** `docProps/core.xml` carried an author name in
  `dc:creator` and `cp:lastModifiedBy`. Text extraction cannot see those fields, which is
  exactly why they get missed. The copy here has both emptied.

## What makes it a good test

**It says "should", not "shall".** 85 `should`, 30 `must`, zero `shall`. Two consequences,
and both bit the pipeline before they were fixed:

- Deliverable detection looked only for `shall provide` and friends, so it found **nothing**
  in this document. `DELIVERABLE_CUES` is now built from all three modals.
- Per `reference/rfp-extraction.md`, `should` normalises to **desirable**, so a
  requirement-by-requirement read produces a brief that is almost entirely desirable. That
  is a real trap rather than a bug: a bid team that treats "should" as optional will
  under-answer a document where every clause is still scored. Record `raw_priority` and
  say so at the Stage 2 read-back.

**Its clause numbering runs six levels deep.** `2.3.2.2.2.4` is a real reference here. The
splitter allowed five components and silently matched none of the deepest clauses.

**Its headings are welded to their body text.** Word stores several headings in the same
run as the sentence that follows, so extraction yields
`2.3.1.1 Change Management StrategyThe Tenderers should provide…`. `unglue()` splits at
the lowercase-to-capital boundary when what precedes it could stand as a title.

**It is almost entirely CM.** 11 sections, 5 cm-core and 6 cm-adjacent, none set aside —
so unlike a full tender it does not exercise the "what did we ignore" half of triage. Use
it for extraction and sizing; use a whole tender for triage.

## Files

| File | What it is |
|---|---|
| `inputs/Transport-Company-RFP.docx` | The source, metadata stripped |
| `inputs/Transport-Company-RFP.txt` | Extracted text |
| `rfp_triage.json` | Stage 1 output — 11 sections scored |

## Reproduce

```bash
python3 -c "
import sys; sys.path.insert(0,'skills/cm-proposal-generator/scripts')
from ingest_source import read_docx
from pathlib import Path
print('\n'.join(t for _, t in read_docx(
    Path('examples/transport-erp/inputs/Transport-Company-RFP.docx'))))" \
  > examples/transport-erp/inputs/Transport-Company-RFP.txt

python skills/cm-proposal-generator/scripts/triage_rfp.py \
    examples/transport-erp/inputs/Transport-Company-RFP.txt \
    -o examples/transport-erp/rfp_triage.json
```

## Known blocker for Stages 2–6

This is section 2.3 of a larger tender. It carries no evaluation criteria, no weights, no
submission deadline and no response format — so section sizing has to come from the
deliverables the document names, and that assumption gets recorded rather than hidden.
