# Airtable as the source for past RFPs and past proposals

Past tenders and past proposal decks live in Airtable rather than in Markdown
files: **CM Knowledge Bank → Proposals and Tender**. The other six sections
(`methodology`, `case-studies`, `credentials`, `team`, `commercials`, `boilerplate`) stay
as Markdown in this folder.

Whichever store an entry comes from, it has to arrive at retrieval as the same record —
`kb_index.json` stays the one interchange format, and `retrieve.py` never learns where an
entry came from. Anything else and the pipeline and the intake page rank different banks.

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

## Fields worth adding to the register

Three columns would let the intake page rank past projects against a tender instead of
just listing them. Everything else it can already do.

| Add | Type | Why |
|---|---|---|
| Tags | Multiple select | The only thing retrieval matches on. Without it, ranking has nothing to work with but Location. |
| Outcome | Single select — `won`, `lost`, `no-bid`, `withdrawn`, `pending`, `unknown` | Language from a losing bid reads exactly as well as language from a winning one. |
| Submitted | Date | Lets old bids be marked stale rather than quietly reused. |

## Fields for entries extracted from those documents

If extracted entries are kept in Airtable too rather than as Markdown, this is the shape
they need. The first five are required — an entry missing any of them cannot be indexed.

| Airtable field | Type | Maps to | Required |
|---|---|---|---|
| Entry ID | Single line text | `id` | ✓ |
| Title | Single line text | `title` | ✓ |
| Section | Single select — `past-rfps`, `presentations` | `section` | ✓ |
| Content | Long text | the retrievable body | ✓ |
| Tags | Multiple select | `tags` | ✓ |
| Last reviewed | Date | `last_reviewed` | ✓ |
| Clearance | Single select — `internal-only`, `anonymised`, `named` | `clearance` | |
| Metrics verified | Checkbox | `metrics_verified` | |
| Owner | Collaborator or single line text | `owner` | |
| Supersedes | Link to another record (same table) | `supersedes` | |
| Source document | Attachment | `source_document` | |
| Client | Single line text | `bid.client_ref` | |
| Sector | Single line text | `bid.sector` | |
| Submitted | Date | `bid.submitted` | |
| Outcome | Single select — `won`, `lost`, `no-bid`, `withdrawn`, `pending`, `unknown` | `bid.outcome` | |
| Outcome notes | Long text | `bid.outcome_notes` | |
| Sections that scored | Long text | `bid.sections_that_scored` | |

## Three field defaults that carry the safety properties

These are not cosmetic. Each one is a guard that exists because the alternative has a
specific, expensive failure mode.

- **Clearance defaults to `internal-only`.** Retrieval excludes internal-only entries, so
  a record added in a hurry cannot reach a client deck before somebody has checked whether
  the last client agreed to be named. Set the default in Airtable, not by convention.
- **Metrics verified defaults to off.** A number in a past proposal was true of *that*
  engagement on the day it was written. Carrying it into a new bid is a fresh claim, made
  by a person.
- **Outcome defaults to `unknown`, never `won`.** Language from a losing bid reads exactly
  as well as language from a winning one. `unknown` is a usable value; a wrong `won` is
  the reason this column exists.

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

| Table | Id | One row is | Feeds |
|---|---|---|---|
| Proposals and Tenders | `tblxQyGlAV81vz3ES` | A past bid: tender PDF, proposal deck, location, price | Source material to mine |
| Content Library | `tblf1nFLP3p30Fg3S` | One reusable idea, in prose | The slides themselves |

**Content Library fields.** Title (primary), Entry ID, Section, Content, Tags, Clearance,
Last reviewed, Metrics verified, Owner, Source project (linked to Proposals and Tenders),
Bid outcome.

### Two behaviours worth knowing

**A blank Clearance is read as `internal-only`.** Airtable's API cannot set a default on a
single-select, so the intake page treats an empty cell as the most restrictive value
rather than the most permissive. A row somebody started and did not finish is excluded
from retrieval instead of being offered to a client. Set the field default to
`internal-only` in the Airtable UI as well, so the grid shows what the pipeline assumes.

**A row missing Section, Tags or Content is flagged, not dropped.** Retrieval scopes by
section and matches tags literally, so a row without them cannot be found — which looks
exactly like a row that does not exist. The page counts them and labels each one rather
than letting them disappear.

### Pulling a document out of an attachment

`RFP Document` and `Proposal (pptx) Deck` are attachments — a project row points at a
file, it isn't the file's content, and `ingest_source.py` only reads a local path. The
intake page bridges the two: Stage 03's `selection.json` lists each attachment as
`{name, url}`, where `url` is Airtable's own attachment link. That link is only valid for
a couple of hours from when the page read the record — download promptly, and if it has
gone stale, reopen the page (or re-list the table through the connector) for a fresh one.

```bash
curl -sSL -o Transport-Company-RFP.docx "<the url from selection.json>"
python skills/cm-proposal-generator/scripts/ingest_source.py Transport-Company-RFP.docx \
    -o proposal-assets/knowledge-bank/methodology/transport-phasing.md --outcome won
```

From there it's the same draft-then-review path as any other ingest: split into
single-idea entries, verify the numbers, set clearance, then `index_kb.py`. An attachment
is never a `source` in a `proposal_plan.json` — only the entry id that comes out the other
end of this is.

### Still to build

The **pipeline** does not yet read Content Library — `index_kb.py` reads Markdown, and
`index_kb.py --merge` accepts a synced file that nothing currently writes. Until a fetcher
exists, the intake page and Stage 4 see different banks. The merge format is documented
above and the loader is tested; what is missing is the script that calls Airtable and
writes it. This is a separate problem from the attachment flow above — Content Library
holds already-extracted prose, not raw documents.
