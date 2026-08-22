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
| Two documents, compared, each run standing alone | Trend across many periods, burn-up charts, forecasting |
| Documents the consultant uploads or points at | Reading from SharePoint, OneDrive, Google Drive, Jira or any live source |
| `.xlsx` `.xlsm` `.docx` `.pptx` `.csv` | `.pdf`, legacy `.doc`/`.xls`/`.ppt` |
| Text, table and cell **values** | Cell colour, charts, images, tracked changes, comments, speaker notes |
| Rule-based materiality with a per-programme override file | Learning which changes this client cares about |
| A markdown update, ready to speak from or paste into a deck | A built .pptx status slide (hand the output to the `pptx` skill) |
| A draft for the consultant to review | Anything sent to a client unread |

A programme that signals RAG by cell fill rather than by a word is a real limitation, not
an edge case. Say so at Stage 1 rather than inferring RAG from the numbers.

## Pipeline

```
  Stage 1  INTAKE    two uploaded documents      ──▶ snapshots/*.json
  Stage 2  DIFF      snapshot pair, per document ──▶ changes/*.json
  Stage 3  MERGE     all changes, one ID space   ──▶ change_brief.json + .md
  Stage 4  WRITE     the brief, read by you      ──▶ status_update.md
  Stage 5  QA        update vs. brief            ──▶ qa_report.md
```

For the standard two-document case, `compare.py` runs Stages 1–3 in one command. Each
stage still writes its file, so a run can be resumed, inspected, or re-run from any stage.
Never go straight from two documents to an update — the intermediate artifacts are what
make the output checkable, and Stage 5 has nothing to check against without them.

Stages 1, 2, 3 and 5 are scripts and are deterministic. **Stage 4 is the only stage you
write**, and it is the whole reason a person is in the loop.

### Run workspace

Create `status-updates/<programme-slug>-<period-slug>/` in the user's working directory:

```
status-updates/meridian-wk12/
├── inputs/               # the documents as uploaded, both periods
├── snapshots/            # Stage 1, one per document per period
├── changes/              # Stage 2, one per document
├── change_brief.json     # Stage 3
├── change_brief.md       #   the readable version — this is what you write from
├── status_update.md      # Stage 4
└── qa_report.md          # Stage 5
```

Multi-document runs put each period's uploads in `inputs/week-NN/`; a standing weekly rhythm
adds `.snapshot-archive/`. Neither is needed for a two-file comparison.

## Stage 1 — Intake

**Documents come from the consultant, as uploads or local files.** There is no connection
to SharePoint, OneDrive or any live source. That's deliberate rather than missing: it keeps
the skill working across clients whose tenants nobody has admin rights in.

### The default: two files, compared

The normal case is two files and nothing else. Two CM plans this week, two training
trackers next week, two RICEFWA decks the week after — **each run stands alone**. Nothing
carries over between runs, nothing has to have been set up beforehand, and the consultant
never has to remember what was compared last time or which documents a previous session
knew about.

```bash
python scripts/compare.py "CM Plan v4.docx" "CM Plan v5 FINAL.docx" \
    --previous-period "Week 11" --current-period "Week 12" -o run/
```

Previous document first, current second. That runs extract, diff and merge in one go and
writes `run/change_brief.md` — what you write the update from — plus every intermediate
artifact, so the run is still inspectable stage by stage.

Ask only for what you actually need: **which file is the earlier one**, and what the two
periods are called in the meeting. The period labels are cosmetic (they appear in the
brief); getting the order wrong is not, because it inverts every slip into a pull-in.
If it isn't obvious from the filenames which is earlier, ask rather than infer.

The two documents don't have to be the same type or have similar names — if they are two
versions of the same report, pass them and they're compared. `compare.py` warns on a
format mismatch, since a `.docx` against an `.xlsx` is more often two different documents
than two versions of one.

### Optional: several documents, or a weekly rhythm

Only when the consultant asks for it. Neither of these is a prerequisite for the above.

**Several documents in one update.** Put each period's files in a folder; `intake.py` pairs
them by filename with the client's version noise stripped, and reports what paired, what's
new, what's missing and what it skipped:

```bash
python scripts/intake.py \
    --previous inputs/week-11 --previous-period "Week 11" \
    --current  inputs/week-12 --current-period  "Week 12" \
    --snapshots snapshots
```

Then diff each pair and merge them with `write_update.py` (Stages 2–3 below) so three
documents produce one update rather than three.

**A standing weekly rhythm.** Adding `--archive .snapshot-archive` stores each snapshot, so
from the next run onward only the current period's files get uploaded:

```bash
python scripts/intake.py --current inputs/week-13 --current-period "Week 13" \
    --snapshots snapshots --archive .snapshot-archive
```

Offer this only to someone running the same documents week after week, and say what it
costs: the archive holds the documents' extracted content, so it carries the same
confidentiality as the source files and belongs wherever those are allowed to live. A
document in the archive that wasn't uploaded is reported as `MISSING` — **ask for it**,
never report it as unchanged. An absent document and an unchanged one look identical
downstream and mean completely different things.

### Before trusting anything downstream

**Check the key.** Look at the shape of the diff: a large number of additions and removals
with few field changes means the item key is wrong, not that the programme was rewritten.
`reference/extraction-guide.md` has the causes and the fixes. Do not proceed past a bad
key — every later stage inherits it.

Report back briefly: which documents were compared, how many items each, and anything the
intake flagged — a skipped PDF, a format mismatch, a colour-coded RAG column, a locked file,
a document that produced no items at all. This is a transparency checkpoint, not a request
for approval; continue into the next stage unless the consultant redirects.

A single document can also be extracted by hand when the pairing needs doing manually:

```bash
python scripts/extract.py inputs/week-11/cm-plan.docx --period "Week 11" \
    --name cm-plan -o snapshots/cm-plan-11.json
```

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
the rules file and the `--name` values all carry forward. If they're running the same
documents every week, mention the snapshot archive — but a plain two-file comparison needs
nothing carried over at all, which is usually the easier promise to keep.

Two honest results this skill will produce and should never dress up:

- **Nothing moved.** Deliver it as a finding, and check whether the documents were actually
  updated — an untouched tracker is itself worth raising.
- **The documents disagree.** The plan says an activity is complete; the tracker says the
  training under it hasn't started. Put the contradiction in the update as an ask. It's
  usually the most useful thing in the room.
