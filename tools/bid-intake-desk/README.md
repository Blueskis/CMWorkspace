# Bid Intake Desk

A browser front end for the whole pipeline except the one step that needs judgement.

```
01 Read the tender        triage — which clauses are CM's to answer
02 Check what got picked  the baked-in bank, plus past bids ranked from Airtable
03 Review the plan        rfp_brief + proposal_plan, built in the page
04 Download your deck     .pptx + QA, in the browser, downloadable
```

These are the page's own headings. This doc otherwise calls the four stages by number —
Stage 01 through Stage 04 — since the on-page wording is deliberately plainer than what's
useful in a technical doc.

**Nothing leaves the page, and nothing needs clicking.** Upload a tender and the deck
builds itself: triage sets the retrieval tags, everything sharing a tag is selected, the
plan is assembled and the deck rendered. Stage 02's panel is there to correct that, not to
perform it — a curated bank holds far more than any one tender needs, so the narrowing
still has to happen; it just happens by default. The moment anyone ticks a box by hand,
their choice stands and no later re-rank overwrites it.

The reusable content itself comes from one curated deck of good slides, tagged in speaker
notes and converted by `ingest_source.py --golden-deck` — see
`reference/golden-deck.md`. That conversion happens in the repo, not here, so entries
reach the page on a rebuild.

### Where the two halves of Stage 02 come from

The page itself calls this the **slide library** — plainer wording for a non-technical
user than "knowledge bank." Same thing; this doc uses the latter since it's the actual
folder and schema name.

The **reusable content** is `proposal-assets/knowledge-bank/`, compiled into the page by
`build.py` with `index_kb.py --with-body` — an excerpt ranks an entry, but putting its
prose on a slide needs the whole body. A browser cannot read a git repository and the CSP
blocks every host that might serve one, so entries are fixed until the next publish.
Adding one means editing Markdown, rebuilding and republishing.

The upside is that Stage 02 has content with **no connector at all**: the bank, the
ranking, plan assembly and the build all work with `window.claude` entirely absent.

The **past bids** are still read live from Airtable, because that is where colleagues
contribute — a bid is added and its deck attached, and nothing more is asked of them.
Turning those decks into entries is a separate, reviewed step: see
`reference/airtable-source.md`.

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
prose actually adapted to the client, Stage 03 provides two optional workflows:

1. **Ask Claude for a written plan** — the original workflow, for full model-driven adaptation.
2. **Strengthen with slide-building skills** — an optional multi-step enhancement:
   - `/presentation-outline-builder` constructs narrative flow across sections
   - `/hook-maker` opens each major section with client-facing stakes and relevance
   - `/visual-simplifier` cuts ruthlessly: one idea per slide, short bullets, specifics over prose
   - `/slide-writer` disciplines the wording: bullet constraints, unit clarity, source citations
   
   Paste the prompt, run the skills in sequence, and drop the enhanced plan back into Stage 04
   to override the assembled version. The plan's sources array is preserved throughout.

Content taken from the tender rather than the bank — cover text, the clause list — is
attributed `tender:<filename>` rather than borrowing an unrelated entry id. It keeps the
invariant that no block is unattributed while staying honest about where the words are from.

Stage 04 also has **See how this works** (formerly "Load the worked example"), which runs
`examples/acme-erp` through the renderer and the QA checks with no tender at all — the
fastest way to tell a broken plan from a broken page.

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
generic template as base64, that template's profile, and the knowledge bank itself — a
strict CSP blocks every external host, so anything the page needs has to be in the page.
A bank entry that fails to index fails the build rather than shipping. Only the register
of past bids is read live.

`index.src.html` is the source; `index.html` is the built artifact. Never edit
`index.html` — the next build overwrites it.
