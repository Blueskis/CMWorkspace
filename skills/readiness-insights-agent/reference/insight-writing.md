# Writing the insights

Stage 4 is the only stage a script cannot do. Everything else in this skill exists to make
this stage checkable; none of it makes it good. This file is the standard.

## What counts as an insight

Four parts, in this order. Missing any one of them and it is not an insight yet:

1. **The finding, with its number in it.** Not "capacity is a concern" — "Field Ops
   capacity sits at 25/100, the lowest cell in the matrix, and fell 9.8 points between
   waves."
2. **So what for the programme.** The consequence, not a restatement. If the *so what*
   could be pasted under any other finding, it is filler.
3. **The action.** Something a named role could start on Monday, specific enough that
   someone could refuse it.
4. **The date it is up against.** Which milestone, how long the action takes, whether
   that fits.

## The tests to apply before writing one down

**Would a different number change the recommendation?** If the action is the same whether
the score is 40 or 70, the score is decoration and the recommendation is a pre-existing
opinion.

**Is this the finding, or the first thing the data shows?** The first read is usually the
lowest score. The finding is more often a relationship: skills up while confidence flat,
awareness high while understanding low, one segment moving against every other, a score
that recovered because the unhappiest people stopped responding.

**Who does this belong to?** A capacity finding sent to the training team is a finding
nobody can act on. Map the recommendation to the function that owns the lever — operations
owns rota cover, the programme owns comms design, the sponsor owns anything requiring a
trade-off between deliverables.

**What would have to be true for this to be wrong?** Write the counter-signal down. A
theme with no counter-signal recorded is usually one nobody looked for.

## Confidence, stated honestly

`low` is a legitimate and useful answer. It does not mean drop the finding — it means state
it as a question and say what would answer it. "Comms feedback suggests X, on a 16%
response rate; a rota-time pulse before the gate would confirm or kill it" is more useful
to a sponsor than either silence or false certainty.

Stage 5 forces `low` where an insight rests only on a thin cell or only on sources below
the response-rate floor. Do not route around the check by adding an unrelated citation to
an insight so it clears — the citation list is the evidence the claim rests on, not a
padding field.

## Anchoring to the timeline

Anchor to **the milestone the finding actually bears on**, which is usually not go-live.
A training design problem bears on the next training wave. A superuser problem bears on the
date the network is meant to stand up. Anchoring everything to go-live makes every finding
look equally distant and destroys the ordering the brief is built on.

`remediation_lead_time_days` is the honest elapsed time the action needs, including the
decisions in front of it. Renegotiating rota cover is not a two-day task because the email
takes two days; it is a four-week task because it needs an operations director, a cost, and
a schedule change. Estimating this short to avoid a `too_late` verdict is the one failure
mode that makes this whole skill worse than useless — it converts an early warning into a
missed deadline.

When the verdict is `too_late`, write the insight as a decision, not an action: what is
being descoped, delayed, or accepted, and who decides. Say it plainly and say it early;
four weeks of notice on an unfixable problem is worth more than an action item nobody can
complete.

## Themes

A theme is a claim about what people said, so it needs the quotes that make it true.

- **Two quotes minimum**, and Stage 5 enforces it. One person's complaint is an anecdote —
  which can still be worth reporting, but as an anecdote, inside an insight, not as a
  theme.
- **Prevalence is counted, not estimated**, and against a stated denominator: "14 of 62
  verbatims (23%)". "Many respondents" is not a finding.
- **Label in the respondents' language.** "No cover to attend training and run the route"
  beats "capacity constraints impacting learning uptake" — the first is quotable at a
  steerco and the second is consultant register that hides who has to fix it.
- **Frequency is not importance.** A single verbatim saying the dry run failed twice
  outranks eleven saying the room was cold. Weight by consequence against the timeline.

## What not to do

**Do not average across segments to get a headline number.** "Overall readiness is 61%" is
the least useful sentence in change reporting: it hides the only thing that matters, which
is that one group is fine and another is not. Lead with the spread.

**Do not read a delta from a base that moved.** If wave 1 was 58 responses and wave 2 was
71 different people, the delta includes who turned up. Say so where it matters.

**Do not treat silence as agreement.** A segment that returned nothing is a blind spot, and
it goes in the brief as one. The most consequential finding in a readiness run is often
about the group nobody managed to ask.

**Do not soften a finding into a recommendation nobody can refuse.** "Continue to monitor
capacity" is what an insight decays into when nobody wanted to own it.
