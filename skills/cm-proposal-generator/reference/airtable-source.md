# Airtable as the source for past RFPs and past proposals

Past tenders and past proposal decks live in Airtable rather than in Markdown
files: **CM Knowledge Bank → Proposals and Tender**. The other six sections
(`methodology`, `case-studies`, `credentials`, `team`, `commercials`, `boilerplate`) stay
as Markdown in this folder.

Whichever store an entry comes from, it has to arrive at retrieval as the same record —
`kb_index.json` stays the one interchange format, and `retrieve.py` never learns where an
entry came from. Anything else and the pipeline and the intake page rank different banks.
`sync_airtable.py` is what keeps that true; see
[Syncing Content Library into the pipeline](#syncing-content-library-into-the-pipeline).

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

One question, which Content Library structurally cannot answer: **have we bid something
like this before, and how did it go?** An entry is an idea; only the register knows about
bids. Stage 02 ranks past projects against the tender and orders them most-similar-first,
so the answer points at a specific deck worth mining.

Everything after that is manual by necessity: the page cannot read an attachment out of
Airtable — the files live on a host the artifact's CSP blocks — so the deck is downloaded
from the record and dropped into *Draft entries from a past deck*, which does read it.

Three columns carry the ranking:

| Field | Type | What it does |
|---|---|---|
| Tags | Multiple select | +3 per tag shared with the tender. The only thing matched on; without it rows can only be ordered by name. Use the same vocabulary as Content Library — matching is literal. |
| Outcome | Single select — `won`, `lost`, `no-bid`, `withdrawn`, `pending`, `unknown` | ±2. A won bid is worth mining ahead of a lost one, but only just: a lost bid on the same subject still outranks a won one on a different subject. |
| Submitted | Date | −2 beyond 24 months, so an old bid is surfaced as old rather than quietly reused. |

**These three are matched by value shape, not field id.** The other five columns are read
by id, so a rename cannot empty them; these were added after their ids were last observed
here, and guessing an id would be worse than not reading the column. So Tags is recognised
as the multiple-select, Outcome as the single choice whose name is one of the six, and
Submitted as the only ISO date — looking only at columns no known id has claimed. Rename
them freely; retype them and the page stops seeing them.

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

### Syncing Content Library into the pipeline

`sync_airtable.py` is the fetcher `index_kb.py --merge` was written for. Without it the
pipeline reads only Markdown, so `retrieve.py` cannot see a single Content Library row and
Stage 4 ranks a different bank from the one the intake page shows.

```bash
export AIRTABLE_TOKEN=pat...
python skills/cm-proposal-generator/scripts/sync_airtable.py -o airtable_entries.json
python skills/cm-proposal-generator/scripts/index_kb.py proposal-assets/knowledge-bank \
    --merge airtable_entries.json -o proposals/<run>/kb_index.json
```

The token is a read-only [personal access token](https://airtable.com/create/tokens) with
`data.records:read` and `schema.bases:read`, granted to this base. It is read from the
environment and never accepted as a flag, so it stays out of shell history.

Both stores land in `kb_index.json` as the same kind of record — retrieval cannot tell
them apart, which is the point. An Airtable-sourced entry shows its `record_url` where a
Markdown one shows its path, so a shortlisted entry is one click from the row it came from.

Three behaviours worth knowing:

- **A blank Clearance is sent as `internal-only`, explicitly.** `build_record()` defaults an
  *absent* clearance to `anonymised`; leaving the field off would make the pipeline quietly
  more permissive than the page for exactly the rows nobody finished. The fetcher never
  relies on that default.
- **Rows are sent even when unusable.** A row with no Section is written to the merge file
  and rejected by `index_kb.py`, which names it on stderr. The fetcher prints a count as a
  courtesy but does not filter: two validators drift, so there is one.
- **Field ids, not field names.** Renaming a column in the Airtable UI keeps its id, so the
  bank survives a rename rather than silently emptying.

`--fetch-attachments DIR` additionally downloads past-bid **decks** from Proposals and
Tenders into `DIR`, ready for `ingest_source.py`. Tenders are skipped unless `--include-rfp`
is passed, for the reason above: an RFP is the client's document, not ours to mine.

`--from-file FILE` reads a saved API response instead of calling Airtable — for working
offline, or checking a mapping without spending calls.

### When the script cannot reach Airtable

`api.airtable.com` is not reachable from every environment — a sandbox may deny the host
outright, and a session without a token cannot authenticate anyway. The intake page is the
fallback, because it reads the table through the *reader's own* connector rather than over
the network: open it, let Content Library load, and press **Export for the pipeline** in
Stage 02. That writes `airtable_entries.json` — the same file `sync_airtable.py` produces,
from the same rows — and `index_kb.py --merge` takes it unchanged.

The two implementations are held together the way the renderer is: run the same records
through both and the entries must match field for field. `sync_airtable.py` is the
reference if they ever disagree.
