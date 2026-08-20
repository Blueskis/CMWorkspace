# Airtable as the source for past RFPs and past proposals

Past tenders and past proposal decks live in Airtable rather than in Markdown
files: **CM Knowledge Bank → Proposals and Tender**. The other six sections
(`methodology`, `case-studies`, `credentials`, `team`, `commercials`, `boilerplate`) stay
as Markdown in this folder.

Whichever store an entry comes from, it has to arrive at retrieval as the same record —
`kb_index.json` stays the one interchange format, and `retrieve.py` never learns where an
entry came from.

## What the table actually holds

`CM Knowledge Bank → Proposals and Tenders` (`appAi9h5mT0hPz5o2` / `tblxQyGlAV81vz3ES`):

| Field | Type |
|---|---|
| Project Name | Single line text (primary) |
| Location | Single select |
| RFP Document | Attachments |
| Proposal (pptx) Deck | Attachments |
| Quoted Price for CM | Single line text |

**This is a register of past projects, not retrievable content.** One row is one bid,
with the tender and the deck attached. That is a good way to keep bid records and a poor
way to feed a generator: Stage 4 retrieves an entry and adapts its *prose* to the new
client, and an attached PDF is a file, not prose. The two jobs are different and both
are needed — the register tells you which past bid resembles this one, and
`ingest_source.py` turns that bid's documents into entries the generator can write from.

## What the register is for

One question the prose bank structurally cannot answer: **have we bid something
like this before, and how did it go?** An entry is an idea; only the register knows about
bids. Stage 02 ranks past projects against the tender and orders them most-similar-first,
so the answer points at a specific deck worth mining.

Neither the page nor the pipeline can read an attachment straight out of Airtable — the
files live on a host the artifact's CSP blocks, and this environment's network policy
blocks the same hosts by default. `sync_airtable.py` closes that gap once those hosts are
allowlisted and `AIRTABLE_TOKEN` is set; until then the deck is downloaded by hand from
the record's own Airtable page and run through `ingest_source.py` directly — the page
itself has no drafting step of its own.

Three columns carry the ranking:

| Field | Type | What it does |
|---|---|---|
| Tags | Multiple select | +3 per tag shared with the tender. The only thing matched on; without it rows can only be ordered by name. Use the same vocabulary as the knowledge bank — matching is literal. |
| Outcome | Single select — `won`, `lost`, `no-bid`, `withdrawn`, `pending`, `unknown` | ±2. A won bid is worth mining ahead of a lost one, but only just: a lost bid on the same subject still outranks a won one on a different subject. |
| Submitted | Date | −2 beyond 24 months, so an old bid is surfaced as old rather than quietly reused. |

**These three are matched by value shape, not field id.** The other five columns are read
by id, so a rename cannot empty them; these were added after their ids were last observed
here, and guessing an id would be worse than not reading the column. So Tags is recognised
as the multiple-select, Outcome as the single choice whose name is one of the six, and
Submitted as the only ISO date — looking only at columns no known id has claimed. Rename
them freely; retype them and the page stops seeing them.

## Tags must match the rest of the bank

Retrieval is literal tag matching. `financial-services` and `finserv` are two different
tags and only one will match; so are `Public Sector` and `public-sector`. Use a
**Multiple select** rather than free text so Airtable enforces the vocabulary, and seed
its options from the tags already in the Markdown bank:

```bash
python skills/cm-proposal-generator/scripts/index_kb.py proposal-assets/knowledge-bank \
    -o /tmp/kb_index.json
python3 -c "
import json, collections
idx = json.load(open('/tmp/kb_index.json'))
counts = collections.Counter(t for e in idx['entries'] for t in e['tags'])
print('\n'.join(f'{n:>3}  {t}' for t, n in counts.most_common()))"
```

Lowercase kebab-case throughout, matching what is already there.

## One entry per idea, not one per document

The rule that applies to the Markdown bank applies here: retrieval pulls a record whole
and adapts it to the client. A twelve-slide deck pasted into one Content cell retrieves
as a twelve-slide lump. Split it — a methodology record, a case study, a set of
credentials — and let `Source document` carry the original.

## Status

Wired up. Both attachment fields are live on `Proposals and Tenders` and their field IDs
match `tools/bid-intake-desk/index.src.html`'s `AIRTABLE.field` config exactly — confirmed
against the table schema, not assumed. What that unblocks and what it doesn't is below.

---

## The two tables, as built

`CM Knowledge Bank` now holds both halves, and the split is what makes the generator work.

| Store | Where | One record is | Who maintains it |
|---|---|---|---|
| Proposals and Tenders | Airtable `tblxQyGlAV81vz3ES` | A past bid: tender, deck, outcome, price | Anyone — drop a file in |
| Knowledge bank | `proposal-assets/knowledge-bank/` | One reusable idea, in prose | Extracted from those bids, then reviewed |

**Content Library has been removed.** Asking colleagues to type prose into a spreadsheet is
the effort this pipeline exists to avoid; contributing a past bid should be dropping a file
into a record and nothing more. The prose now lives in the repo as Markdown, extracted from
those documents rather than retyped, version-controlled and reviewable.

### Pulling a document out of an attachment

`RFP Document` and `Proposal (pptx) Deck` are both attachments, but only one of them is
ours to mine. The **deck** is our own past response — extractable, reviewable, eventually
retrievable. The **RFP** is the client's own tender: useful for judging how closely that
past bid resembles the current one, but never a source to draft an entry from. Running
it through `ingest_source.py` would file a client's confidential requirements into the
bank mislabeled as our own methodology — a mistake worth naming plainly rather than
leaving to be discovered.

A project row points at a file, not the file's content, and `ingest_source.py` only
reads a local path. The intake page bridges the two for the deck: Stage 03's
`selection.json` lists each attachment as `{name, url}` under `proposal_deck` (and,
separately, `rfp_document` for context), where `url` is Airtable's own attachment link.
That link is only valid for a couple of hours from when the page read the record —
download promptly, and if it has gone stale, reopen the page (or re-list the table
through the connector) for a fresh one.

```bash
curl -sSL -o retail-2025-response.pptx "<the url from selection.json's proposal_deck>"
python skills/cm-proposal-generator/scripts/ingest_source.py retail-2025-response.pptx \
    -o proposal-assets/knowledge-bank/methodology/retail-phasing.md --outcome won
```

From there it's the same draft-then-review path as any other ingest: split into
single-idea entries, verify the numbers, set clearance, then `index_kb.py`. An attachment
is never a `source` in a `proposal_plan.json` — only the entry id that comes out the other
end of this is.

