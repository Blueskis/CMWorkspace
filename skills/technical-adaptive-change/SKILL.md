---
name: technical-adaptive-change-v1.0
description: Classifies a change initiative as Technical, Adaptive, or a Hybrid/spectrum between the two, using Heifetz's Technical vs. Adaptive Change framework. Presents a checklist of diagnostic indicators (with an "Others" free-text option) across problem definition, solution ownership, nature of change, stakeholder loss, and implementation mechanism, then scores the selections to produce a classification with rationale and recommended change management approach. Use this skill whenever the user wants to diagnose, categorize, or assess a change initiative, project, or client situation as technical vs. adaptive — including phrases like "is this technical or adaptive", "diagnose this change", "what kind of change is this", or when scoping a new change management engagement and the CM approach isn't yet decided. Also trigger when the user asks for a client-ready memo or slide summarizing this diagnosis.
---

# Technical vs. Adaptive Change Classifier

Diagnoses a change initiative using Ronald Heifetz's Technical vs. Adaptive Change framework, and translates the diagnosis into a recommended change management approach.

## Background (for your own calibration, don't dump this on the user)

- **Technical problems**: the problem is clearly defined, an expert or existing playbook has the answer, and people mostly need training/communication/logistics to adopt it. Authority can just direct the fix.
- **Adaptive problems**: the problem itself is contested or not fully understood, no existing expertise fully solves it, and the people with the problem have to change their own beliefs, habits, loyalties, or ways of working to close the gap. Authority alone can't mandate this — it requires learning, and it usually involves real or perceived loss.
- Most real change initiatives are **hybrids**: a technical core (new system, new process) wrapped in an adaptive shell (new ways of working, new identity, resistance rooted in loss). The diagnosis is about where on that spectrum the initiative sits, and which parts are technical vs. adaptive.

## Process

### Step 1: Run the checklist

Present the checklist below to the user as selectable items (checkboxes). If you're in a chat surface, present it directly as a markdown checklist the user can copy/tick off in their reply, or ask them to just list which numbers apply. Always include the "Others" free-text line.

Don't make the user read the scoring logic — just get their selections.

**Diagnostic Checklist — tick everything that applies to this change**

*Problem Definition*
1. The problem and its root cause are already well understood *(Technical)*
2. There's a known best-practice, precedent, or vendor solution to follow *(Technical)*
3. Different stakeholders define the problem differently, or disagree it's even a problem *(Adaptive)*
4. We don't yet know what's really driving the gap or resistance *(Adaptive)*

*Solution & Expertise*
5. A subject matter expert, vendor, or existing SOP can prescribe the fix *(Technical)*
6. The solution can be fully specified in a manual, system config, or process map *(Technical)*
7. The solution requires stakeholders to build new beliefs, judgment, or skill over time — not just follow a new step *(Adaptive)*
8. No single expert has "the answer" — it will have to emerge through trial, dialogue, and iteration *(Adaptive)*

*Nature of the Change*
9. Change is primarily to a tool, process, or system *(Technical)*
10. People's day-to-day tasks change, but their role and identity stay basically the same *(Technical)*
11. Change requires shifting values, mindsets, or "the way we've always done things" *(Adaptive)*
12. Change touches people's sense of competence, status, or professional identity *(Adaptive)*

*Stakeholder Impact & Loss*
13. Stakeholders are largely willing and just need training/awareness *(Technical)*
14. Resistance, where it exists, is mostly logistical (time, capacity, scheduling) *(Technical)*
15. There's real or perceived loss involved — power, relationships, autonomy, identity *(Adaptive)*
16. Resistance is emotional or political, not just a knowledge gap *(Adaptive)*

*Implementation Mechanism*
17. Can be rolled out via a project plan, training schedule, and go-live/cutover checklist *(Technical)*
18. Success depends on visible leadership modeling the new behavior over time, not just announcing it *(Adaptive)*
19. Requires an ongoing sponsor coalition and iterative experimentation, not a single rollout event *(Adaptive)*

*Others* — free text: let the user describe anything not captured above. Read their description and classify it yourself as leaning Technical or Adaptive (or note if it's genuinely ambiguous), stating your reasoning in one line when you present the final output.

### Step 2: Score

Count total Technical (T) ticks and Adaptive (A) ticks. Classify using this spectrum:

| A as % of (T+A) | Classification |
|---|---|
| 0–15% | **Technical** |
| 16–35% | **Technical-leaning Hybrid** |
| 36–64% | **Balanced Hybrid** |
| 65–84% | **Adaptive-leaning Hybrid** |
| 85–100% | **Adaptive** |

**"Others" entries don't count as one tick.** A single free-text entry can describe a severe signal (e.g. identity threat, political resistance, loss of authority) that outweighs several checkbox ticks combined. Read each "Others" entry and weight it by severity, not frequency — a severe one can count as 2-3 ticks' worth, or even single-handedly move a mostly-technical case into Hybrid territory. State explicitly how you weighted it and why when you present the output, so the user can override your judgment if they disagree.

**Thin signal (under ~5 total ticks):** don't stop and ask for more — that's friction the user doesn't need, especially if the ticks are one-sided with no contradicting signal. Commit to a classification, but flag in one line that the signal is thin (e.g. "low tick count, but clean and one-sided — confidence is decent despite the small sample"). Only ask the user to add more if the few ticks they gave are themselves contradictory or ambiguous.

### Step 3: Output

Give a concise, direct output (this is for a change management practitioner, not a first-timer — skip framework explainers unless asked):

1. **Classification** (from the table above) with the T/A tick count (e.g. "4T / 11A → Adaptive-leaning Hybrid")
2. **Rationale** — 2-4 bullets max, citing the specific findings that drove the call, not a generic restatement. **Never present a bare item number on its own ("item 3", "T:1,2,5") — always pair the number with what it actually found, in plain language specific to this initiative**, e.g. "(item 3) leadership feels real urgency from the 2027 deadline, but that urgency hasn't reached the frontline." The number gives traceability back to the framework; the plain-language content is what makes it readable. Always format this as a numbered or bulleted list, one finding per line — never run several findings together in a single prose paragraph.
3. **Recommended CM approach** — pull from the playbook below, tailored to the specific findings, described in plain language — not a generic dump of the whole playbook
4. If it's a Hybrid: explicitly name which parts of the initiative are the technical core vs. the adaptive shell, since they usually need different treatment run in parallel, not sequenced as one plan

### Step 4: Memo version (only if requested)

If the user asks for a memo, slide snippet, or client-ready version, reformat Step 3's output into a short structured memo (headers: Diagnosis / Rationale / Recommended Approach / Key Risks). Keep it to something that fits on one slide or half a page — this is a diagnostic summary, not a full change strategy document. Use the docx or pptx skill if they want it as an actual file; otherwise a clean markdown block in chat is enough.

## CM Approach Playbook

**If mostly Technical:**
- Standard ADKAR-style rollout: awareness → desire → knowledge → ability → reinforcement, but weighted toward Knowledge/Ability
- Structured training, job aids, quick-reference guides
- Clear go-live/cutover plan with defined success metrics (adoption %, error rates, ticket volume)
- Comms focus: "what's changing and how to do it," not "why this matters to who you are"
- Feedback loop = help desk / super-user network for logistics issues

**If mostly Adaptive:**
- Sustained, visible sponsor coalition — not a single kickoff announcement
- Create structured space (workshops, listening sessions) to surface what people stand to lose, before pushing solutions
- Facilitation and coaching over training — the answer isn't yours to hand down
- Phased pilots / iterative experimentation rather than big-bang rollout
- Leadership must visibly model the new behavior, not just endorse it
- Measure sentiment and behavior change, not just usage/adoption metrics
- Expect a longer sustainment period; resistance will resurface and needs to be worked through, not just messaged past

**If Hybrid:**
- Split the workstream explicitly: run the technical core on a standard project/training track, and run a parallel adaptive track (sponsorship, engagement, loss-processing) for the people component
- Sequence matters less than most people assume — the adaptive track usually needs to *start* alongside or before the technical track, not after go-live when resistance shows up
- Name the loss explicitly in comms rather than only selling benefits — this is the most common miss in initiatives that get misdiagnosed as purely technical

## Notes

- This is a diagnostic tool, not a certainty machine. Where the signal is mixed or thin, say so plainly rather than forcing a confident-sounding classification.
- Don't let the user's own framing of the initiative (e.g., "it's just a system change") override what their checklist answers actually show — that mismatch is itself often the most useful thing to flag back to them.
