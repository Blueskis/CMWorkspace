# past-rfps

Requirement chapters and response text from tenders we have already answered. See
`../README.md` for the entry format and `../../../skills/cm-proposal-generator/reference/knowledge-bank-guide.md`
for the field rules.

## What belongs here

Not the tender PDFs — those are documents, and a document is not retrievable content.
What belongs here is what a past tender **taught us**, written as entries Stage 4 can pull:

- **Requirement patterns that recur.** "Public-sector ERP tenders in this region always
  specify class sizes, languages and re-run obligations for training" is worth an entry,
  because the next one will too and the response can be ready rather than assembled.
- **The client's own vocabulary.** Which authorities call it a Change Sustenance Plan,
  which call it Transition Management. Stage 2 has to mirror the client's term, and this
  is where the mapping is remembered.
- **Response text that was actually scored.** With the `bid.outcome` and, where the
  debrief gave one, `bid.sections_that_scored`.

## Why `outcome` is not optional

Language from a losing bid reads exactly as well as language from a winning one. Reusing
it without knowing which it was is the specific failure this folder creates the
opportunity for, so the `bid` block carries `outcome` and `outcome_notes`. `unknown` is a
legitimate value — a guess is not.

## Getting content in

```bash
# PDFs first: extract with the `pdf` skill, then ingest the text
python skills/cm-proposal-generator/scripts/ingest_source.py past-bids/authority-2025.txt \
    -o proposal-assets/knowledge-bank/past-rfps/authority-erp-2025.md \
    --outcome lost --client-ref "anonymised: national health authority"
```

`ingest_source.py` writes a **draft**: one file per source document, clearance
`internal-only`, metrics unverified. Split it into single-idea entries and clear it before
it can reach a bid — a whole tender ingested as one entry retrieves as one lump.
