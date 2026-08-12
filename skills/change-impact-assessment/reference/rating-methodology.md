# Change Impact Rating Methodology

**The client template owns the scoring model.** Its `Change Impact Ratings` sheet carries the
authoritative anchors, and the generator reproduces its arithmetic exactly. This document
restates that model for use during extraction and adds the four things the template does not
define: the band cut-offs on the overall average, resistance, confidence, and overrides.

## The model

Three dimensions — **People**, **Process**, **Technology** — each scored **0–3**.
**Overall Impact = the unweighted average of the three**, exactly as the template's own column
header says, written into the workbook as a live Excel formula.

| Score | Label |
|---|---|
| 0 | No change |
| 1 | Low |
| 2 | Medium |
| 3 | High |

## Anchors (from the template's rubric sheet)

### People — role change / new role, new skills required, change in behaviour or mindset

| Score | Anchor |
|---|---|
| 0 | No change. Same role. |
| 1 | Minimal additional or removed activity. Minimal behaviour change. Same role, or same role at higher frequency. |
| 2 | Requires a new activity or process step while using existing resources. Expanded scope without new headcount, new skills required, or a reduction in manual activity. |
| 3 | Requires additional hiring, new skills acquisition or reorganisation of functions. Major increase or decrease in work effort. High behavioural or mindset shift to execute the new business vision. |

### Process — automation, approval/regulatory, new process flow, information retrieval, business documentation

| Score | Anchor |
|---|---|
| 0 | Same process, no change. |
| 1 | Minor changes to the process steps. Some data within the process looks different, or the system of record changes. Optional additional steps; similar steps in a different system. |
| 2 | Simplified by shifting toward automation. Added or deleted process steps or activities. |
| 3 | Significant changes to the process steps. Changes to the hand-off of process ownership and accountability. Critical data elements to input, or sources, differ from the existing data structure. Multiple new process steps, or severe upstream/downstream impact. |

### Technology — interface/GUI, functionality, infrastructure

| Score | Anchor |
|---|---|
| 0 | No change. |
| 1 | Same system with added or enhanced features. Some fields or screen layout change; fields become more granular. |
| 2 | Same system with a version upgrade (new features added to the existing system). Gain or loss of system functionality. New workbench. |
| 3 | New system added or replaced. Substantial new users to an existing system. (A new workbench counts as 3 only in exceptional cases where the magnitude of change is high.) |

## Band cut-offs — this skill's assumption, not the template's

The template defines the per-dimension 0–3 scale but **does not state cut-offs for the overall
average**. The generator uses:

| Overall average | Rating |
|---|---|
| ≥ 2.50 | **High** |
| 1.50 – 2.49 | **Medium** |
| 0.50 – 1.49 | **Low** |
| < 0.50 | **No / Minimal** |

This is stated as an assumption on the workbook's Assessment Info sheet. **Confirm it with the
client before baselining** — if they have their own convention, change `BANDS` in
`scripts/generate_cia.py` and it flows through the register colouring, heatmap and roll-ups.

## Scoring notes

**Score each dimension independently against the anchors.** Do not decide the overall rating
first and back-fill the three scores.

**On a greenfield implementation, Technology saturates.** If the programme replaces the system
outright, almost every row scores Technology 3 — that is the anchor working correctly, not a
scoring error. It does mean the People and Process scores are doing nearly all the
discriminating work, so score those two with particular care, and say so at handover: an
average dragged upward by a constant is worth flagging to whoever reads the distribution.

**A group that keeps its own system scores Technology 0 or 1** even inside a big programme.
Downstream teams reading a changed document format are the common case.

**Expect a spread.** A register where everything is High gives the programme no way to
prioritise and will not be believed. If you don't have a spread, re-score against the anchors
rather than adjusting to taste.

## What the template drops, and where it goes

The template has no policy or data dimension. Policy, control, compliance, data-ownership and
engagement impacts are real and still need recording — put them in the **Others (e.g., policies,
engagements)** column, where the template intends them. In the JSON that is `other_impacts`.

This matters more than it looks. On an Ariba implementation the largest single category of
change is control being enforced where it was previously advisory, and that lands in Others
rather than in any scored dimension. A row can therefore be Medium by score and still be the
one that generates the most resistance — CI-005 in the worked example is exactly this.

## Overrides — when to break the arithmetic

The average is a baseline, not a verdict. Record an override in `rating_override` with a
mandatory `rating_override_reason` when:

- **Volume amplifies it.** A Medium impact hitting several thousand people on day one may need
  a High-grade response purely on volume.
- **Political sensitivity.** Union-consulted change, a headcount implication, or a visible loss
  of status can make a technically-small change behaviourally large.
- **A hard compliance date.** Regulatory exposure raises the response tier regardless of score.
- **Single point of failure.** Two people do this, and both are sceptical.

The override is recorded in the **Others** column so the template's own arithmetic in the
Overall Impact column stays untouched and auditable. Never override downward to shrink a
training budget; if a rating is being argued down, that argument belongs in the notes where the
sponsor can see it.

## Anticipated resistance — rated separately

Impact magnitude and resistance are **not the same thing**, and conflating them is the most
common flaw in a change impact assessment. A large, welcome change (automating a hated manual
reconciliation) is High impact / Low resistance. A small, unwelcome change (a new approval
constraint on a manager used to spending freely) can be Low impact / High resistance.

| Level | Signals in the source material |
|---|---|
| **Low** | The group asked for this, or is indifferent. Neutral-to-positive language. |
| **Medium** | Accepts the rationale but worried about workload, timing or capability. Hedged language: "as long as…", "provided that…". |
| **High** | Disputes the rationale, loses discretion/status/headcount, has been burned by a prior rollout, or is absorbing work from elsewhere. Look for sarcasm, prior-failure references, "we already tried this". |

High resistance always requires a `mitigation_actions` entry, whatever the impact rating.

The template has no resistance column. It is carried in the JSON, surfaced on the Comms Plan
sheet, and becomes a register column under `--extended`.

## Confidence

Every row records how it was derived — this is what makes the output a defensible *baseline*
rather than an assertion.

| Confidence | Meaning |
|---|---|
| **High** | Stated explicitly in a source document. The `source_ref` points at the sentence. |
| **Medium** | Inferred by combining two or more sources (e.g. an FS describes the new approval matrix, an interview describes today's practice). |
| **Low** | Extrapolated from a pattern in the solution design, with no direct source statement. Requires business validation before baselining. |

**Every Low-confidence row must carry an open question in `notes`.** These become the agenda for
the validation workshop and are listed on the Traceability sheet.
