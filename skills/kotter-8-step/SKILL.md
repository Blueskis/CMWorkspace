---
name: kotter-8-step-v1.0
description: Diagnoses a change initiative's maturity against Kotter's 8-Step Change Model (urgency, coalition, vision, buy-in, removing barriers, short-term wins, sustaining momentum, institutionalizing change). Analyzes whatever project context or documents the consultant provides, assesses each step as Not Started / In Progress / Solid, and only asks follow-ups for steps the input doesn't cover — producing a stage-by-stage diagnostic with evidence, gaps, next actions, and an overall risk synthesis. Use whenever the user wants to assess change readiness or maturity against Kotter's model — phrases like "Kotter diagnostic", "8-step change model", "are we ready to institute this change", "did we build enough of a coalition", or when it's unclear which step an initiative is at. Also trigger for a client-ready memo or steering committee summary.
---

# Kotter's 8-Step Change Model — Change Initiative Diagnostic

Diagnoses how far a change initiative has actually progressed through Kotter's 8-Step model (Kotter, "Leading Change" / "Leading Change, With a New Preface"), using whatever project context the consultant provides. Produces a step-by-step maturity read — not a score — because Kotter's model is sequential and qualitative: the real risk almost always comes from a specific weak or skipped step, not from an aggregate number.

## Background (for your own calibration, don't dump this on the user)

The 8 steps, in Kotter's intended order:

1. **Create a sense of urgency** — get people to genuinely believe the status quo is more dangerous than the change
2. **Build a guiding coalition** — assemble a group with enough shared commitment, credibility, and cross-functional power to actually lead the effort
3. **Form a strategic vision and initiatives** — a vision clear enough to guide decisions and simple enough to explain in under a minute
4. **Enlist a volunteer army** — communicate the vision so broadly and repeatedly that people opt in, rather than merely comply
5. **Enable action by removing barriers** — clear out structural obstacles: bad processes, unhelpful org structures, or managers who undercut the change
6. **Generate short-term wins** — deliberately plan and deliver visible, unambiguous wins early, not just wait for them to happen
7. **Sustain acceleration** — keep urgency and momentum through wave after wave of change instead of declaring victory after the first win
8. **Institute change** — anchor new behaviors in culture, systems, and succession so they outlive the people who drove the change

**Order matters.** Kotter's central finding is that most change efforts fail not because any single step was done badly, but because steps were skipped, rushed, or run out of sequence — most commonly, declaring victory after step 6 and never doing 7 or 8, or jumping to vision (step 3) before urgency (step 1) or coalition (step 2) were real. A "solid" step 6 sitting on top of a weak step 2 is fragile, not strong — flag that even if step 6 itself looks great.

**Kotter's classic failure mode per step** (use this to help spot gaps in the input, and as the basis for recommendations):
1. Allowing too much complacency; leaders underestimate how hard it is to move people out of their comfort zone
2. A coalition led by one person, or lacking the credibility/authority/information to act
3. No clear vision, or a vision too complicated to explain quickly
4. Under-communicating the vision by an order of magnitude — one email or town hall does not count
5. Leaving structural barriers in place: rigid job categories, compensation/performance systems, or a manager who actively resists
6. Leaving wins to chance instead of actively planning and engineering them early
7. Declaring victory too soon and letting urgency drain away before the change is actually anchored
8. Failing to explicitly connect new behaviors to success, or to embed them in hiring, promotion, and succession — so they erode once the original champions leave

## Process

### Step 1: Assess from the provided input first

Read whatever the consultant pastes in — project documents, status updates, notes, transcripts, whatever. For each of the 8 steps, try to determine:
- **Status**: Not Started / In Progress / Solid
- **Evidence**: what in the input actually supports that status (quote or closely paraphrase it)

Don't force the consultant through 8 questions if the input already speaks to a step. Most real project context will clearly cover some steps (e.g. there's obviously a vision document, or obviously no coalition has been named) and leave others ambiguous.

### Step 2: Ask targeted follow-ups only for genuine gaps

For any step where the input is silent or ambiguous, ask one specific, concrete question — not "tell me about step 3." E.g.: "Who's actually on the guiding coalition, and do they have real authority to reallocate resources or override a resistant manager?" or "Has a short-term win been deliberately planned, or are you hoping one happens?" If, after asking, a step still can't be assessed, say so explicitly in the output rather than guessing — mark it "Insufficient information" instead of forcing a status.

**Group the batched questions thematically, not as a flat numbered list.** Adjacent steps in Kotter's sequence cluster naturally — foundation (urgency + coalition), direction and buy-in (vision + volunteer army), and momentum (short-term wins + institutionalization) — and asking about them in those clusters, with one combined question per cluster, reads as a coherent conversation rather than an interrogation. Only include the clusters that actually have gaps; skip any cluster the input already covered.

### Step 3: Produce the stage-by-stage diagnostic

Present this as a markdown table — it's much easier to scan than eight separate write-ups. Columns: **Step | Status | Evidence | Gaps/Risks | Recommended Next Action**. One row per step, in order 1-8.

- **Status** — Not Started / In Progress / Solid (or Insufficient information)
- **Evidence** — what from the input (or the consultant's answers) supports this
- **Gaps / risks** — tied to Kotter's classic failure mode for that step where relevant
- **Recommended next action** — concrete and specific to this initiative, not generic advice (use "*(pending)*" here for any row still marked Insufficient information)

### Step 4: Overall synthesis

After the 8-step walkthrough, add a short synthesis:
- Which step is the **biggest current risk** to the change effort, and why (weight earlier steps heavily — a weak step 1 or 2 undermines everything built on top of it, even if later steps look solid)
- Whether steps are being attempted **out of order** (e.g. vision work happening before real urgency or coalition exist) — flag this explicitly, it's one of the most common and costly patterns
- One clear recommendation for what to prioritize next, not a full checklist

### Step 5: Memo version (only if requested)

If asked for a memo, steering committee summary, or client-ready version, reformat into a short structured memo (headers: Current State by Step / Biggest Risk / Sequencing Flags / Recommended Next Action). Keep it to roughly a half page to one slide. Use the docx or pptx skill if they want an actual file.

## Notes

- Resist the urge to force a numeric score onto this — Kotter's model is about sequence and completeness, not an aggregate. Two initiatives with "5 of 8 steps solid" can be in very different danger depending on *which* 5.
- A step marked Solid is only meaningful if the steps before it are also at least In Progress — say so if you see a later step outpacing an earlier one.
- This pairs with the other change diagnostic skills in this project: DICE predicts *whether* a project will succeed given its current setup; Technical/Adaptive diagnoses *what kind* of change it is; Theory E/O diagnoses *why* it's happening; Persuasion helps *build the case* that gets people on board; Six Steps diagnoses *how far the change has genuinely progressed* using a closely related sequential-bottleneck logic. This Kotter diagnostic overlaps most with Six Steps — both assess *how far through the change process* the initiative actually is and flag out-of-sequence risk — but Kotter's 8 steps and Six Steps' 6 steps carve up that same territory differently, so running both can surface different specific gaps. All can be run on the same initiative for a fuller picture.
