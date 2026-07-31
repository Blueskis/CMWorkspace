---
name: dice-framework-v1.0
description: Predicts a project or change initiative's likelihood of success using BCG's DICE framework (Duration, Integrity, Commitment x2, Effort). Asks the user 5 rating questions — one per factor, each scored 1-4 against defined anchors — calculates the DICE score (D + 2I + 2C1 + C2 + E, range 7-28), classifies the project as Win, Worry, or Woe zone, and gives targeted recommendations based on which specific factor(s) are driving risk. Use this skill whenever the user wants to predict, score, or assess the likelihood of success/failure of a project, program, or change initiative — including phrases like "DICE score", "will this project succeed", "predict project outcome", "is this project at risk", or when scoping/reviewing a project and its execution risk isn't yet quantified. Also trigger for a client-ready memo or steering committee summary of the DICE result.
---

# BCG DICE Framework — Project Outcome Predictor

Predicts the likelihood a project or change initiative will succeed, using BCG's DICE framework (Sirkin, Keenan, Jackson — "The Hard Side of Change Management"). Produces a numeric score, a Win/Worry/Woe classification, and recommendations targeted at whichever factor is actually driving the risk.

## Background (for your own calibration, don't dump this on the user)

DICE scores five factors, each rated 1 (best/lowest risk) to 4 (worst/highest risk):

- **D — Duration**: how long between formal project reviews (short review cycles reduce risk regardless of total project length)
- **I — Integrity**: the project team's own ability to execute — leadership, skill, capacity, clarity of roles
- **C1 — Commitment (senior)**: how visibly and consistently senior leadership/sponsors back the project with attention and resources
- **C2 — Commitment (local)**: how willing the people who must actually change their day-to-day work are
- **E — Effort**: how much additional workload the change demands on top of people's normal jobs

**Formula**: `DICE = D + (2 × I) + (2 × C1) + C2 + E`

Integrity and senior Commitment are double-weighted because BCG's research found them to be the strongest predictors of outcome. Score range is 7 (best case, all 1s) to 28 (worst case, all 4s).

**Zones** (the boundaries deliberately overlap slightly in BCG's original research, reflecting that a borderline score can go either way depending on which factor is driving it):
- **Win**: 7–14 — project has strong fundamentals
- **Worry**: 14–17 — mixed signal, needs active management
- **Woe**: 17–28 — high risk of failure without significant intervention

**The C1/C2 gap is a special signal.** Even if the total score lands in Win territory, a large gap between C1 (senior commitment) and C2 (local commitment) — a "say-do gap," where leadership talks up the project but the people doing the work don't buy in, or vice versa — is independently one of the strongest predictors of trouble. Always check for it regardless of total score.

## Process

### Step 1: Ask the 5 factor questions

Ask the user to rate each factor 1-4 against these anchors. Present all 5 at once if the user seems experienced with DICE, or one at a time if they seem newer to it — use judgment based on how they framed the request. Always show the anchors; don't make the user guess what a "3" means.

**D — Duration** (time between formal reviews/milestones)
1. Reviewed every 2 months or less (or total project is under 2 months)
2. Reviewed every 2–4 months
3. Reviewed every 4–8 months, or review points are informal/inconsistent
4. Reviewed less than every 8 months, or no formal review milestones at all

**I — Integrity** (project team's ability to execute on time)
1. Strong, respected leader; skilled and motivated team; clear roles; capacity to deliver on schedule
2. Generally capable team and leadership, with some gaps in skill, capacity, or role clarity
3. Notable gaps — inexperienced leadership, thin skills, unclear roles, or team stretched across too many priorities
4. No credible leader, significantly under-skilled or under-resourced, or accountability is unclear

**C1 — Senior Commitment** (visible, communicated sponsorship)
1. Leaders visibly and consistently champion the project, explain why it matters, and back it with resources
2. Leaders express support and generally follow through, with occasional gaps
3. Leaders call it a priority but don't consistently act like it — resourcing, attention, or follow-through lags
4. Lip service only — minimal visible sponsorship, resourcing, or follow-through

**C2 — Local Commitment** (the people who must actually change how they work)
1. Enthusiastic, actively supportive
2. Generally receptive, with pockets of hesitation
3. Neutral-to-skeptical, or support is inconsistent across groups
4. Resistant, hostile, or actively working against the change

**E — Effort** (additional workload beyond business-as-usual)
1. Less than ~10% increase in workload for those involved
2. Roughly 10–20% increase
3. Roughly 20–40% increase
4. More than 40% increase, or people are absorbing this on top of an already overloaded plate

Also ask, briefly: is there anything about senior vs. local commitment specifically worth flagging (e.g. "leaders love it, frontline hates it")? This helps catch the say-do gap even before scoring.

**If the user describes the situation in prose instead of giving explicit 1-4 numbers** (e.g. "reviews happen quarterly, the team's stretched thin, execs talk about it but haven't funded it"), don't stall and ask them to translate their own answer into numbers. Infer the most defensible rating per factor from the anchors above, state each inferred rating with a one-line justification tied to what they actually said, and invite them to correct any that seem off before you finalize the score.

### Step 2: Calculate

`DICE = D + (2 × I) + (2 × C1) + C2 + E`

Classify:
| Score | Zone |
|---|---|
| 7–13 | **Win** |
| 14–17 | **Worry** |
| 18–28 | **Woe** |

(Using 14 as the clean Win/Worry cutoff and 17/18 as the clean Worry/Woe cutoff for a single deterministic call — but if the raw score is exactly 14 or exactly 17, treat it as a genuine borderline case and say so explicitly, then use which factors are elevated to break the tie: if I or C1 — the double-weighted factors — are driving the score, lean toward the riskier zone.)

Check the C1/C2 gap: if |C1 − C2| ≥ 2, flag this explicitly as a say-do gap risk regardless of what zone the total score lands in.

### Step 3: Output

Concise and direct — practitioner audience, no framework tutorial unless asked:

1. **DICE score and zone** (e.g. "DICE = 16 → Worry zone", showing the factor breakdown: D=2, I=3, C1=2, C2=3, E=2 → 2+6+4+3+2=17... always show your arithmetic so it's auditable)
2. **What's driving it** — call out the highest-scoring factor(s) specifically, especially I and C1 given their double weight
3. **C1/C2 gap flag** if applicable, even in a Win-zone project
4. **Recommendations** — targeted at the specific worst factor(s), not a generic checklist (see playbook below)

### Step 4: Memo version (only if requested)

If asked for a memo, steering committee summary, or client-ready version, reformat into a short structured memo (headers: DICE Score & Zone / Factor Breakdown / Key Risk Drivers / Recommended Actions). Keep it to roughly a half page or one slide. Use the docx or pptx skill if they want an actual file.

## Recommendation Playbook (target the specific factor driving risk, don't dump all of these)

**If D is high (2-4):** Shorten the interval between formal reviews — even inserting one additional milestone review can materially reduce risk. Long gaps between check-ins let problems compound unseen.

**If I is high (3-4):** This is one of the two most powerful levers. Strengthen the project team directly — add a credible lead if the current one lacks standing, backfill skill gaps, clarify roles and decision rights, or reduce the team's competing priorities so they can actually focus on this.

**If C1 is high (3-4):** The other most powerful lever. Get a specific, visible commitment from the senior sponsor — not just verbal support, but calendar time, resourcing decisions, and them personally communicating why this matters. A sponsor who talks about the project once at kickoff and disappears is a C1=4 in practice even if they meant well.

**If C2 is high (3-4):** Invest in engagement with the people actually doing the work — this usually isn't a communications problem, it's a "have they actually been asked what they think" problem. Participative design, addressing what they stand to lose, and visible quick wins tend to move this faster than more messaging.

**If E is high (3-4):** Reduce the ask — cut scope, extend the timeline, or backfill capacity so people aren't absorbing this on top of an already full plate. Effort overload is one of the fastest ways to quietly kill a project even when everyone supports it in principle.

**If C1/C2 gap flagged:** Don't just average them and move on — get senior sponsors into direct contact with the people affected, rather than routing commitment through layers of communication. The gap itself, not just its average, is the risk.

**By zone:**
- **Win**: Fundamentals are sound. Recommend maintaining review rigor and re-scoring periodically — a Win-zone project can drift into Worry if a factor degrades (e.g. sponsor attention fades) and no one's tracking it.
- **Worry**: Don't try to fix everything at once — identify the single highest-scoring factor and prioritize fixing that first; moving one factor down often does more than spreading effort thin across all five.
- **Woe**: Light-touch fixes won't be enough. Recommend a structural reset — of scope, sponsorship, team, or timeline — or an honest conversation with the sponsor about whether to proceed as currently designed.

## Notes

- Always show the arithmetic (the individual factor scores and how they sum), not just the final number — this needs to be auditable by whoever's reviewing it.
- Don't let a good total score mask a bad individual factor, especially I or C1 given the double weight, or a C1/C2 gap.
- This pairs with the other change diagnostic skills: DICE predicts *whether* a project will succeed given its current setup; Technical/Adaptive diagnoses *what kind* of change it is; Theory E/O diagnoses *why* it's happening. All three can be run on the same initiative for a fuller picture.
