---
name: change-impact-assessment-v1.0
description: Generates a baseline change impact assessment workbook (Excel) for a system implementation — SAP S/4HANA, Ariba, Workday, Salesforce or similar — from the programme's own documents. Reads interview and workshop notes, process design models (Signavio/BPMN), functional specifications and org design material; extracts one impact row per process change × stakeholder group; scores each on five weighted dimensions to produce a Low/Medium/High/Critical rating; and derives the training and communication response from the rating. Output is a multi-sheet .xlsx — impact register (as-is → to-be, ratings, training, comms), heatmap, training plan with effort roll-up, comms plan by wave, and source traceability. Use whenever a CM lead wants to build, refresh or sense-check a change impact assessment from project documentation — phrases like "change impact assessment", "CIA", "impact register", "what's the impact of this rollout on each group", "build me the change impacts from these documents", "training needs analysis from the process design", or when someone hands over interview notes and design docs and asks what the change means for the business.
---

# Change Impact Assessment — Baseline Generator

Turns a folder of programme documents into a defensible baseline change impact assessment
workbook. The point is not the spreadsheet — it is that every row traces to a source document,
every rating is arithmetic a client can audit, and every training and comms line is derived
from a rating rather than asserted.

**Deliverable:** a multi-sheet `.xlsx` — Cover, Impact Register, Impact Heatmap, Training Plan,
Comms Plan, Traceability, Reference.

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
| `reference/extraction-guide.md` | How to mine each source type, split/merge rows, and check coverage. **Read before extracting.** |
| `reference/rating-methodology.md` | The five dimensions, 1-5 anchors, weights, bands, overrides, confidence. **Read before scoring.** |
| `reference/response-playbook.md` | Deriving training method/duration/timing and comms channel/wave/sender from a rating. **Read before filling the response columns.** |
| `reference/input-schema.md` | Field-by-field contract for `cia_input.json`. |
| `scripts/generate_cia.py` | Validates the JSON and renders the workbook. |
| `examples/` | A complete worked example — six source documents and the 20-row `sample_cia_input.json` they produce. |

## Process

### Step 1: Intake

Establish, briefly:

1. **The documents.** Ask for whatever exists — interview/workshop notes, Signavio or BPMN
   exports, functional specs, org design, solution scope. Take them in any format; if the user
   points at a folder, read it. **Do not wait for a complete set** — work with what is there and
   record the gaps as open questions.
2. **Programme basics.** Client, solution scope, go-live date, wave/geography split, who owns
   the assessment.
3. **Anything already done.** An existing register, stakeholder analysis, or training needs
   analysis is a starting point, not something to duplicate.

If the user has **no documents** and only a narrative, say so plainly: you can still produce a
register from what they describe, but nearly every row will be Medium or Low confidence, and it
is worth being explicit that the output is a structured hypothesis rather than a baseline.

### Step 2: Extract

Read `reference/extraction-guide.md` and follow its five passes: build the process spine from
the design models, attach the to-be, attach the as-is and human signal from interviews, split
and merge to one row per **process change × stakeholder group**, then score.

Read every document supplied, in full. This is the step that determines whether the assessment
is any good, and there is no shortcut — a register built from skimming produces rows that
describe system features rather than human impacts, and a business audience spots the
difference immediately.

Keep verbatim quotes from interviews. A real sentence from a real person carries more weight in
a steering committee than any adjective you can write.

### Step 3: Score

Read `reference/rating-methodology.md`. Score all five dimensions independently against the
anchors — do not decide the overall rating first and back-fill the dimensions.

Expect a spread across Low, Medium, High and Critical. A register where everything is High gives
the programme no way to prioritise and will not be believed.

Rate **anticipated resistance separately from impact magnitude** — they are different things,
and the confusion between them is the most common flaw in a change impact assessment. A large
welcome change is High impact / Low resistance; a small unwelcome one can be the reverse.

### Step 4: Derive the training and comms response

Read `reference/response-playbook.md`. Rating sets the tier; audience size, frequency of use,
and whether new judgement is required set the method within it.

Write `key_message` from the affected person's point of view, in one sentence, with no acronyms.
Name a real person or role as `comms_owner` for every High and Critical impact — "the change
team" is the least credible sender available.

### Step 5: Write `cia_input.json`

Per `reference/input-schema.md`. Cite source document refs on every row.

### Step 6: Validate and generate

```bash
python3 scripts/generate_cia.py cia_input.json -o "Change Impact Assessment — <Client> v0.1.xlsx"
```

Requires `openpyxl` (`pip install openpyxl`). Use `--validate-only` to check without rendering.

Hard errors block generation — fix them. Warnings do not, but **work through each one before
handing over the file**: they flag exactly the gaps a reviewer will find (a Critical impact with
no owner, a Low-confidence row with no open question, a workstream with no significant impacts,
a source document nothing was derived from). Fix what you can from the documents; where a
warning reflects a genuine unknown, leave it and report it as an open question rather than
papering over it.

### Step 7: Hand over

Give the user the file and a short written summary — not a description of the spreadsheet, but
what the assessment found:

1. **Shape of the change** — how many impacts, the rating distribution, which stakeholder groups
   and workstreams carry the weight.
2. **The three or four things that actually matter** — the most severe impacts, and any
   convergent finding where several rows point at the same underlying problem.
3. **Training and comms load** — total person-hours and days, and any group whose training load
   in the pre-go-live window is not achievable.
4. **Open questions and gaps** — Low-confidence rows, undesigned processes, stakeholder groups
   nobody has interviewed, decisions the programme owes the assessment.
5. **What happens next** — which groups to validate with, in what order.

Lead with the finding, not the file. The user asked for a workbook; what they need is to know
what is in it.

### Step 8: Memo, deck or refresh (only if asked)

For a client-ready memo or steering committee summary, use the `docx` or `pptx` skill.
To refresh an existing assessment, edit the JSON and re-run — the workbook is regenerated
whole, so the JSON is the master, not the spreadsheet.

## The workbook

Ratings, weighted scores, training effort, heatmap counts and the roll-up sheets are **live
Excel formulas**, so a CM lead can re-score an impact in a validation workshop and watch the
ratings, heatmap, training budget and comms plan all move with it. Fifty pre-formatted blank
rows sit under the register with dropdowns and formulas already in place, so impacts can be
added in-workbook. Roll-ups look impacts up by ID, so re-sorting the register is safe.

If the user edits the workbook heavily, the JSON is no longer the master. Say so when you hand
it over, and offer to re-import if they want to keep generating from source.

## Notes

- **Suppliers and other external audiences are the most commonly missed stakeholder group** on
  Ariba and network-based implementations. They do not appear on the client's org chart, are
  rarely interviewed, and their non-adoption is a leading cause of benefit shortfall. Check for
  them explicitly.
- **A small population can carry a Critical impact.** A single analyst whose entire deliverable
  is automated away is easy to miss in a register sorted by headcount, and is exactly the person
  most likely to become a visible casualty of the programme.
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
