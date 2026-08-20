# Bid Intake Desk

A browser front end for the whole pipeline except the one step that needs judgement.

```
01 Read the tender        triage — which clauses are CM's to answer
02 Choose the evidence    both Airtable tables, ranked against the tender
03 Assemble the plan      rfp_brief + proposal_plan, built in the page
04 Build the deck         .pptx + QA, in the browser, downloadable
```

**Nothing leaves the page.** The only thing anyone types or uploads is the tender itself;
picking entries in Stage 02 cascades through plan assembly and the build without a file
changing hands.

### What assembling a plan in a page can and cannot do

A model *adapts*: it rewrites bank prose in the client's language, mirrors their section
names, drafts the argument for why this bidder understands this programme. A page has no
way to call one — the artifact runtime grants `artifact`, `downloads`, `mcp` and `self`,
and none of those is a model. So Stage 03 does the part that is mechanical and refuses the
part that isn't:

- **Places** each selected entry's own prose onto slides, sourced to that entry's id.
- **Derives** a requirement per CM-owned tender clause, and maps one to a section only on
  literal tag overlap — the same blunt matching `retrieve.py` uses. A requirement nothing
  matches stays uncovered and Stage 04 reports it, because claiming coverage that cannot
  be shown is the worse failure.
- **Refuses** to write "Our Understanding". That section is emitted as an explicit `[GAP]`,
  since no knowledge-bank entry can know this client's situation.

The result is a sourced first draft with a visible to-do list, not a finished bid. For
prose actually adapted to the client, Stage 03 still keeps the old Claude prompt behind
*The files this run produced* — paste it, and drop what comes back into Stage 04 to
override the assembled plan.

Content taken from the tender rather than the bank — cover text, the clause list — is
attributed `tender:<filename>` rather than borrowing an unrelated entry id. It keeps the
invariant that no block is unattributed while staying honest about where the words are from.

Stage 04 also has **Load the worked example**, which runs `examples/acme-erp` through the
renderer and the QA checks with no tender at all — the fastest way to tell a broken plan
from a broken page.

## Exporting the bank for the pipeline

Stage 02's **Export for the pipeline** writes `airtable_entries.json`, the file
`index_kb.py --merge` reads. It is the same output `sync_airtable.py` produces, built from
the same Content Library rows — the difference is only how Airtable is reached: the script
calls the REST API with a token, the page uses the reader's own connector. That matters
when `api.airtable.com` is blocked by a sandbox's network policy, or when there is no token
to hand.

Same anti-drift rule as the renderer, and the same test: run identical records through
`entryFrom()` + `libraryMergeFile()` and through `sync_airtable.py --from-file`, and every
entry must match field for field. The Python is the reference.

## The renderer is a port, and the Python is the reference

`pptx.js` is a port of `skills/cm-proposal-generator/scripts/render_pptx.py`. Two
implementations of the same thing will drift unless something holds them together, so the
test is byte equality: build the worked example both ways and every part of the package
must match.

```bash
python skills/cm-proposal-generator/scripts/render_pptx.py \
    examples/acme-erp/proposal_plan.json \
    proposal-assets/templates/pptx-generic/pptx-generic.potx -o /tmp/python.pptx
# then build the same plan in the page, download it, and compare:
python3 -c "
import zipfile
a, b = zipfile.ZipFile('/tmp/python.pptx'), zipfile.ZipFile('/tmp/browser.pptx')
assert set(a.namelist()) == set(b.namelist()), 'part names differ'
bad = [n for n in a.namelist() if a.read(n) != b.read(n)]
print('identical' if not bad else f'DIFFER: {bad}')"
```

At the last check: **77 of 77 parts byte-identical.** If they ever diverge, the Python is
right and the port is wrong — it is the one the pipeline runs and the one with the
worked example behind it.

That equality is fragile in one specific way worth knowing: Python's
`html.escape(quote=True)` writes `&#x27;` for an apostrophe where JavaScript would
naturally write `&#39;`. Both are valid XML and mean the same character, but they are
different bytes, so `pptx.js` matches Python's entity set deliberately.

## What the browser build cannot do

**Images.** Embedding a picture needs a media part and a content-type override. A plan
using `kind: "image"` still builds, but those blocks render as a visible marker telling
you to use `render_pptx.py`, which does embed them. Nothing is dropped silently.

**Saving may be refused.** The runtime allows one set of download types always — `gif png
jpg jpeg webp mp4 webm txt json md` — and gates a second behind a per-view setting:
`docx pptx epub csv ttf html svg pdf`. `.pptx` is in that second set, so where extended
types are not enabled for a viewer, `downloads.save` rejects with `extension_not_enabled`.

**The page cannot lift this itself.** `capabilities: {downloads: true}` is the whole
declaration — the contract has no field that requests extended types. The remedy is to
enable extended download types for the view; the deck is already built and still in memory,
so pressing the button again after enabling is enough, with no rebuild.

Every save failure leaves the deck intact. The messages say so and offer a retry rather
than pointing at `render_pptx.py` — a terminal is the thing this tool exists to avoid.

## Build

```bash
python tools/bid-intake-desk/build.py
```

Inlines the two sample tenders, the worked example's plan and brief, `pptx.js`, the
generic template as base64, and that template's profile — a strict CSP blocks every
external host, so anything the page needs has to be in the page. Both Airtable tables are read live, so the knowledge bank is never
frozen into it.

`index.src.html` is the source; `index.html` is the built artifact. Never edit
`index.html` — the next build overwrites it.
