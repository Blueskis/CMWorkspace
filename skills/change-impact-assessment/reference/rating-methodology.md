# Change Impact Rating Methodology

The rating model used by `generate_cia.py`. Everything here is mirrored in the
script's constants and in the generated workbook's **Cover** sheet, so a client
can audit how any rating was arrived at.

## Principle

A change impact is rated on **five dimensions**, each scored 1–5, then combined
into a single weighted score and banded into a rating. Dimensions are scored
independently — do not score "how big does this feel overall" and reverse-engineer
the dimensions.

## The five dimensions

### 1. People & Role (weight 30%)

How much the *job itself* changes for the person doing it — tasks, decision rights,
accountability, span of control, headcount, or reporting line.

| Score | Anchor |
|---|---|
| 1 | No change to the role. Same tasks, same decisions, same accountability. |
| 2 | Same role, minor task changes. A few steps look different; no new judgement required. |
| 3 | Meaningful task change within the same role. New activities or decisions added, some old ones removed. |
| 4 | Role substantially redefined. Significant new accountabilities, or work moves to/from this role from elsewhere. |
| 5 | Role created, eliminated, merged, or relocated (e.g. moved into a shared service centre). Headcount or reporting line changes. |

### 2. Process (weight 25%)

How much the process flow, sequence, hand-offs, or cycle time changes.

| Score | Anchor |
|---|---|
| 1 | Process unchanged. |
| 2 | Same flow, cosmetic differences (screen layout, field names, terminology). |
| 3 | Steps added, removed, or resequenced, but the overall flow is recognisable. |
| 4 | Process substantially redesigned — new hand-offs, new approval paths, or a major change in cycle time or entry point. |
| 5 | Process is net-new, eliminated, or fully automated end-to-end. No recognisable predecessor. |

### 3. Technology (weight 20%)

How much the system the user touches changes.

| Score | Anchor |
|---|---|
| 1 | Same system, no visible change. |
| 2 | Same system, updated screens or navigation. |
| 3 | New module within a familiar platform, or a familiar task in a new UI. |
| 4 | New system for this user group, replacing a system they used daily. |
| 5 | New system *and* a new interaction paradigm (e.g. moving from email/spreadsheet to a transactional network, or desktop to mobile/guided buying). |

### 4. Policy & Control (weight 15%)

How much the governing rules change — approval thresholds, segregation of duties,
compliance obligations, mandated behaviour.

| Score | Anchor |
|---|---|
| 1 | No policy change. |
| 2 | Policy wording updated; substance unchanged. |
| 3 | Thresholds, tolerances, or approval routing changed. |
| 4 | New mandatory control introduced, or a discretionary practice becomes enforced by the system. |
| 5 | New compliance/audit obligation with personal or legal accountability, or a previously permitted practice is now blocked outright. |

### 5. Data & Reporting (weight 10%)

How much the data the person creates, maintains, or consumes changes.

| Score | Anchor |
|---|---|
| 1 | No change to data or reports. |
| 2 | Same data, new report format or location. |
| 3 | New fields to populate, or new reports replacing familiar ones. |
| 4 | New master data ownership or stewardship responsibility, or reports rebuilt on a new data model. |
| 5 | New data domain the group has never maintained, or a self-service reporting model replacing a report-request model. |

## Weighted score

```
Weighted Score = (People × 0.30) + (Process × 0.25) + (Technology × 0.20)
               + (Policy × 0.15) + (Data × 0.10)
```

Range: 1.00 – 5.00. Written into the workbook as a **live Excel formula**, so a
CM lead can adjust a dimension score in validation workshops and watch the rating
move.

**Why People and Process carry the most weight:** change management effort is
driven by how much a person's day-to-day job changes, not by how impressive the
technology is. A system swap that leaves the job identical needs far less
intervention than a role redesign delivered on familiar software.

## Rating bands

| Weighted Score | Rating | What it means for the response |
|---|---|---|
| < 1.75 | **Low** | Awareness only. Comms, no dedicated training. |
| 1.75 – 2.74 | **Medium** | Job aid or e-learning. Standard comms cadence. |
| 2.75 – 3.74 | **High** | Instructor-led or virtual ILT, hands-on practice, targeted comms with named sponsor. |
| ≥ 3.75 | **Critical** | Full curriculum plus go-live hypercare/floorwalking, individually-tracked adoption, sponsor-led engagement, and an explicit resistance plan. |

## Overrides — when to break the formula

The score is a baseline, not a verdict. Override the computed rating (record it in
`rating_override` with a mandatory `rating_override_reason`) when:

- **Volume amplifies it.** A Medium impact hitting 4,000 requisitioners on day one
  may need a Critical-grade response purely on volume. Rate the impact honestly,
  override the *response*, and say why.
- **Political sensitivity.** Union-consulted change, a headcount implication, or a
  loss of visible status can make a technically-small change behaviourally large.
- **A hard compliance date.** If getting it wrong carries a regulatory penalty, the
  response tier goes up regardless of score.
- **Single point of failure.** Two people in the world do this, and both are
  skeptical — the score understates the risk.

Never override downward just to shrink the training budget. If a rating is being
argued down, that argument belongs in the `notes` column where the sponsor can see it.

## Anticipated resistance (rated separately)

Impact magnitude and resistance are **not the same thing**. A large, welcome change
(automating a hated manual reconciliation) is High impact / Low resistance. A small,
unwelcome change (a new approval step for a manager used to spending freely) can be
Low impact / High resistance.

| Level | Signals in the source material |
|---|---|
| **Low** | Group asked for this, or is indifferent. Language in interviews is neutral-to-positive. |
| **Medium** | Group accepts the rationale but is worried about workload, timing, or capability. Hedged language: "as long as…", "provided that…". |
| **High** | Group disputes the rationale, loses discretion/status/headcount, has been burned by a prior rollout, or is being asked to absorb work from elsewhere. Look for sarcasm, prior-failure references, and "we already tried this". |

High resistance always requires a `mitigation_actions` entry, whatever the impact rating.

## Confidence

Every row records how it was derived — this is what makes the output a defensible
*baseline* rather than an assertion.

| Confidence | Meaning |
|---|---|
| **High** | Stated explicitly in a source document. The `source_ref` points at the sentence. |
| **Medium** | Inferred by combining two or more sources (e.g. an FS describes the new approval matrix, an interview describes today's practice). |
| **Low** | Extrapolated from a pattern in the solution design, with no direct source statement. Requires business validation before baselining. |

**Every Low-confidence row must carry an open question in `notes`.** These become
the agenda for the validation workshop.
