---
name: theory-e-o-change-v1.0
description: Diagnoses what's motivating a change initiative using Beer & Nohria's Theory E (Economic value) vs. Theory O (Organizational capability) framework. Presents a checklist (with an "Others" free-text option) across goals, leadership/decision-making, process/structure, and incentives/consultants, then scores Theory E and Theory O as two independent axes — since they are not mutually exclusive and often run simultaneously — to classify the change as predominantly E, predominantly O, or Combination, with a recommended approach for addressing the diagnosed motivation. Use whenever the user wants to diagnose what's driving a change, restructuring, or transformation — phrases like "is this Theory E or Theory O", "what's motivating this change", "economic vs organizational change", or when scoping a CM engagement and the underlying drivers aren't yet clear. Also trigger for a client-ready memo/slide summarizing this diagnosis.
---

# Theory E vs. Theory O Change Motivation Diagnostic

Diagnoses what's really driving a change initiative using Michael Beer and Nitin Nohria's Theory E / Theory O framework, and translates the diagnosis into a recommended approach for managing that motivation.

## Background (for your own calibration, don't dump this on the user)

- **Theory E (Economic value)**: change is driven by maximizing shareholder/economic value. Hard measures (stock price, ROI, cost savings), top-down decision-making by a small senior group, restructuring/downsizing/M&A as the primary lever, financial incentives, external consultants used to analyze and prescribe.
- **Theory O (Organizational capability)**: change is driven by building long-term organizational capability, culture, and commitment. Soft measures (engagement, learning, capability), participative decision-making, culture/capability-building as the primary lever, non-financial or collective incentives, consultants used to facilitate the organization's own process.
- **Critically, these are not opposite ends of one spectrum — they are two independent axes.** A change initiative can score high on both simultaneously (Beer & Nohria's own recommendation for best-in-class change: use both, sequenced deliberately) or low on both (a change with an unclear or poorly-articulated rationale). Don't force this into a single Technical-vs-Adaptive-style spectrum — score E and O separately.

## Process

### Step 1: Run the checklist

Present the checklist below to the user as selectable items. If in a chat surface, present it as a markdown list they can tick off by number, or ask them to just list which numbers apply. Always include the "Others" free-text line. Don't make the user read the scoring logic — just get their selections.

**Diagnostic Checklist — tick everything that applies to this change**

*Goals & Rationale*
1. Primary goal is maximizing shareholder or economic value *(Theory E)*
2. Success is measured by hard numbers — stock price, ROI, cost savings, margin *(Theory E)*
3. Primary goal is building long-term organizational capability or culture *(Theory O)*
4. Success is measured by soft measures — engagement, commitment, learning, capability *(Theory O)*

*Leadership & Decision-Making*
5. Change is driven top-down by a small senior leadership group *(Theory E)*
6. Decisions are made quickly, with limited broad consultation *(Theory E)*
7. Change is participative — broad employee involvement in shaping it *(Theory O)*
8. Decisions unfold gradually, incorporating feedback from multiple levels *(Theory O)*

*Process & Structure*
9. Change involves restructuring — downsizing, delayering, divestiture, M&A *(Theory E)*
10. Formal structures and systems are changed first; culture is expected to follow *(Theory E)*
11. Change focuses on capability-building — training, teamwork, culture programs *(Theory O)*
12. Culture/mindset shift is the primary lever; structural change is secondary or emergent *(Theory O)*

*Incentives & Consultants*
13. Financial incentives (bonuses, equity, individual performance pay) are a central lever *(Theory E)*
14. External consultants are used mainly to analyze and prescribe the solution *(Theory E)*
15. Incentives, if used, are non-financial or team/values-based rather than individual bonus-driven *(Theory O)*
16. External consultants, if used, mainly facilitate the organization's own process rather than prescribe it *(Theory O)*

*Others* — free text: let the user describe anything not captured above (e.g. a specific mandate, crisis, or trigger behind the change). Read it and classify it yourself as leaning E, O, both, or neither, stating your reasoning in one line when you present the output.

### Step 2: Score — two independent axes, not one spectrum

- **Theory E score** = (ticked E items ÷ 8) × 100%
- **Theory O score** = (ticked O items ÷ 8) × 100%

Fold "Others" entries in by severity/relevance, not as a flat +1 — a single entry describing a strong, explicit driver (e.g. "the board mandated 20% cost reduction in 90 days" or "this came out of an employee engagement crisis") can weight as heavily as 2-3 checklist ticks on the relevant axis.

Classify using both scores together:

| E score | O score | Classification |
|---|---|---|
| ≥50% | ≥50% | **Combination** — both drivers present, run deliberately together |
| ≥50% | <50% | **Predominantly Theory E** |
| <50% | ≥50% | **Predominantly Theory O** |
| <50% | <50% | **Underdetermined** — thin or unclear signal on both axes |

**Thin signal:** if total ticks are low (under ~4), don't stop and ask for more if the signal is otherwise clean and one-sided — commit to a call and flag the sample size in one line. Only ask for more if the answers are themselves contradictory or genuinely too sparse to say anything (e.g. 0-1 total ticks).

### Step 3: Output

Concise, direct — this is for a change management practitioner, skip framework explainers unless asked:

1. **Classification** with both scores (e.g. "E: 75% (6/8) | O: 38% (3/8) → Predominantly Theory E")
2. **Rationale** — 2-4 bullets max, citing the specific findings that drove the call. Never present a bare item number on its own ("item 3", "E:1,2,5") — always pair the number with what it actually found, in plain language specific to this initiative, e.g. "(item 9) this involved real restructuring — downsizing/delayering — not just a capability program." The number gives traceability back to the framework; the plain-language content is what makes it readable. Always format this as a numbered or bulleted list, one finding per line — never run several findings together in a single prose paragraph.
3. **Recommended approach** — pull from the playbook below, tailored to what was actually ticked

### Step 4: Memo version (only if requested)

If asked for a memo, slide snippet, or client-ready version, reformat Step 3 into a short structured memo (headers: Diagnosis / Rationale / Recommended Approach / Key Risks). Keep it to roughly a half page or one slide. Use the docx or pptx skill if they want an actual file; otherwise a clean markdown block in chat is enough.

## Recommended Approach Playbook

**If Predominantly Theory E:**
- Name the risk explicitly: economic gains from restructuring/cost-cutting tend to erode if commitment and capability aren't built alongside them — the classic pattern is a good year-one financial result followed by attrition, disengagement, and the gains not sticking.
- Layer in O-style interventions without abandoning the E discipline: participative forums to shape *how* the economic targets get hit (not *whether* they get hit), capability-building for the roles that survive restructuring, and team/collective incentive components alongside individual ones.
- Invest specifically in trust-rebuilding if restructuring already happened — this is usually the biggest gap in E-led change.
- Keep leadership accountable to the hard numbers; don't dilute the economic case, just don't let it be the *only* lever.

**If Predominantly Theory O:**
- Name the risk explicitly: capability/culture-building without clear economic targets or accountability can stall, lose executive sponsorship, or fail to demonstrate ROI — it needs a business case, not just a values case.
- Layer in E-style discipline: define hard success metrics and milestones, tie some portion of leadership accountability to measurable outcomes, and sequence the work so early wins are visible and defensible in economic terms.
- Make sure there's a senior sponsor who can translate the capability-building work into terms the board/leadership will fund and protect.

**If Combination (both high):**
- This is what Beer & Nohria consider the strongest approach, but it's also the hardest to execute — the tension between the two needs to be *managed*, not ignored.
- Sequence deliberately: set direction and hard economic targets top-down early (E), then shift into participative process to build the capability and commitment needed to hit them (O) — don't try to run both simultaneously without an explicit plan for how they interact.
- Watch for E actions undermining O trust (e.g. a round of layoffs happening mid-way through a participative culture program) — this is the most common failure mode in combination approaches, and it needs to be actively managed and communicated, not assumed away.
- Consider splitting accountability: leadership/finance own the economic track, HR/OD or change management owns the capability track, with a clear integration point where the two are reconciled (e.g. steering committee, joint milestones).

**If Underdetermined:**
- Flag this plainly rather than forcing a confident-sounding call — a change initiative without a clearly articulated economic or organizational rationale is itself a risk (people won't know what they're being asked to commit to, or why).
- Recommend clarifying the actual mandate with the sponsor before designing the CM approach — ask what specifically triggered this change and what "success" looks like to them, since that answer usually reveals which theory (or both) is actually in play.

## Notes

- E and O are independent axes — always report both scores, never collapse into a single number.
- Don't let the user's own framing override what their checklist actually shows (e.g., a change framed as "cultural transformation" that scores 75% Theory E on the actual checklist is worth flagging back to them — that mismatch is often the most useful insight).
- This pairs naturally with the Technical vs. Adaptive Change skill — Theory E/O diagnoses *why* the change is happening; Technical/Adaptive diagnoses *what kind* of change it is. Both lenses can be run on the same initiative.
