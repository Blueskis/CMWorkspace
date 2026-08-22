---
name: readiness-insights-agent-v0.1
description: Compiles multiple streams of change-management feedback — training evaluation scores and free-text comments, comms channel feedback forms, change readiness assessments, pulse surveys — into one evidence-traced readiness brief, read against the programme's timeline and upcoming deliverables so each finding carries a "by when" rather than just a score. Runs a six-stage pipeline — ingest each source into a common signal set, capture the programme timeline, roll the numbers into a segment-by-dimension matrix and lay the verbatims out for coding, write insights anchored to milestones, audit evidence and coverage, then render the brief. Use whenever a practitioner wants to make sense of change feedback — phrases like "what is this training feedback telling us", "are we ready for go-live", "pull the readiness data together", "analyse these survey results", "what are the themes in this feedback", "readiness report for the steerco". Do NOT use for designing a survey, for QA of training content (use training-qa-agent), or for writing a bid (use cm-proposal-generator).
---

# Readiness Insights Agent

Takes the feedback a change programme is already drowning in — training evaluations,
comms feedback forms, readiness assessments, pulse surveys, workshop notes — and turns it
into a readiness brief that a sponsor can act on: what the data says, for which group,
how confident we are, and what has to happen before which date.

**The point of this skill is evidence and timing, not summarisation.** Anyone can
summarise a survey. What makes this useful is that (a) every insight traces to specific
response IDs, and (b) every insight is read against the programme calendar, so a finding
either has an action window or is declared past it. Both are checked mechanically in
Stage 5.

## MVP scope (read this before promising anything)

This is v0.1. What it does and does not do:

| In scope | Out of scope (v0.1) |
|---|---|
| CSV-shaped feedback exports, one adapter per source | Live survey-platform APIs, PDF report scraping |
| Likert/numeric items and free-text comments | Ratings buried in prose, audio, video |
| Segment × readiness-dimension rollups, wave-on-wave deltas | Significance testing, regression, driver analysis |
| Model-written themes over listed verbatims | Automatic topic modelling or sentiment scoring |
| Insights anchored to milestones with a lead-time verdict | Rescheduling the plan, or resourcing the actions |
| Evidence, coverage, anchoring and confidence audits | Judging whether a reading is *right* |
| A self-contained HTML brief | PowerPoint output (pipe the insights into `pptx`) |

Hand the output over as **a draft read for the practitioner to challenge**, never as a
finished assessment. Say so explicitly when you deliver it.

## Pipeline

```
  Stage 1  INGEST     feedback files + adapters ──▶ signals.json
  Stage 2  CONTEXT    plan, milestones, segments ──▶ programme.json
  Stage 3  ANALYSE    signals ──▶ analysis.json + verbatims.md
  Stage 4  INTERPRET  analysis + worksheet + programme ──▶ insights.json
  Stage 5  AUDIT      evidence, coverage, anchoring, confidence ──▶ qa_report.md
  Stage 6  RENDER     insights + analysis + programme ──▶ brief.html
```

Each stage writes a file, so a run can be resumed, inspected, or re-run from any stage.
Never jump from a pile of CSVs to a set of conclusions — the intermediate artifacts are
what make a conclusion checkable, and Stage 5 has nothing to check without them.

### Run workspace

Create `readiness/<programme-slug>-<YYYYMMDD>/` in the user's working directory:

```
readiness/northwind-20260814/
├── inputs/           # copies of the raw exports
├── adapters/         # one JSON per source, see Stage 1
├── signals.json      # Stage 1
├── programme.json    # Stage 2
├── analysis.json     # Stage 3
├── verbatims.md      # Stage 3
├── insights.json     # Stage 4
├── qa_report.md      # Stage 5
└── brief.html        # Stage 6
```

## Stage 1 — Ingest

Find out what feedback actually exists. Ask for it by instrument, not in the abstract:
training evaluations (which waves?), comms or channel feedback forms, change readiness
assessments, pulse surveys, workshop and floorwalking notes, support-ticket themes from
any earlier release.

For each source, write an adapter — a small JSON file naming the columns and mapping each
item to a readiness dimension. Format and worked examples:
`reference/source-adapters.md`. Dimensions: `reference/readiness-dimensions.md`.

```bash
python scripts/ingest_feedback.py --map adapters/training_w2.json \
                                  --map adapters/comms_july.json -o signals.json
```

Three rules that decide whether the rest of the run means anything:

1. **Map items to dimensions once, in the adapter — never per row.** "I know where to get
   help" is an awareness item every time it appears, or the segment comparison is
   comparing different questions.
2. **Record the population, not just the responses.** A 16% response rate is a finding in
   itself, and Stage 5 uses it to force honest confidence ratings. If nobody knows the
   population, say so rather than guessing one.
3. **Never impute.** The script drops blanks and counts them. Do not fill them, and do not
   let a low-n cell borrow strength from a neighbouring one.

Report back: sources ingested, response rates, signal counts, any warnings. Then continue.

## Stage 2 — Programme context

**This is the stage that separates an insight from an observation, and the one people
skip.** A confidence score of 58 is a talking point eleven weeks out and an escalation
nine days out. Without the calendar the agent can only describe.

Write `programme.json` against `schemas/programme.schema.json`: the as-of date, the
methodology, every dated milestone the feedback could change the plan for (training waves,
comms drops, decision gates, cutover, deliverable due dates, hypercare exit), and the full
list of impacted segments **including groups nobody surveyed**.

Ask for the plan if you have not been given one. Ask specifically for:

- What is the next irreversible date, and what has to be true before it?
- What deliverables are due between now and then, and who owns them?
- Who is in scope that these instruments do not reach — contractors, shift workers,
  franchisees, offshore teams, anyone without a corporate email?

That last question is the one that produces the most valuable finding in most runs. A
segment listed here with no data becomes a declared blind spot in the brief; a segment
never listed simply disappears, and the brief silently reports readiness for the people
who were easy to reach as if it were readiness for everyone.

## Stage 3 — Analyse

Numbers and text, separately, before interpreting either.

```bash
python scripts/analyze_quant.py signals.json --programme programme.json -o analysis.json
python scripts/prepare_verbatims.py signals.json -o verbatims.md
```

`analyze_quant.py` builds the segment × dimension matrix: n, mean on a 0-100 normalised
scale, detractor share, RAG band, and wave-on-wave delta where sources carry wave labels.
Cell IDs (`A:capacity:Field Ops`) are what insights cite. A base under `--min-n` is banded
*thin* and never green; segments with nothing at all are banded *no data* and listed as
blind spots.

`prepare_verbatims.py` lists every comment under its dimension and segment with its signal
ID, plus term frequencies. **Read the worksheet.** Do not theme from the term-frequency
table — it tells you which words recur, which is not what people meant. "Training"
appearing 40 times is not a theme; "the exercises used demo data that looks nothing like a
real job sheet" repeated eleven times is.

Look for the three things the numbers hide: a score that is flat because two segments moved
in opposite directions, a dimension that improved while the thing it exists to predict did
not, and a segment whose verbatims contradict its scores.

## Stage 4 — Interpret

Write `insights.json` against `schemas/insights.schema.json`. This is the stage the model
does, and `reference/insight-writing.md` is the standard to write to — read it before
starting. In outline:

- **Themes** code the verbatims. Two quotes minimum, prevalence counted not estimated, and
  a counter-signal recorded for each — what in the data cuts against it, or "none found".
- **Insights** state a finding with its number in it, then the *so what* for the programme,
  then an action someone could start on Monday, with an owner.
- **Every insight is anchored** to a milestone with an honest `remediation_lead_time_days`,
  or explicitly `not_time_bound`. Anchor to the milestone the finding actually bears on,
  not always to go-live.
- **Confidence is rated honestly.** A thin base or a single low-response-rate source means
  `low`, and Stage 5 enforces it. Low confidence is not a reason to drop a finding — it is
  a reason to state it as a question and say what would answer it.
- **Blind spots are carried forward** from the analysis coverage, each with why it matters
  and how to close it.
- **Gaps** — something the programme needs to know that this feedback cannot answer — are
  `gap: true` with a note, never a plausible-sounding paragraph.

Then join to the calendar:

```bash
python scripts/timeline_join.py insights.json programme.json -o action_windows.md
```

Verdicts are `in_window`, `act_now`, and `too_late`. **`too_late` is the most valuable
output of the run and must survive into the brief.** When remediation needs longer than
remains, the honest message is that the decision has changed shape — descope, delay, or
accept the risk — and saying it four weeks early is the whole reason the practitioner
compiled the feedback. Do not quietly shorten a lead-time estimate to make a verdict look
better.

Two more things to write, not compute:

- **Say what is working.** A brief that is only red is one nobody acts on, and the thing
  that improved usually tells you what to protect under time pressure.
- **Rank by consequence, not by score.** The worst score is not automatically the most
  urgent finding; the one closest to an irreversible date usually is.

## Stage 5 — Audit

```bash
python scripts/qa_insights.py signals.json analysis.json insights.json \
    --programme programme.json -o qa_report.md
```

Hard failures, all of them non-negotiable: evidence that does not resolve, a blind spot in
the analysis that the brief never declares, an insight with no milestone and no
`not_time_bound`, a confidence rating the base does not support, a theme on fewer than two
quotes, a gap with no note.

Fix the insights and re-run. Never edit the analysis to make the audit pass, and never
delete a blind spot to clear a failure — that failure is the check doing its job.

## Stage 6 — Render and deliver

```bash
python scripts/render_brief.py insights.json analysis.json programme.json -o brief.html
```

One self-contained HTML file: headline, heatmap, insights ordered by how little time is
left, themes with quotes, blind spots, milestone strip. Every card carries its evidence
IDs — the brief and its audit trail are the same document.

When you hand it over, say in the chat: the headline, the count of `too_late` findings,
the blind spots, and the response rates the whole thing rests on. Then say plainly that it
is a draft read to be challenged, and that Stage 5 checked the sourcing, not the judgement.

## Where this fits with the other skills

- **Diagnostic frameworks** (`kotter-8-step`, `dice-framework`, `critical-few-behaviours`
  and the rest) ask what the practitioner believes. This skill asks what the data says.
  Running this first gives those frameworks evidence to work from.
- **`training-qa-agent`** reviews the materials; this reviews what happened when people
  sat through them. A Stage 4 theme about content quality is a good reason to send the
  module through that skill.
- **`pptx`** turns `insights.json` into a steerco deck when HTML is not the deliverable.
