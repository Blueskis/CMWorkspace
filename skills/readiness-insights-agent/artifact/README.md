# Snapshot triage page

A self-contained HTML page for the people who *hold* the feedback rather than the people
who analyse it. A workstream lead drops in one or several .xlsx or .csv exports — a
training evaluation, a comms feedback form, a readiness assessment — and gets an immediate
read across all of them: a segment × dimension heatmap, how the answers split, computed
observations, and the comments laid out for coding.

Published as an Artifact. `snapshot-triage.html` in this folder is the built output and
the file to republish; its React/TypeScript/Tailwind source lives in
`snapshot-triage/` (see that folder's own README for the dev workflow) and is styled to
match the `Change Impact Intake` tool's design system, so the CM Workspace toolset reads
as one family rather than a pile of one-off pages.

## What it is, and what it is not

It is a **quick look, standalone** — deliberately not the six-stage pipeline. There is no
programme timeline in it, so no insight carries a "by when"; there is no audit stage, so
nothing forces a blind spot to be declared. It computes what the responses say and stops
there.

The bridge back to the pipeline is the export: **Download summary (.csv)** gives the
matrix, **Download full read (.json)** gives the matrix, blind spots, observations and
every comment with its group and dimension. Hand either to the practitioner running
`readiness-insights-agent` and Stage 2 onwards proceeds normally.

## Reading several files together

Each file keeps its **own** column mapping — instruments do not share headers, and forcing
one mapping across them is how a comms question ends up scored as a training question.
Sources pool into one matrix, and each cell records which sources fed it.

Two things follow from pooling, and both are in the page:

- **Group names are aligned explicitly.** They are matched literally, so "Field Ops" in one
  export and "Field Operations" in another are two groups — which halves both bases while
  looking like data. Case and punctuation variants merge automatically; a likely match on
  wording is *suggested* with a one-click merge but never applied, because only the person
  holding the data knows whether two similar names are one team. A file with no grouping
  column at all appears as "(all of &lt;source&gt;)" and can be pointed at a real group.
- **Disagreement between sources is a finding.** Where two sources both have a readable
  base on the same group and dimension and their means differ by 15 points or more, the
  page says so rather than quietly averaging them — different questions, a different
  moment, or a different set of people answering are all worth knowing before pooling.

## Design decisions worth keeping

- **The files never leave the browser.** Parsing is local, via SheetJS bundled into the
  page at build time — no upload, no storage, no network calls at runtime. This is what
  makes it safe to hand to a client-side lead with raw staff feedback in the sheet.
- **The mapping step is visible and editable.** Column roles and readiness dimensions are
  guessed from header wording and shown for correction before anything is computed. A
  dimension guessed with no keyword match says so.
- **A thin base is never green.** Under five responses a cell is banded *thin* and held
  out of the RAG read; empty cells read "no data", never as a pass.
- **Findings are arithmetic, not judgement**, and labelled as such: lowest cell, spreads
  over 20 points, skills-above-confidence, awareness-above-understanding, divided rooms,
  thin and empty cells, and the strongest reading.

## Working on it

Edit the source in `snapshot-triage/`, not the built HTML directly:

```bash
cd snapshot-triage
pnpm install
pnpm run build     # -> dist/index.html, single self-contained file
cp dist/index.html ../snapshot-triage.html
```

Test headlessly rather than by eye alone — the parser is the part that breaks. Build a
realistic .xlsx (needs `openpyxl`), then drive the bundle in headless chromium:

```bash
python3 - <<'PY'
import csv, openpyxl
wb = openpyxl.Workbook(); ws = wb.active
for r in csv.reader(open('../../../examples/northwind-readiness/inputs/training_eval_wave2.csv')):
    ws.append([int(c) if c.isdigit() else c for c in r])
wb.save('/tmp/test_eval.xlsx')
PY
```

Append a test `<script>` **after the last `</script>` tag** in the built file (not by
searching for `</body>` — see `snapshot-triage/README.md` for why that lands inside a
SheetJS string literal and corrupts the bundle). Have it wait for `window.load`, build a
`DataTransfer` from base64-embedded test files, dispatch a real `drop` `DragEvent` at
`[class*="border-dashed"]`, and log each step to a visible div; `headless_shell
--dump-dom` reads the result back. Both themes are worth a screenshot: the palette is
token-driven with `prefers-color-scheme` and `data-theme` covered, same as every other
artifact in this workspace.
