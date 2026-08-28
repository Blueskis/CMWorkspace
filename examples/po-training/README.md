# Worked Example — Purchase Order module training

A complete `training-material-generator` run, end to end: two invented source documents in,
a 17-slide draft training deck out, with a QA report that passes on mechanics and still
reports one open `[GAP]`.

Everything here is **invented**. There is no real system, no real client, and the two
"screenshots" are generated rectangles. The point is to exercise the pipeline — especially
Stage 1, which is the part most likely to break on a document nobody designed for it —
without shipping anyone's specification.

The Purchase Order theme is deliberate: PO Creator and PO Approver are the audience split
that v0.2's audience curation will need, and the plan already records `audiences` on every
module so that change is a renderer flag rather than a re-run.

## Files

| File | What it is |
|---|---|
| `inputs/PO-FSD.docx` | The invented FSD — headings, numbered clauses, field-rule tables, two captioned screenshots, and a logo repeated in four section headers |
| `inputs/PO-Status-Matrix.xlsx` | A supporting status matrix, as a spreadsheet |
| `source_index.json` | Stage 1 output — 15 chunks, 5 tables, 4 images, 12 in-scope topics |
| `assets/` | The images, extracted byte-identical from the .docx |
| `training_plan.json` | Stages 2–3 — 7 modules, 17 slides, 5 objectives, 2 knowledge checks |

## Reproduce it

```bash
# Stage 0 — rebuild the source documents (they are committed, so this is optional)
python skills/training-material-generator/scripts/make_sample_fsd.py -o examples/po-training/inputs/

# Stage 1 — ingest
python skills/training-material-generator/scripts/ingest_docs.py examples/po-training/inputs \
    -o examples/po-training/source_index.json --assets examples/po-training/assets \
    --run-id po-module-20260828

# Stage 4 — render (Stages 2–3 are the model's work; their output is committed here)
python skills/training-material-generator/scripts/render_html.py \
    examples/po-training/training_plan.json training-assets/templates/html-training \
    -o /tmp/po/training.html

# Stage 5 — QA
python skills/training-material-generator/scripts/qa_training.py \
    examples/po-training/source_index.json examples/po-training/training_plan.json \
    -o /tmp/po/qa_report.md
```

A participant copy comes off the same plan:

```bash
python skills/training-material-generator/scripts/render_html.py \
    examples/po-training/training_plan.json training-assets/templates/html-training \
    -o /tmp/po/participant.html --answers hidden --sources hidden
```

## What each part demonstrates

**Ingest recovers context, not just content.** The two screenshots come out with their
figure captions, the heading they sat under, and their position in the document — which is
what lets Stage 3 put the Create PO capture on the Create PO slide rather than guessing.
The logo that repeats in four section headers collapses to one asset with
`occurrences: 4` and classifies as `logo`, so it is neither placed on a slide nor reported
as a dropped screenshot.

**Tables survive as tables.** `POFSD#4.2` is the header field-rules table. Flattened to
prose, the Mandatory column is the first thing lost — and mandatory-versus-optional is
precisely what a learner needs. It reaches the deck as a table with that column intact.

**A diagram is drawn from text, and cites it.** The `stateDiagram-v2` on slide 4 was
written from the prose of `POFSD#2` plus the status matrix, and carries both anchors. The
FSD's own process-flow picture is in `excluded_assets` with the reason — redrawn so it stays
legible at slide size — rather than being silently ignored.

**Knowledge checks are 5 questions, mixed.** Two checks, each 3 multiple-choice and
2 True/False, every answer with a rationale and a source anchor, all of it in the speaker
notes. Render with `--answers hidden` and the participant copy carries the questions and no
key.

**The `[GAP]` is the interesting slide.** "Where to get help" is empty because the
specification never names a support route — and two exception paths in the deck end with
"contact a Procurement Admin" who is never identified. That is a real hole in the source
document, and the deck reports it as an action rather than inventing a plausible service
desk address. This is the behaviour to keep: a `[GAP]` on a business rule means the spec
does not say, which is a question for the process owner.

## Expected result

```
17 slides · 2 screenshots inlined · 1 diagram · 2 knowledge checks · 1 [GAP]
Objectives: 5/5 covered, 5/5 tested
Topics: 12/12 in-scope taught or deferred
Images: 3 placement-class, 3 placed or excluded with a reason
Checks: 2 (10 questions), 0 faults
QA status: PASS (mechanical checks)
```

QA passing does **not** mean the deck is ready. It means nothing is unattributed, nothing
was dropped without a decision, and no check is malformed. The two things it cannot do are
in every report's handover note: check every business rule against the specification, and
check every screenshot against the build learners will actually see.
