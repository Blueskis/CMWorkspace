---
name: cutover-comms-plan-v1.0
description: Builds a cutover communications plan — first as an editable browser artifact the CM member can adjust, then exported to Excel when they are happy with the draft. One row per comms with Purpose, Audience, Channel, Sender, Owner, Approver, Dependencies and a deliberately blank Comms Content Link column for later linkage to the drafted content. Applies cadence rules that set how many comms a cutover needs based on its complexity (a brand-new system defaults to 2 — before go-live and after; an upgrade or change to an existing system defaults to 5 — T-14, T-7, T-1, cutover begins, go-live) plus modifiers for downtime, required user action, external audiences, hypercare, multi-wave rollouts and go/no-go gates. Populates the CM member's own existing Excel template when they supply one, otherwise generates a formatted workbook. Use whenever the user wants to plan, build, scope, or sense-check communications around a cutover, go-live, deployment, migration, system upgrade or system retirement — phrases like "cutover comms plan", "go-live communications", "how many comms do we need for this go-live", "build the comms schedule for the deployment", "populate our comms plan template".
---

# Cutover Communications Plan Builder

Turns a CM member's description of a cutover into a populated communications plan
workbook: one row per comms, with the rules for *how many* comms and *when* derived
from the cutover's complexity rather than guessed.

The plan covers the comms **schedule and governance**, not the comms **content**. The
`Comms Content Link` column is intentionally left blank on generation — it exists so
each line item can later be linked to the drafted collateral.

## What gets produced

A workbook with one row per comms and these columns:

| Column | What it holds |
|---|---|
| Comms ID | Unique reference (C01, C02…) |
| Cutover Milestone | Anchor point — T-14, T-1, Cutover begins, Go-live, T+5 |
| Planned Send Date | Actual calendar date/time |
| Comms Title | Working title or subject line |
| **Purpose** | What the comms is *for* — the decision, action or awareness it drives |
| **Audience** | Who receives it |
| **Channel** | How it is delivered |
| **Sender** | Whose name it goes out under |
| **Owner** | Who drafts, schedules and sends it |
| **Approver** | Who signs off before it goes out |
| **Dependencies** | What must be true or done first |
| **Comms Content Link** | *Blank by design* — future link to the drafted content |
| Status | Not started / Drafting / In review / Approved / Scheduled / Sent |
| Notes | Anything else |

Plus a `Plan Info` sheet recording the cutover type, complexity tier, the cadence rule
applied and which modifiers were used — so the comms count is auditable, not arbitrary
— and a `Reference` sheet with the column dictionary and dropdown lists.

**Sender vs. Owner vs. Approver** trips people up, so hold the distinction firmly:
the *sender* is the voice the message goes out under (authority), the *owner* drafts
and sends it (delivery), the *approver* signs it off (control). They are usually three
different people, and the sender's seniority should scale with the size of the ask.

## Process

### Step 1: Scope the cutover

Ask these — all at once, they're quick:

1. **System / project name, and the go-live date.**
2. **Cutover type**: brand-new system, an upgrade/change to an existing system, a
   decommission/retirement, or a behind-the-scenes migration with no user-visible change?
3. **Audiences**: who is affected, roughly how many, and are any of them external
   (customers, vendors, partners, regulators)?
4. **Is there a downtime/outage window** where the system is unavailable, and how long?
5. **Do users have to do anything before cutover** (clear queues, save work, submit
   early, re-enrol)?
6. **Is there a formal Go/No-Go gate, a hypercare period, or multiple waves?**
7. **Default Owner, Approver and Sponsor names** — so every row doesn't need asking about
   individually.

If the member has an **existing Excel template**, ask for the path now — the plan will
be written into their template rather than a generated one.

Don't stall on a thin answer. Anything not given, infer the most defensible default,
state the assumption, and let them correct it in Step 3.

### Step 2: Apply the cadence rules to derive the line items

**Base count by cutover type:**

| Cutover type | Base | Line items |
|---|---|---|
| **Brand-new system** (net-new capability, no established way of working displaced) | **2** | Pre go-live awareness (T-5); Go-live / now available (T+0) |
| **Upgrade or change to an existing system** | **5** | T-14 reminder; T-7 reminder; T-1 reminder; Cutover begins; Go-live |
| Decommission / retirement | 4 | T-14; T-7; T-1 final shutdown notice; Service retired |
| Behind-the-scenes migration, no user-visible change | 2 | T-7 notice; Migration complete |

**Complexity modifiers** — each adds specific named line items on top of the base:

| # | Trigger | Adds |
|---|---|---|
| M1 | Business downtime / outage window | +1 service restored (+2 if no "cutover begins" comms in the base to cover outage start) |
| M2 | Users must act before cutover | +1 action-required notice at T-3; +1 chaser at T-1 if completion is tracked and material |
| M3 | External audiences | +1 per distinct external audience, issued at T-21 (external parties need longer lead and contractual notice periods may apply) |
| M4 | Hypercare / elevated support period | +2 — hypercare and how to get help (T+1); hypercare close / back to BAU |
| M5 | Multi-wave or phased rollout | base set **per wave**, plus 1 programme-level "what's coming and which wave you're in" and 1 "all waves complete" |
| M6 | Checkpoint calls during the cutover | +1 per checkpoint — a long cutover runs several, and each one's outcome is a comms |
| M7 | Formal Go/No-Go gate with rollback option | +1 Go/No-Go outcome comms straight after the gate |
| M8 | Regulated, high-risk, or board/exec-visible | +2 — exec pre-cutover brief; exec close-out |
| M9 | Training or readiness prerequisite | +1 readiness reminder at T-21, targeted at non-completers only |

**Merge, don't stack.** Where two derived items land on the same audience at the same
milestone, merge them into one line item with a combined purpose. A go-live comms
routinely absorbs M1's "service restored" and M4's "how to get help"; count it once.

**Floor and ceiling:**

- **Floor: 2.** Never fewer than one comms before go-live and one after, whatever the
  cutover. A plan with nothing after go-live is not a plan.
- **Ceiling: 6 push comms per audience.** Above that, consolidate, or move the
  lower-value items to pull channels (intranet, banner) rather than another email.
  Say so explicitly when the cap bites — comms fatigue costs you the T-1 reminder,
  which is the one that actually matters.
- **Cut anything without a distinct purpose from its neighbour.** A reminder that
  repeats the previous one verbatim trains people to stop reading.

**Show the arithmetic** when you present the derived plan, e.g.
*"Upgrade base 5 + M1 downtime (+1) + M2 user action (+1) = 7, less 1 merged (go-live
absorbs service-restored) = **6 comms**."*

**Resulting complexity tier**, for the Plan Info sheet:

| Tier | Count | Typical shape |
|---|---|---|
| 1 — Low | 2 | New system or silent migration; single internal audience; no downtime, no user action |
| 2 — Standard | 5 | Upgrade/change; internal audiences; downtime covered by cutover-begins and go-live |
| 3 — Elevated | 6–9 | Base plus 2–4 modifiers |
| 4 — Complex | 10+ | Multi-wave, external, or regulated. Per-audience cap applies and consolidation is mandatory |

### Step 3: Pre-fill every line item, then have it corrected

Do **not** interrogate the member field by field across every comms — that's 7 questions
× 6 comms and they'll abandon it. Instead:

1. Draft every row using `references/line-item-library.md`, which carries default
   purpose, audience, channel, sender, owner, approver and dependencies for each
   standard line item.
2. Adapt the defaults to what they actually told you in Step 1 (real names, real
   audiences, real dates counted back from go-live).
3. Present the full table in chat and ask them to correct it — reviewing is far
   cheaper than composing. Flag explicitly which cells are assumptions.

Purpose lines must say what the comms *does*, not what it is. "T-7 reminder" is not a
purpose; "reinforce the downtime window and point users to the job aids before the
freeze" is.

### Step 4: Validate before building

Run these checks and report anything that fails — this is where the plan earns its keep:

1. **Completeness** — every row has purpose, audience, channel, sender, owner, approver.
2. **Separation of duties** — owner ≠ approver. Flag any row where they're the same person.
3. **Chronology** — send dates ascending and consistent with the milestone; nothing
   labelled "before" dated after go-live.
4. **Approval lead time** — at least 3 business days between draft-ready and send.
   Flag any comms whose approval window is too tight, especially ones depending on a
   Go/No-Go outcome, which cannot be pre-scheduled.
5. **Audience load** — no audience over the 6-push ceiling.
6. **Dependency realism** — every "cutover begins" and "go-live" comms must name the
   runbook step or sign-off that triggers it. Without one it gets sent by guesswork at
   3am, or not at all.
7. **Out-of-hours ownership** — comms falling outside business hours need an owner who
   is actually on the cutover bridge, not the CM lead who is asleep.
8. **Coverage** — at least one comms before and one after go-live, per audience.
9. **Content link blank** — confirm it's empty by design, not left empty by accident.

### Step 5: Build the workbook

There are two routes. **Default to the interactive one** — a CM member almost always
wants to adjust the draft before it becomes a file.

**Route A — the editable artifact (preferred).** Publish
`assets/cutover-comms-plan.html` with the Artifact tool and hand over the link. It runs
the same cadence rules and the same nine checks live in the browser, lets the member
edit every field in place, and exports the finished plan to `.xlsx` themselves when
they're happy with it. Edits persist locally, so they can come back to a part-finished
draft. Their "Export spec JSON" button produces exactly the spec Route B consumes, so
the two routes compose: draft in the browser, then run the export through the script to
land it in a client template.

**Route B — the script**, for populating an existing client template, or when the
member wants the file straight away with no editing round. Write the spec to JSON (see
`references/example_spec.json` for the shape), then:

```bash
pip install openpyxl   # if not already present

# Generated workbook
python3 scripts/build_comms_plan.py --spec spec.json --out cutover_comms_plan.xlsx

# Or populate the member's own template
python3 scripts/build_comms_plan.py --spec spec.json --out cutover_comms_plan.xlsx \
    --template "their_template.xlsx" [--sheet "Comms Plan"] [--header-row 3]
```

In template mode the script auto-detects the header row, matches the template's own
column names to the canonical fields by synonym, appends any required column the
template lacks (including `Comms Content Link`), preserves the template's formatting,
and prints what it matched. **Read that output** — if it reports columns it couldn't
match, or data it couldn't write, resolve it with `--sheet`/`--header-row` or tell the
member which of their columns went unpopulated. Don't hand over a silently half-filled
template.

**The script will not overwrite a populated template.** Client "templates" are very
often a *previous* cutover's completed plan rather than a blank form, so writing at the
first data row destroys real project history. When rows are already present the script
stops and makes you choose `--append` (keep theirs, add beneath) or `--replace-rows`
(clear and rewrite). Default to `--append` unless the member says otherwise — their
history is usually the reason they kept the file.

#### Template profiles

`--list-profiles` shows the built-in client formats. A profile pins ambiguous columns
explicitly, translates the plan into the client's own vocabulary, and fills any column
of theirs that can be derived. It is auto-detected from the template's headers;
`--no-profile` turns that off.

`eng-cutover` covers a cutover **activity task list** — a runbook where comms are rows
among other cutover activities, keyed by `Activity Category` / `Activity Type` /
`Comms #`. Against that format the script:

- maps the milestone onto their category vocabulary (Reminder Comms, Cutover Period
  Comms, Checkpoint Comms, Go Live Comms) and the status onto theirs, where
  **Disseminated** means sent;
- **splits a multi-audience comms into one row per audience**, because that format
  carries one audience per row — this is what makes their `#2a` / `#2b` suffixes mean
  something, and it changes the row count, which the script reports;
- snaps generated wording onto the template's own strings, including trailing-space
  variants and values the client has extended, so their filters keep grouping;
- flags any value with no precedent in the file, so a new category is a decision;
- derives their `Draft Created On` from the send date and the 3-business-day approval
  lead time;
- appends `Purpose`, `Channel`, `Sender` and `Comms Content Link`, which runbook
  formats routinely lack even though the CM member needs all four.

Columns are appended at the end, never inserted: `insert_cols` shifts values without
moving merged ranges, autofilters, column widths or data validations, so inserting
silently points a client's dropdowns at the wrong columns.

`python3 scripts/build_comms_plan.py --list-fields` prints the spec keys.

The artifact carries its own copy of the cadence rules, the line-item defaults and the
checks. **If you change a rule in this skill, change it in
`assets/cutover-comms-plan.html` too** — `CUTOVER_TYPES`, `MODIFIERS`, `LIB` and
`validate()` are the corresponding pieces — or the two routes will start disagreeing
about how many comms a cutover needs.

### Step 6: Hand back

Give them the file plus, in chat: the comms count and how it was derived (the
arithmetic from Step 2), anything that failed validation in Step 4, and the specific
assumptions they should check. Note that `Comms Content Link` is deliberately blank and
is where drafted content gets linked once it exists.

## Notes

- The cadence rules are defaults, not law. If the member has a house standard or a
  client template that mandates a different rhythm, follow theirs and say which rule
  you overrode — but still apply the floor, the per-audience ceiling and the Step 4
  validation, since those catch real failures regardless of cadence.
- A comms plan is not a stakeholder plan, and it is not a case for change. If the real
  question is *who to engage and how hard*, or *whether the message will land at all*,
  that is separate analysis — do it first, and let its conclusions shape the Purpose
  column here rather than trying to answer it through the schedule.
- This is a build tool, not a diagnostic. It takes the cutover as given and schedules
  the comms around it; it does not assess whether the change itself is well set up.
- Anything scheduled to auto-send that depends on a Go/No-Go outcome is the single
  most common way these plans fail in practice — an "it's live!" email going out
  during a rollback. Check for it every time.
