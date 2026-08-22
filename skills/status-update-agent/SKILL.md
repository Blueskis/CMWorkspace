---
name: status-update-agent-v0.1
description: Compares this period's version of a recurring programme document against last period's and writes the status update a consultant delivers at the cadence meeting. Handles Word CM plans, Excel training-completion and adoption trackers, and PowerPoint RICEFWA/build status decks — extracting each into a normalised snapshot, diffing them item by item, rating each change for materiality, and writing a spoken update in which every claim cites the change it came from. Use whenever someone wants to know what changed between two versions of a recurring report, or wants a weekly/fortnightly/monthly status update, stand-up update, cadence update, steering summary or progress readout written from documents — phrases like "what changed since last week", "write my weekly status update", "compare this week's tracker to last week's", "prep me for the Thursday cadence", "summarise the movement on the RICEFWA deck". Do NOT use to assess whether a change programme is healthy or well-run — this reports movement between documents, it does not diagnose initiatives.
---

# Status Update Agent

A consultant walks into a weekly cadence meeting holding three documents that also existed
last week: a CM plan, a training tracker, a RICEFWA deck. The meeting doesn't want the
documents. It wants to know what moved, what's wrong, and what the consultant needs a
decision on. This skill does the comparison and drafts that update.

**The point of this skill is that every claim is checkable.** Anyone can summarise a
document. What makes this useful in front of a client is that (a) every statement about
the documents cites a specific change with a specific before and after, (b) anything that
is the consultant's interpretation rather than a change in the documents is visibly marked
as such, and (c) nothing material can be dropped without the omission being recorded.
Stage 5 enforces all three mechanically.

## MVP scope (read this before promising anything)

This is v0.1.

| In scope | Out of scope (v0.1) |
|---|---|
| Two periods of the same document, compared | Trend across many periods, burn-up charts, forecasting |
| `.xlsx` `.xlsm` `.docx` `.pptx` `.csv` | `.pdf`, legacy `.doc`/`.xls`/`.ppt`, Google/Smartsheet/Jira live sources |
| Text, table and cell **values** | Cell colour, charts, images, tracked changes, comments, speaker notes |
| Rule-based materiality with a per-programme override file | Learning which changes this client cares about |
| A markdown update, ready to speak from or paste into a deck | A built .pptx status slide (hand the output to the `pptx` skill) |
| A draft for the consultant to review | Anything sent to a client unread |

A programme that signals RAG by cell fill rather than by a word is a real limitation, not
an edge case. Say so at Stage 1 rather than inferring RAG from the numbers.

## Pipeline

```
  Stage 1  EXTRACT   each document, both periods ──▶ snapshots/*.json
  Stage 2  DIFF      snapshot pair, per document  ──▶ changes/*.json
  Stage 3  MERGE     all changes, one ID space    ──▶ change_brief.json + .md
  Stage 4  WRITE     the brief, read by you       ──▶ status_update.md
  Stage 5  QA        update vs. brief             ──▶ qa_report.md
```

Each stage writes a file, so a run can be resumed, inspected, or re-run from any stage.
Never go straight from two documents to an update — the intermediate artifacts are what
make the output checkable, and Stage 5 has nothing to check against without them.

Stages 1, 2, 3 and 5 are scripts and are deterministic. **Stage 4 is the only stage you
write**, and it is the whole reason a person is in the loop.

### Run workspace

Create `status-updates/<programme-slug>-<period-slug>/` in the user's working directory:

```
status-updates/meridian-wk12/
├── inputs/
│   ├── week-11/          # last period's documents, as received
│   └── week-12/          # this period's
├── snapshots/            # Stage 1, one per document per period
├── changes/              # Stage 2, one per document
├── change_brief.json     # Stage 3
├── change_brief.md       #   the readable version — this is what you write from
├── status_update.md      # Stage 4
└── qa_report.md          # Stage 5
```

## Stage 1 — Extract

Locate both periods' documents and pair them up by what they are, not by filename —
`CM Plan v4.docx` and `CM Plan v5 FINAL.docx` are the same document. Pass a stable
`--name` for each pair so the pairing survives the client's file naming.

```bash
python scripts/extract.py inputs/week-11/cm-plan.docx --period "Week 11" \
    --name cm-plan -o snapshots/cm-plan-11.json
```

Ask for whatever isn't obvious: which documents are in scope this week, what the period is
called in the meeting, and — if a document is new this period — whether there is a prior
version at all. A document with no previous version cannot be diffed; report it as new and
summarise it separately rather than diffing it against nothing.

**Then check the key before trusting anything downstream.** Run Stage 2 and look at the
shape of the result: a large number of additions and removals with few field changes means
the item key is wrong, not that the programme was rewritten. `reference/extraction-guide.md`
has the causes and the fixes. Do not proceed past a bad key — every later stage inherits it.

Report back briefly: which documents, how many items each, anything unsupported (a PDF, a
colour-coded RAG column, a locked file). This is a transparency checkpoint, not a request
for approval — continue into Stage 2 unless the consultant redirects.

## Stage 2 — Diff

One run per document pair:

```bash
python scripts/diff_snapshots.py snapshots/cm-plan-11.json snapshots/cm-plan-12.json \
    -o changes/cm-plan.json
```

Matching is by item key, then by label/text similarity for whatever's left over, so a
renamed activity reads as a rename rather than a deletion plus an addition. Materiality is
assigned by rule — see `reference/materiality-rules.md`.

If the programme's vocabulary differs from the defaults (status names, RAG words,
what counts as a big percentage move), dump the rules with `--print-rules`, edit, and pass
back with `--rules`. Do this once, early, and keep the file in the run folder; changing
thresholds mid-engagement makes weeks incomparable.

## Stage 3 — Merge

```bash
python scripts/write_update.py changes/*.json \
    -o change_brief.json --md change_brief.md
```

Three documents, one meeting, one update. This renumbers every change into a single ID
space (`C1`, `C2`, …), tags each with its source document, and groups them into the running
order of a cadence update. Read `change_brief.md` in full before writing — including the
roll-ups, which are what let you quote a movement instead of listing seven rows.

## Stage 4 — Write

Write `status_update.md` from the brief. `reference/narrative-patterns.md` covers structure,
aggregation and the failure modes; the rules that Stage 5 enforces are:

- **Every claim carries a `[C#]` citation or the `[JUDGEMENT]` marker.** No third state.
  If you can't cite it and it isn't your read, it doesn't go in.
- **Cite only IDs that exist in the brief.** An invented citation is worse than none.
- **Every high-materiality change is mentioned, or waived** with `<!-- omit: C7 reason -->`.
  Waiving is legitimate and normal; silence is not.
- **Aggregate.** Roll-ups and grouped citations, not one bullet per changed cell.
- **Mark interpretation.** The connections between documents are the most valuable part of
  the update and the least checkable. `[JUDGEMENT]` is not a hedge; it's the label that
  lets a client tell your analysis from the tracker's contents.

## Stage 5 — QA

```bash
python scripts/qa_update.py change_brief.json status_update.md -o qa_report.md
```

Fails on an unattributed claim, a citation that resolves to nothing, or an uncovered
high-materiality change. Uncovered medium changes are listed as warnings — read them; the
thing the meeting actually cares about is occasionally in that list.

**Fix and re-run until it passes.** Fix by editing the update, never by loosening the
check: if a claim can't be cited, either find the change that supports it or cut it. A
claim you can't attribute is one you shouldn't make in front of a client.

## Delivering it

Hand over the update **as a draft to review before the meeting**, and say so. Alongside it,
say plainly:

- what was compared, and what period each document represents;
- anything that couldn't be read (a PDF, colour-coded RAG, a locked file);
- anything deliberately omitted and why;
- any medium change left out that the consultant might disagree with.

Then offer the two obvious next steps: the `pptx` skill to put the update on a status slide
on the programme's template, and re-running the same pipeline next week — the run folder,
the rules file and the `--name` values all carry forward, which is most of the setup.

Two honest results this skill will produce and should never dress up:

- **Nothing moved.** Deliver it as a finding, and check whether the documents were actually
  updated — an untouched tracker is itself worth raising.
- **The documents disagree.** The plan says an activity is complete; the tracker says the
  training under it hasn't started. Put the contradiction in the update as an ask. It's
  usually the most useful thing in the room.
