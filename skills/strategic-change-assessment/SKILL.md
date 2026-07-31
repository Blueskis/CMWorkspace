---
name: strategic-change-assessment-v1.0
description: Runs a consultant's change-initiative narrative through whichever of the project's 12 Strategic Change framework skills are suitable (DICE, Technical vs. Adaptive, Theory E/O, Kotter's 8-Step, Persuasion, Tipping Point, Immunity to Change, Six Steps, Productive Distress, Critical Few Behaviours, Dual Operating System, Network Position). Gathers one narrative up front, auto-selects which frameworks apply (or honors an explicit list from the consultant), chains them so later frameworks build on earlier findings, and closes with a cross-framework synthesis of convergent findings and one prioritized recommendation. Use whenever a consultant wants a broad, multi-lens assessment of a change initiative — "assess this project", "give me a full change readiness read", "what's going on with this initiative", "run this through your frameworks", "is this project healthy", or a project description naming no single framework. If a specific framework is named, invoke that skill directly instead.
---

# Strategic Change Assessment — Multi-Framework Orchestrator

Takes one comprehensive account of a change initiative from a consultant, works out which of the project's 12 framework skills actually have something to say about it, runs them in a sensible order so later frameworks build on what earlier ones found, and closes with a synthesis that connects the dots across frameworks rather than just listing 12 separate reports back to back.

This skill doesn't reimplement any framework's diagnostic logic — it orchestrates the other 12 skills in this project by invoking them via the Skill tool in sequence. Each framework skill remains the single source of truth for its own diagnostic process.

## Background (for your own calibration, don't dump this on the user)

The 12 available framework skills, with the suitability signal that makes each one worth running:

| Skill | Run it when the narrative shows... |
|---|---|
| `dice-framework-v1.0` | Anything about review cadence, sponsorship, team capability, workload/effort, or a general "will this succeed" question |
| `technical-adaptive-change-v1.0` | Ambiguity about what *kind* of change this is — a system/process change, a values/identity change, or both |
| `theory-e-o-change-v1.0` | A question about *why* the change is happening — economic/compliance driver vs. capability/culture driver, especially with restructuring in the picture |
| `kotter-8-step-v1.0` | A need for a broad "where are we in the change process" maturity read across urgency through institutionalization |
| `persuasion-case-for-change-v1.0` | Concerns about whether the case for change is landing, buy-in, or the comms/narrative around the change |
| `tipping-point-v1.0` | A change with some early traction that isn't spreading into the broader population — a "why hasn't this caught on" situation |
| `immunity-to-change-v1.0` | A specific named person or persona who genuinely wants the change to succeed but isn't changing their behavior |
| `six-steps-change-v1.0` | Concern that formal rollout/spread is proceeding ahead of genuine groundwork — "does this look done on paper but not in practice" |
| `productive-distress-v1.0` | Signals of too much or too little pressure — overwhelm, avoidance, checkbox compliance, or flat complacency |
| `critical-few-behaviours-v1.0` | A need to identify or reinforce specific behaviors the change depends on |
| `dual-operating-system-v1.0` | Concern about day-to-day work being crowded out by change work, or questions about a change-agent network vs. the hierarchy |
| `network-position-v1.0` | A need to identify or prioritize *which specific people* to engage to sustain the change |

**A rich narrative will often trigger many of these at once — that's normal, not a sign of over-triggering.** These frameworks answer genuinely different questions (whether it'll succeed, what kind of change it is, why it's happening, how far it's progressed, where to focus energy, who's stuck, who to engage), so real project narratives legitimately have something to say to most of them. The triage in Step 2 is about excluding what's clearly *not* applicable, not about narrowing down to just one or two.

**Default run order** roughly follows the deck's own phase structure, since later-phase frameworks benefit from earlier diagnostic groundwork: **Assess** (technical-adaptive-change, theory-e-o-change, kotter-8-step, dice-framework) → **Build** (persuasion-case-for-change, tipping-point, immunity-to-change) → **Conduct** (six-steps-change, productive-distress, critical-few-behaviours, dual-operating-system) → **Sustain** (network-position). Use this ordering unless the consultant's explicit request implies a different one.

## Process

### Step 1: Gather one comprehensive narrative

Ask the consultant to describe the project/change initiative in whatever depth they have — background, timeline, stakeholders, pain points, current state, anything that feels relevant. Also make clear they can instead name specific frameworks or a specific question if they already know what they want, in which case skip straight to Step 3 with their explicit list rather than triaging.

If they give a thin narrative, don't stall waiting for more — proceed with what's given; each individual framework skill already knows how to ask its own genuine follow-up questions where it has real gaps.

### Step 2: Triage — select which frameworks are suitable

Using the signals table above, decide which frameworks the narrative gives genuine grounds to run. **This is your call to make, not a menu for the consultant to pick from** — don't turn this into another round of questions. The only exception is if the consultant explicitly named specific frameworks or a specific question in Step 1; if so, honor that list directly instead of running your own triage.

Present the selected list briefly before running anything — one line per selected framework naming *why* it's suitable (tying back to something specific in the narrative), plus a one-line note on anything clearly not suitable and why it's being skipped. This is a transparency checkpoint, not a request for approval — proceed into Step 3 right after, unless the consultant redirects.

### Step 3: Chain through the selected skills in order

Run the selected frameworks in the default phase order (or the order implied by an explicit consultant request). For each one:

1. Invoke it via the Skill tool using its versioned name (e.g. `dice-framework-v1.0`).
2. When working through that skill's own Step 1 intake, use the master narrative from Step 1 — plus everything surfaced by frameworks already run earlier in this chain — as the starting input, extracting what you can exactly as each skill's own narrative-intake instructions describe. Only ask the consultant a genuine follow-up question if something that specific framework needs still isn't covered by anything said so far.
3. After each framework's output, note its 2-3 most important findings in a short running list — this is what "builds on earlier findings" means in practice: a later framework's diagnosis should visibly draw on what an earlier one already established (the way, across this project's own testing, a DICE Effort score used the same overload finding productive-distress had already surfaced), not treat each framework as if it's seeing the situation for the first time.

Don't ask the consultant to confirm before moving from one framework to the next — keep the chain moving, and only pause for a framework's own genuine follow-up questions when it has them.

### Step 4: Cross-framework synthesis

Once every selected framework has run, close with a synthesis — this is the actual value of running the orchestrator instead of each skill separately:

1. **Findings by framework** — one or two lines each, in the order run
2. **Convergent findings** — name anything two or more frameworks independently pointed at (e.g. an effort/capacity problem showing up in DICE, productive-distress, and six-steps all at once). Convergent findings are the highest-confidence signal available here, since independent frameworks arriving at the same root cause is much stronger evidence than any single framework's read alone.
3. **Tensions or contradictions**, if any — where two frameworks' reads sit in real tension (e.g. one framework reading a factor as strong that another reads as a live risk) — don't paper over this, name it and give your best read on how to hold both
4. **One prioritized recommendation** — not a combined checklist of every framework's individual recommendation, but the single highest-leverage thing to address first, reasoned from the convergent findings specifically

### Step 5: Memo / deck version (only if requested)

If asked for a memo, steering committee summary, or client-ready version, reformat the synthesis into a short structured document (headers: Frameworks Assessed / Key Findings / Convergent Risks / Recommended Priority). Use the docx or pptx skill if they want an actual file.

## Notes

- Resist the urge to run all 12 by default "to be thorough" — an unsuitable framework run anyway produces noise (forced, thin findings) that dilutes the real convergent signal from the frameworks that actually apply.
- The synthesis step is the reason this skill exists rather than the consultant just invoking frameworks one at a time — if you skip straight to listing each framework's output with no synthesis, you haven't actually added anything beyond what running them individually would have given.
- If the consultant only ever wants one specific lens, this orchestrator is the wrong tool — point them to that framework's own skill directly rather than running the full triage-and-chain process for a single-framework question.
