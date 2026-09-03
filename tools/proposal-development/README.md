# Proposal Development Tool

Section 03 of the proposal workflow: after a tender is read (section 01) and past
proposals are shortlisted against it (section 02), this drafts a first-version deck built
on the firm's own PowerPoint template, then exports it.

Published as a claude.ai Artifact — the page itself lives in `artifact/`, assembled from
the tested modules in `src/` by `build.py`. It is a sibling to the **Proposal Reference
Tool** artifact (sections 01–02), not a replacement: this build carries sections 01–02
forward unchanged and adds section 03.

## Layout

```
src/            tested JS modules — OOXML read/write, outline, retrieval, drafting, export
artifact/       the page template (proposal-development-tool.html.tmpl) with a {{MODULES}}
                marker where build.py inlines src/*.js
build.py        assembles artifact/*.tmpl + src/*.js -> a single-file HTML artifact
test/           node:test suite (28 cases) plus fixtures and a python-pptx validator
```

## How section 03 works

1. **Template** — upload the firm's `.potx`/`.pptx`. Read-only: layouts, placeholders,
   theme colours, fonts, and slide size are profiled in the browser (`src/ooxml-read.js`,
   a port of `skills/cm-proposal-generator/scripts/profile_template.py`). Nothing is
   uploaded anywhere.
2. **Past proposals** — drop in the decks worth reusing from section 02's shortlist
   (Airtable attachments can't be fetched directly from a published artifact, so this is a
   manual step). Split into per-slide text for retrieval.
3. **Outline** — built from the tender's own `cm-core` clauses (the same triage section 01
   already does), named and ordered exactly as the tender itself does
   (`src/outline.js`, a port of `reference/section-library.md`'s three rules).
4. **Draft** — one `sample()` call per section, grounded in the retrieved past-deck
   excerpts (`src/retrieve.js`, `src/draft.js`). Every content block carries a `sources[]`
   citation or an explicit `gap: true` + `gap_note` — no third state. A block that arrives
   any other way (no source, or a source ID never offered to it) is rewritten into a
   `[GAP]` block naming what's missing. This is the `proposal_plan.schema.json` provenance
   invariant, enforced client-side.
5. **Export** — builds a real `.pptx` on the uploaded template (`src/ooxml-write.js`):
   placeholder-only shapes with no explicit geometry, font, or colour, so everything
   inherits from the template's own layout and theme. `.pptx` sits in the platform's
   *extended* download-extension set, which may not be enabled for a given viewer — if the
   save is refused, the tool falls back to a `.json` (the plan, buildable through the
   `pptx` skill's template workflow) plus a readable `.md` outline.

## Building

```bash
python3 build.py -o out/proposal-development-tool.html
```

Stdlib only — no npm dependencies, matching `skills/cm-proposal-generator/scripts/`.

## Testing

```bash
python3 test/fixtures/make_template.py   # generates fixtures/*.potx, gitignored
node --test test/                        # 28 cases: zip, template profiling, the OOXML
                                          # writer, outline, retrieval, drafting/provenance,
                                          # export/download fallback
pip install python-pptx                  # independent validator for generated .pptx files
python3 test/validate_pptx.py out/some.pptx
```

`node --test` exercises the modules directly; `build.py`'s output additionally gets an
integration smoke test (not part of the 28 cases) that runs the actual inlined bundle in a
`vm` context with a minimal fake DOM, driving a full tender → template → deck → draft →
export flow through the real page functions and validating the resulting `.pptx` with
`python-pptx`.

LibreOffice (`soffice --headless --convert-to pdf`) could not be exercised in the
container this tool was built in — it failed to launch even against a trivial `.txt` file,
independent of anything this tool produces. `python-pptx` is the validator actually used;
whoever runs this next should confirm a real `.pptx` opens in PowerPoint or LibreOffice on
a normal machine before relying on it.

## What v0.1 does not do

Pricing, multi-lot bids, embedded images or charts in generated slides, semantic/embedding
retrieval, writing back to Airtable, or any claim that the output is submission-ready.
Output is always a first draft for practitioner review — the `[GAP]` markers are the
point, not a defect.
