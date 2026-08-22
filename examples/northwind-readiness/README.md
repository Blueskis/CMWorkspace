# Worked Example — Northwind Logistics (fictional)

A complete run of the readiness pipeline, used to demonstrate and regression-test it.
**The client, the programme, and every response in `inputs/` are invented** — the CSVs
were generated with a seeded script, with realistic segment profiles and verbatims written
to be typical rather than convenient.

Four sources, 915 signals, 5 segments, 6 milestones, an as-of date of 2026-08-14 and a
go-live on 2026-10-05.

## Reproduce it

```bash
# Stage 1 — ingest the four feedback exports
python ../../skills/readiness-insights-agent/scripts/ingest_feedback.py \
    --map adapters/training_eval_wave1.json \
    --map adapters/training_eval_wave2.json \
    --map adapters/comms_feedback_july.json \
    --map adapters/readiness_assessment_aug.json \
    -o /tmp/nw/signals.json

# Stage 3 — matrix and verbatim worksheet
python ../../skills/readiness-insights-agent/scripts/analyze_quant.py \
    /tmp/nw/signals.json --programme programme.json -o /tmp/nw/analysis.json
python ../../skills/readiness-insights-agent/scripts/prepare_verbatims.py \
    /tmp/nw/signals.json -o /tmp/nw/verbatims.md

# Stage 4 — the timeline read (insights.json here is the model-written Stage 4 output)
python ../../skills/readiness-insights-agent/scripts/timeline_join.py \
    insights.json programme.json

# Stage 5 — audit
python ../../skills/readiness-insights-agent/scripts/qa_insights.py \
    signals.json analysis.json insights.json --programme programme.json

# Stage 6 — render
python ../../skills/readiness-insights-agent/scripts/render_brief.py \
    insights.json analysis.json programme.json -o /tmp/nw/brief.html
```

Expected: QA passes, 28/35 matrix cells carry data, 9 declared blind spots, 7 insights,
6 themes, 1 `too_late` verdict, 1 open `[GAP]`.

## What it demonstrates

**Sources disagree, and the disagreement is the finding.** Field Ops skills rose 19.2
points between training waves while their confidence moved 0.3. The training got better;
readiness did not. An average across the two would have shown steady improvement.

**A `too_late` verdict, four weeks early.** `I2` recommends renegotiating rota cover so
Field Ops can attend wave 3. That needs about 30 days and wave 3 is 24 days out, so
`timeline_join.py` bands it `too_late` and the brief presents it as a descope-or-delay
decision for the board rather than an action item for the change lead. This is the output
the whole pipeline exists to produce.

**The blind spot outranks every score in the matrix.** 310 subcontracted engineers run the
same scheduling flow and go live on the same day, and appear in no source at all. They are
listed in `programme.json` as a segment, so all seven of their cells come through as
declared blind spots and `I4` carries them into the brief as a gap. Had they not been
listed in Stage 2, the brief would have reported readiness for the people who were easy to
reach and called it readiness.

**Confidence ratings are forced, not chosen.** `I5` rests only on the July comms form,
which returned 15.6%. Stage 5 fails the run if that insight claims anything above
`low`. Editing `insights.json` and re-running the audit is the quickest way to see each
check fire.

**A thin base is never green.** Depot Admin and Customer Care system-readiness cells have
n=4 each. They are banded thin, excluded from the RAG read, and declared.

**Something is working, and it is said.** `I7` reports the wave 2 redesign as the thing to
protect under time pressure. A brief that is only red is one nobody acts on.

## Note on the numbers

The responses are synthetic, so the *scores* mean nothing outside this example. The
*structure* is what is being demonstrated: which cell a finding cites, whether it clears
the audit, and where it lands against the calendar.
