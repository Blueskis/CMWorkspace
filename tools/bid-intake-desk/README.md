# Bid Intake Desk

A browser front end for the whole pipeline except the one step that needs judgement.

```
01 Read the tender        triage — which clauses are CM's to answer
02 Choose the evidence    both Airtable tables, ranked against the tender
03 Hand off for the plan  selection.json → Claude writes proposal_plan.json
04 Build the deck         .pptx + QA, in the browser, downloadable
```

Only step 03 leaves the page. Writing the plan means extracting requirements verbatim,
naming sections the client's way, and adapting bank prose to this client — judgement, not
computation. Everything either side of it is mechanical and runs here.

The handoff is two files, and confusing them is the easiest mistake the page can invite.
`selection.json` records *which* evidence to draw on; `proposal_plan.json` says what each
slide actually contains. Stage 03 emits a single prompt block with the selection already
inside it — paste that whole block into Claude, and what comes back is the file Stage 04
wants. Stage 04 recognises a `selection.json` pasted into it by name and says so rather
than reporting a missing key.

Stage 04 also has **Load the worked example**, which runs `examples/acme-erp` through the
renderer and the QA checks with no plan of your own. It is the fastest way to see what the
second half does, and the fastest way to tell a broken plan from a broken page.

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

**Saving may be refused.** `.pptx` is in the artifact runtime's extended download set. If
extended types are not enabled for a viewer, `downloads.save` rejects with
`extension_not_enabled` and the page says so plainly — the deck built correctly, it just
cannot be handed over there.

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
