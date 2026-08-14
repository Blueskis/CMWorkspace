---
name: change-impact-assessment-v1.0
description: Populates the client's own CIA template (Excel) with a baseline change impact assessment for a system implementation — SAP S/4HANA, Ariba, Workday, Salesforce or similar — built from the programme's own documents. Reads interview and workshop notes, meeting recordings and transcripts (.vtt/.srt from Teams, Zoom or Meet, or raw audio transcribed locally), process design models (Signavio/BPMN), functional specifications, slide decks, spreadsheets and org design material in Word, PowerPoint, Excel, PDF and BPMN formats; extracts one impact row per process change × stakeholder group against a four-level process taxonomy (L1-L4); scores People, Process and Technology 0-3 against the template's own rubric and averages them into an overall impact; and derives the training and communication response from the resulting band. Output is the client template populated and untouched in structure, plus supplementary heatmap, training plan with effort roll-up, comms plan by wave, and source traceability sheets. Use whenever a CM lead wants to build, refresh or sense-check a change impact assessment from project documentation — phrases like "change impact assessment", "CIA", "impact register", "what's the impact of this rollout on each group", "build me the change impacts from these documents", "training needs analysis from the process design", "fill in the CIA template", "here are the interview recordings and the process design", or when someone hands over interview notes, transcripts and design docs and asks what the change means for the business.
---

# Change Impact Assessment — Baseline Generator

Turns a folder of programme documents into a defensible baseline change impact assessment, in
the client's own template. The point is not the spreadsheet — it is that every row traces to a
source document, every rating is arithmetic a client can audit, and every training and comms
line is derived from a rating rather than asserted.

**Deliverable:** the client's CIA template populated — `CIA Template` and `Change Impact Ratings`
carried through with their headers, theme colours, merges and rubric untouched — plus
supplementary `Impact Heatmap`, `Training Plan`, `Comms Plan`, `Traceability` and
`Assessment Info` sheets derived from the register.

**The template owns the model.** Four-level process taxonomy (L1–L4 with codes), three
dimensions — People, Process, Technology — each scored **0–3** against the anchors on the
template's own rubric sheet, averaged unweighted into Overall Impact. Do not substitute a
different scoring model; if the client supplies a different template, point the script at it
with `--template` and adjust the column map.

## What this produces, and what it does not

It produces a **baseline** — a first, evidence-linked draft that gives a validation workshop
something concrete to argue with. It does not produce a validated assessment. Rows inferred
rather than stated are marked Low confidence and carry an open question, and those are the
agenda for the business validation that has to follow. Say this to the user plainly when you
hand the file over; a CIA presented as finished when it is a first pass is how these documents
lose credibility.

## Files in this skill

| File | Use it for |
|---|---|
| `templates/CIA_Template.xlsx` | The client template. The default input to the generator. |
| `reference/source-ingestion.md` | Getting client material into a readable state — formats, BPMN, and the audio decision. **Read at intake.** |
| `reference/interview-evidence.md` | Reading interviews and verbatim transcripts as evidence — attribution, quotes, contradictions, what not to believe. **Read before mining any interview.** |
| `reference/extraction-guide.md` | How to mine each source type, build the L1–L4 spine, split/merge rows, and check coverage. **Read before extracting.** |
| `reference/rating-methodology.md` | The template's 0-3 anchors restated, plus the band cut-offs, overrides, resistance and confidence — the four things the template doesn't define. **Read before scoring.** |
| `reference/response-playbook.md` | Deriving training method/duration/timing and comms channel/wave/sender from a rating. **Read before filling the response columns.** |
| `reference/input-schema.md` | Field-by-field contract for `cia_input.json`. |
| `scripts/ingest_sources.py` | Normalises a folder of mixed client files into readable text + a source manifest. |
| `scripts/generate_cia.py` | Validates the JSON and renders the workbook. |
| `examples/` | A complete worked example — six source documents and the 20-row `sample_cia_input.json` they produce. |

## Process

### Step 1: Intake

Establish, briefly:

1. **The documents.** Ask for whatever exists — interview and workshop notes, meeting
   recordings or transcripts, Signavio/BPMN exports, functional specs, org design, solution
   scope. **Take them in any format**: Word, PowerPoint, PDF, Excel, BPMN, `.vtt`/`.srt`
   transcripts, or a folder of all of it. **Do not wait for a complete set** — work with what is
   there and record the gaps as open questions.

   **If there are voice recordings, ask for the meeting platform's transcript first.** Teams,
   Zoom and Meet generate one automatically, with speaker labels and correctly spelled names.
   Consultants often have recordings and don't realise a transcript already exists. It is
   materially better evidence than machine transcription, and it costs nothing.
2. **Programme basics.** Client, solution scope, go-live date, wave/geography split, who owns
   the assessment.
3. **Anything already done.** An existing register, stakeholder analysis, or training needs
   analysis is a starting point, not something to duplicate.

If the user has **no documents** and only a narrative, say so plainly: you can still produce a
register from what they describe, but nearly every row will be Medium or Low confidence, and it
is worth being explicit that the output is a structured hypothesis rather than a baseline.

### Step 2: Ingest

Read `reference/source-ingestion.md`, then normalise everything into readable text with a stable
reference per source:

```bash
python3 scripts/ingest_sources.py /path/to/client/documents -o ingested/
```

Then, before reading anything:

1. **Correct `ingested/sources.json` by hand.** The script guesses `type` from the file
   extension; only you can tell interview notes from a functional spec. Fix types and titles,
   add dates and participants.
2. **Open every PDF and image with the Read tool** — the report lists them. They are not
   text-extracted on purpose: process diagrams, org charts and page layout carry information a
   text extractor discards, and on a CIA the diagram is often the most informative thing in the
   document.
3. **Deal with any audio.** Claude cannot listen to audio, so a recording without a transcript
   is not yet evidence. Get the platform transcript, or transcribe locally with `--transcribe`.
   Never quietly drop a recording — an untranscribed interview is a gap in the assessment and
   should be named at handover.

### Step 3: Extract

Read `reference/extraction-guide.md` and follow its five passes: build the L1–L4 process spine
from the design models, attach the to-be, attach the as-is and human signal from interviews,
split and merge to one row per **process change × stakeholder group**, then score.

L4 is where the register earns its keep — it is the level at which one process splits into the
different things it means for different people. If every L4 just restates its L3, the rows have
not been split finely enough.

Read every document supplied, in full. This is the step that determines whether the assessment
is any good, and there is no shortcut — a register built from skimming produces rows that
describe system features rather than human impacts, and a business audience spots the
difference immediately.

**For interviews and transcripts, read `reference/interview-evidence.md` first.** A verbatim
transcript is not a better set of notes, it is a different kind of evidence: raw rather than
pre-interpreted. It needs attribution discipline — who said something determines whether it is
testimony, a claim, design intent or hearsay — and it rewards attention to hesitation,
contradiction, and the questions nobody answered. It also carries the one thing notes never do:
the actual sentences.

Keep verbatim quotes. A real sentence from a real person carries more weight in a steering
committee than any adjective you can write. Attribute them by role, not by name — the register
goes to a committee that may include the speaker's manager.

**Never bank a number heard only in speech.** Headcounts, volumes and percentages from an
interview are Low confidence until corroborated against an HR extract or system report, and
machine transcription mangles exactly the vocabulary a CIA runs on — figures, acronyms, system
and module names.

### Step 4: Score

Read `reference/rating-methodology.md` and the template's own `Change Impact Ratings` sheet.
Score People, Process and Technology 0-3 independently against the anchors — do not decide the
overall rating first and back-fill the three. Write the matching description alongside each
score; the template pairs every score with a description column, and a score with no explanation
is the first thing a client challenges.

Expect a spread. A register where everything is High gives the programme no way to prioritise
and will not be believed. On a greenfield implementation Technology sits at 3 almost everywhere
— that is the anchor working correctly, but it means People and Process are doing all the
discriminating, so score those two with particular care and say so at handover.

Policy, control, compliance, data-ownership, engagement and commercial impacts have no dimension
in this template. Record them in **Others**, where the template intends them. On a system
implementation with enforced controls, that column often holds the most contentious material in
the assessment.

Rate **anticipated resistance separately from impact magnitude** — they are different things,
and the confusion between them is the most common flaw in a change impact assessment. A large
welcome change is High impact / Low resistance; a small unwelcome one can be the reverse.

### Step 5: Derive the training and comms response

Read `reference/response-playbook.md`. Rating sets the tier; audience size, frequency of use,
and whether new judgement is required set the method within it. Use the People score to split
the High band — People 3 means the role itself is being redesigned, which needs a curriculum
plus hypercare, not a course.

Write `key_message` from the affected person's point of view, in one sentence, with no acronyms.
Name a real person or role as `comms_owner` for every High-rated impact — "the change team" is
the least credible sender available.

### Step 6: Write `cia_input.json`

Per `reference/input-schema.md`. Cite source document refs on every row.

### Step 7: Validate and generate

```bash
python3 scripts/generate_cia.py cia_input.json -o "Change Impact Assessment — <Client> v0.1.xlsx"
```

Requires `openpyxl` (`pip install openpyxl`).

| Flag | Use |
|---|---|
| `--validate-only` | Check the JSON without rendering |
| `--template <path>` | Point at a different client template (defaults to the vendored copy) |
| `--extended` | Append eight governance columns after the template's V — Impact ID, stakeholder group, anticipated resistance, change champion, source ref, confidence, validation status, notes |

**Default output matches the client template exactly** — verified on every run against the
original file. Use `--extended` for the working copy the CM team edits, and the default for the
version that goes to the client, unless they ask for the governance columns. `--extended` also
makes the roll-up sheets sort-safe (they key off Impact ID via INDEX/MATCH) and makes the
stakeholder-group heatmap live rather than a snapshot.

Hard errors block generation — fix them. Warnings do not, but **work through each one before
handing over the file**: they flag exactly the gaps a reviewer will find (a Critical impact with
no owner, a Low-confidence row with no open question, a workstream with no significant impacts,
a source document nothing was derived from). Fix what you can from the documents; where a
warning reflects a genuine unknown, leave it and report it as an open question rather than
papering over it.

### Step 8: Hand over

Give the user the file and a short written summary — not a description of the spreadsheet, but
what the assessment found:

1. **Shape of the change** — how many impacts, the rating distribution, which stakeholder groups
   and L1 areas carry the weight.
2. **The three or four things that actually matter** — the most severe impacts, and any
   convergent finding where several rows point at the same underlying problem.
3. **Training and comms load** — total person-hours and days, and any group whose training load
   in the pre-go-live window is not achievable.
4. **Open questions and gaps** — Low-confidence rows, undesigned processes, stakeholder groups
   nobody has interviewed, decisions the programme owes the assessment.
5. **What happens next** — which groups to validate with, in what order.

Lead with the finding, not the file. The user asked for a workbook; what they need is to know
what is in it.

### Step 9: Memo, deck or refresh (only if asked)

For a client-ready memo or steering committee summary, use the `docx` or `pptx` skill.
To refresh an existing assessment, edit the JSON and re-run — the workbook is regenerated
whole, so the JSON is the master, not the spreadsheet.

## The workbook

Overall Impact, the heatmap counts and the roll-up sheets are **live Excel formulas**, so a CM
lead can re-score a Degree of Impact in a validation workshop and watch the average, heatmap,
training roll-up and comms plan move with it. Fifty pre-formatted blank rows sit under the
register with 0-3 dropdowns and formulas already in place, so impacts can be added in-workbook.

Two things to say at handover:

- **The band cut-offs are an assumption.** The template defines the 0-3 dimension scale but not
  the cut-offs on the overall average. The generator uses High ≥ 2.50 / Medium 1.50–2.49 /
  Low 0.50–1.49 / No-Minimal < 0.50, states this on the Assessment Info sheet, and it is
  changeable in one constant. Confirm it with the client before baselining.
- **If they edit the workbook heavily, the JSON is no longer the master.** Offer to re-import if
  they want to keep generating from source.

## Notes

- **Suppliers and other external audiences are the most commonly missed stakeholder group** on
  Ariba and network-based implementations. They do not appear on the client's org chart, are
  rarely interviewed, and their non-adoption is a leading cause of benefit shortfall. Check for
  them explicitly.
- **A small population can carry the most severe impact in the register.** A single analyst
  whose entire deliverable is automated away is easy to miss in a register sorted by headcount,
  and is exactly the person most likely to become a visible casualty of the programme.
- **An undesigned process is a finding, not a blocker.** Where the design is incomplete, record
  the row at Low confidence with the gap as the open question. A CIA that surfaces "nobody has
  designed emergency purchasing and Facilities has asked twice" has earned its cost before
  anyone reads the ratings.
- **The register is a starting point for further analysis, not the end of it.** It tells you
  *what* changes and *who* it lands on. It does not tell you which specific individuals to
  engage, whether the programme has the sponsorship and capacity to deliver what the register
  implies, or why a supportive person still isn't moving. Where the register makes the case for
  one of those questions — many rows pointing at the same handful of behaviours, a stakeholder
  group whose resistance is concentrated in a few people — name the question for the
  practitioner, but don't launch into answering it uninvited.
