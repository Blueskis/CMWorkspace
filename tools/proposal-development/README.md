# CM Proposal Reference Tool

Three sections in one page: read a tender, correct the automatic read where it's wrong,
shortlist past proposals against it, then draft and export a first-version deck built on
the firm's own PowerPoint template.

Published as a claude.ai Artifact — the page itself lives in `artifact/`, assembled from
the tested modules in `src/` by `build.py`.

## Layout

```
src/            tested JS modules — OOXML read/write, outline, retrieval, triage editing,
                the correction assistant, drafting, export
artifact/       the page template (proposal-development-tool.html.tmpl) with a {{MODULES}}
                marker where build.py inlines src/*.js
build.py        assembles artifact/*.tmpl + src/*.js -> a single-file HTML artifact
test/           node:test suite (53 cases) plus fixtures and a python-pptx validator
```

## How it works

1. **Read the tender** — a keyword classifier (`LEXICON`/`scoreSection`, both in the
   template) triages each clause into `cm-core` (ours to answer), `cm-adjacent`
   (related), or `not-cm`. It is deliberately simple and will miss things.
2. **Correct the read** — every clause carries a verdict control and an editable heading,
   so a miss can be fixed with a click rather than living with it. A **Claude assistant**
   (`src/assistant.js`) answers questions about the read and proposes edits from a plain
   instruction ("anything mentioning the orientation programme is ours") — it never
   applies anything itself; the consultant reviews the proposed batch and clicks Apply or
   Discard. Both paths (manual and assistant) emit the same edit objects
   (`src/triage-edit.js`: `reclassify` / `rename` / `add` / `remove`) and every changed
   clause is visibly badged with what it was before and who changed it.
3. **Shortlist past proposals** — ranks the Airtable register against the tender's own
   vocabulary. Unaffected by triage edits; its ranking comes from the raw tender text.
4. **Draft** — an outline built from the current `cm-core` clauses (`src/outline.js`, a
   port of `reference/section-library.md`'s three rules), then one `sample()` call per
   section grounded in past-deck excerpts you drop in (`src/retrieve.js`, `src/draft.js`).
   Every content block carries a `sources[]` citation or an explicit `gap: true` +
   `gap_note` — no third state. Editing the triage after drafting doesn't discard the
   draft; it's marked stale with a re-draft button, since the outline's clause indexing no
   longer matches.
5. **Export** — builds a real `.pptx` on the uploaded template (`src/ooxml-write.js`):
   placeholder-only shapes with no explicit geometry, font, or colour, so everything
   inherits from the template's own layout and theme. `.pptx` sits in the platform's
   *extended* download-extension set, which may not be enabled for a given viewer — if the
   save is refused, the tool falls back to a `.json` (the plan, buildable through the
   `pptx` skill's template workflow) plus a readable `.md` outline.

## Building

```bash
python3 build.py -o out/cm-proposal-reference-tool.html
```

Stdlib only — no npm dependencies, matching `skills/cm-proposal-generator/scripts/`.

## Testing

```bash
python3 test/fixtures/make_template.py   # generates fixtures/*.potx, gitignored
node --test test/                        # 53 cases: zip, template profiling, the OOXML
                                          # writer, outline, retrieval, triage editing, the
                                          # assistant, drafting/provenance, export fallback
pip install python-pptx                  # independent validator for generated .pptx files
python3 test/validate_pptx.py out/some.pptx
```

`node --test` exercises the modules directly; `build.py`'s output additionally gets an
integration smoke test (gitignored, `tmp/smoke3.mjs`) that runs the actual inlined bundle
in a `vm` context with a minimal fake DOM, driving a full tender → correct-the-read →
template → deck → draft → export flow through the real page functions, including
reclassifying a clause, re-drafting after a stale edit, adding a manual clause, and a full
assistant turn — and validates the resulting `.pptx` with `python-pptx`.

LibreOffice (`soffice --headless --convert-to pdf`) could not be exercised in the
container this tool was built in — it failed to launch even against a trivial `.txt` file,
independent of anything this tool produces. `python-pptx` is the validator actually used;
whoever runs this next should confirm a real `.pptx` opens in PowerPoint or LibreOffice on
a normal machine before relying on it.

## What this tool does not do

Pricing, multi-lot bids, embedded images or charts in generated slides, semantic/embedding
retrieval, writing back to Airtable, persisting triage edits between sessions, or any
claim that the output is submission-ready. Output is always a first draft for practitioner
review — the `[GAP]` markers are the point, not a defect.
