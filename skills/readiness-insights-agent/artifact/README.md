# Snapshot triage page

A self-contained HTML page for the people who *hold* the feedback rather than the people
who analyse it. A workstream lead drops an .xlsx or .csv export into it and gets an
immediate read: a segment × dimension heatmap, how the answers split, computed
observations, and the comments laid out for coding.

Published as an Artifact. The source lives here so it is versioned with the skill; edit
this file and republish to the same URL.

## What it is, and what it is not

It is a **quick look, standalone** — deliberately not the six-stage pipeline. There is no
programme timeline in it, so no insight carries a "by when"; there is no audit stage, so
nothing forces a blind spot to be declared. It computes what the responses say and stops
there.

The bridge back to the pipeline is the export: **Download summary (.csv)** gives the
matrix, **Download full read (.json)** gives the matrix, blind spots, observations and
every comment with its group and dimension. Hand either to the practitioner running
`readiness-insights-agent` and Stage 2 onwards proceeds normally.

## Design decisions worth keeping

- **The file never leaves the browser.** Parsing is local — a zip reader over the .xlsx
  plus `DecompressionStream('deflate-raw')`, no upload, no storage, no network. This is
  what makes it safe to hand to a client-side lead with raw staff feedback in the sheet.
- **The mapping step is visible and editable.** Column roles and readiness dimensions are
  guessed from header wording and shown for correction before anything is computed. A
  dimension guessed with no keyword match says so.
- **A thin base is never green.** Under five responses a cell is banded *thin* and held
  out of the RAG read; empty cells read "no data", never as a pass.
- **Findings are arithmetic, not judgement**, and labelled as such: lowest cell, spreads
  over 20 points, skills-above-confidence, awareness-above-understanding, divided rooms,
  thin and empty cells, and the strongest reading.

## Working on it

Test headlessly rather than by eye alone — the parser is the part that breaks:

```bash
# build a realistic .xlsx (needs openpyxl), then drive the page in headless chromium
python3 - <<'PY'
import csv, openpyxl
wb = openpyxl.Workbook(); ws = wb.active
for r in csv.reader(open('../../../examples/northwind-readiness/inputs/training_eval_wave2.csv')):
    ws.append([int(c) if c.isdigit() else c for c in r])
wb.save('/tmp/test_eval.xlsx')
PY
```

Then append a test block to a copy of the page that base64-inlines that file, calls
`handleFile()`, clicks `#run`, and prints `TABLE`, `MAP` and `ANALYSIS` into a `<div>` —
`headless_shell --dump-dom` reads the result back. Both themes are worth a screenshot:
the palette is token-driven with `prefers-color-scheme` and `data-theme` covered.
