# Reading a rasterised page into a citable note

`ingest_sources.py` flags PDFs and images `read_natively` — deliberately not text-
extracted, because a process diagram or scanned org chart is often the most informative
thing in a document pack, and a text extractor throws all of that away. Left as-is, that
knowledge only ever lives in the conversation: uncitable, and invisible to
`plan_deck.py`'s provenance gate.

`vision_notes.json` (see `lib/schemas/vision_notes.schema.json`) is what turns a page you
looked at into a chunk retrieval can shortlist and a slide can cite, exactly like a text
passage.

## The steps

1. Rasterise: `node lib/deck/cli/rasterise.mjs source.pdf -o intake/vision/pages/`
   (pdf.js-based — no poppler dependency; see that script's own docstring).
2. Read each page image with the Read tool.
3. For each page worth citing, write one entry to `vision_notes.json`:
   - `kind` — `diagram`, `table`, `chart`, `screenshot`, `org-chart`, or `photo`.
   - `transcription` — prose describing what the page actually shows. This is the citable
     claim; never leave it a placeholder.
   - `structured` — optional: rows for a table, `{nodes, edges}` for a diagram/org-chart.
   - `confidence` — `high`/`medium`/`low`. Use `low` for a genuinely unclear scan or an
     ambiguous diagram, not as a hedge on every note.
4. Re-index: `python lib/deck_index.py index source_map.json vision_notes.json -o chunk_index.json`.

## The provenance rule this enables

A slide block can now cite `vision::<note_id>` in its `sources[]` exactly as it cites a
text `chunk_id`. `plan_deck.py`'s provenance check enforces one additional rule beyond the
ordinary "sources or gap" check: a block whose **only** source is a `low`-confidence
vision note is a hard failure. Pair it with a supporting text source, or mark the block
`gap: true` — a shaky read of an unclear diagram cannot be a claim's sole support.
