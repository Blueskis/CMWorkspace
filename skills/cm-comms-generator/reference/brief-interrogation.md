# Brief Interrogation Guide

How to turn a practitioner's prose brief (or the Change Comms Console handoff) into
`change_brief.json`. Read this in Stage 1.

## Why "interrogation," not "extraction"

`cm-proposal-generator`'s RFP extraction guide is about finding requirements a formal
document already states, in five predictable places. A change brief is usually different:
it's prose a practitioner typed in ten minutes between meetings, and it is reliably
**incomplete in the same handful of ways every time.** Interrogating it means actively
checking for the fields practitioners habitually skip, not just parsing what's there.

## What to pull out

### Org and sender
The organisation or team the change is happening in, and who the communications are sent
as. **Sender is not optional and not generic.** "The Programme Team" gets emails deleted
unread; a name the audience recognises as authoritative for this specific change gets them
opened. If the brief doesn't name a sender, this is the first thing to ask for — don't
default to a generic sender to keep moving.

### Audiences (`A1..`)
Every distinct group the change lands on differently. A brief that says "we're
communicating to the organisation" has, in practice, at minimum two audiences the moment
there's a manager layer: the general population and the managers who need to hear it
first and be equipped to answer for it (see `reference/channel-library.md`'s
`briefing_deck` section).

Assign an audience its own ID only if `what_is_different` is genuinely different from
every other audience already recorded — segmenting for its own sake produces channel
runs with nothing distinct to say. Roughly how many (`size`) is worth capturing even as an
approximate figure; don't force false precision, but don't drop the number either — it's
what later makes "2,400 employees" in a banner traceable back to the brief.

### Messages (`M1..`)
The six mandatory questions, checked one by one, because a prose brief answers some and
silently drops others:

1. **What** is changing.
2. **Who** it affects — feeds audience segmentation as much as messages.
3. **Why** — the case for change. Briefs are often strong here; it's usually the first
   thing a practitioner writes.
4. **When** — feeds the timeline (`T1..`) directly.
5. **Action** — what the audience needs to do, if anything.
6. **Help** — where to go with a question. **This is the single most-omitted field.**
   Practitioners writing quickly assume "obviously they'd ask their manager" or "obviously
   there's a help desk" without ever writing it down. If the brief doesn't name a specific
   place to get help — a person, an inbox, a portal — that's an `open_questions` entry,
   not an assumption to fill in silently.

Two more message kinds the six-question frame misses entirely, both worth asking for
directly rather than waiting for them to appear:

- **What is explicitly *not* changing.** Almost every brief under-states this. Audiences
  fill an unstated scope boundary with their own worst assumption, and a sentence like
  "your reporting line does not change" often does more to lower anxiety than anything in
  the "why."
- **Open unknowns the audience will ask about regardless.** If the brief itself doesn't
  know the answer yet (a common one: "exact go-live date TBC"), record it as a message
  with `kind: "unknown"` and `mandatory: false` — it still needs to be *acknowledged* in
  the pack ("we don't have this date yet, here's when we will") even though it can't be
  answered yet. Silence on a known unknown reads worse than an honest "not yet decided."

### Timeline events (`T1..`)
Every date the change touches: go-live, cutover windows, training slots, the last day the
old process is available, review or feedback windows. Practitioners bury these in prose
("some time in the autumn, probably around the 15th") — pull out an actual date only if
one is genuinely given; a vague window becomes `open_questions`, not a fabricated ISO date.

**`confirmed: false` is not a reason to omit a date.** A provisional go-live date is often
exactly what the audience most wants to know, and marking it clearly unconfirmed (in the
brief and, downstream, on every channel that states it) is safer than either omitting it
or presenting it as settled. This is also the field Stage 5's cross-channel consistency
check leans on hardest: an unconfirmed date that drifts between channels is a much more
common real failure than a confirmed one.

## Assigning IDs

Assign in this order, because each layer keys off the one before it:

1. **Audiences first.** Nothing else can be scoped without them.
2. **Messages next**, tagging `audience_ids` where a message applies to a subset (most
   apply to all — leave `audience_ids` empty rather than listing every audience by hand).
3. **Timeline events last**, tagging `audience_ids` the same way where a date only matters
   to some audiences (a training slot that only affects one region, for instance).

IDs are stable once assigned — a run's `comms_plan.json` and later `qa_report.md` both
reference them, and renumbering mid-run breaks the trail the same way renaming a knowledge
bank entry ID breaks `cm-proposal-generator`'s provenance trail.

## The rule that matters most: an unanswered question is an `open_question`, never a guess

This is the comms-brief equivalent of `cm-proposal-generator`'s "never invent a
requirement" rule, and it's stricter here because the audience reads comms as
authoritative in a way they don't read a bid document. Three situations, three different
outcomes:

- **The brief states it.** Use it, verbatim where precision matters (a date, a figure, a
  system name).
- **The brief implies it but doesn't state it.** Record it with a note on what's implied
  and why, and raise it in the Stage 1 read-back rather than resolving it silently — the
  practitioner may know the real answer in five seconds, or may need to go find out.
- **The brief is silent and there's no reasonable inference.** This is an
  `open_questions` entry. It flows through Stage 2 as a channel run that can't be
  finalised, through Stage 3 as a `gap: true` block, and into the delivered pack as a
  visible `[GAP]` — never as a plausible-sounding sentence that papers over the silence.

The "where to get help" field is the one this rule gets tested on most often in practice,
because it's the field practitioners are most likely to assume rather than state. Treat
every brief as silent on it until it's explicitly named.

## Reading the console handoff specifically

When the input is the Change Comms Console's handoff text (artifact `aa44b762`), it
already carries audience names and rough sizes from its Step 02 segmentation and a set of
detected message fragments from its coverage-question scoring. Treat those as a strong
starting point for `A1..` and `M1..`, not as the finished arrays — the console's own
coverage check is a writing prompt against raw brief text, not an audit of drafted
content (see `SKILL.md` Stage 5's note on this distinction). Re-run the six-question and
audience checks above against the handoff's source prose as if it were any other brief;
don't assume the console already did the interrogation.

## Anti-patterns

- **Don't merge two audiences to keep the run simple.** If line managers and their teams
  need genuinely different things (see `briefing_deck`), collapsing them back into one
  audience defeats the reason Stage 2's audience x channel matrix exists.
- **Don't infer a sender from the org name.** "Payroll Team" is not the same act of
  interrogation as asking who the audience actually trusts to tell them this.
- **Don't round a headcount or a date to make it look more finished.** 2,400 stays 2,400;
  "mid-September" stays an `open_questions` entry, not 15 September.
- **Don't skip an audience because the brief doesn't mention them but the change obviously
  touches them.** A payroll change that goes unmentioned for contractors, if contractors
  are paid through the same system, is a gap worth raising, not a scope decision to make
  silently.
