# Change Intake

How to interrogate a practitioner into a `change_brief.json`. The brief is authored once and
then serves every channel, so an hour spent here is repaid on every subsequent run — and a
weak brief produces four weak drafts rather than one.

## The order to ask in

Ask about the **audience before the message**. Practitioners arrive with the programme's
framing ("we're migrating payroll to semi-monthly") and the comm has to be written in the
reader's ("you'll be paid on the 15th and the last working day"). Starting with the audience
forces that translation early, while it is still cheap.

1. Who is affected, and how differently? → `audiences[]`
2. What does each of them have to *do*? → `required_action`
3. Why should they care? → `whats_in_it_for_me`
4. What is actually changing, and why now? → `change`
5. What is *not* changing? → `what_is_not_changing`
6. When? → `milestones[]`
7. Who is saying it, and where do people go for help? → `governance`
8. What must the messages be? → `key_messages[]`

Key messages come last on purpose. A practitioner asked for messages first will give you the
programme's talking points; asked after four questions about the audience, they give you
something a reader would recognise.

## The questions that get skipped

These are the ones that are missing from most real briefs, in rough order of how much damage
the omission does.

**"Where do people go when it doesn't work?"** → `governance.help_route`. A comm with an action
and no support route generates a wave of tickets to whoever's name is on it. Structured, not
prose, so Stage 4 can assert it. Ask for hours and an escalation too.

**"What's staying the same?"** → `change.what_is_not_changing`. Named reassurance stops more
speculation than any amount of positive messaging. If nobody has thought about it, the answer
is usually available in ten seconds and worth a paragraph.

**"Is that date confirmed or indicative?"** → `milestones[].date_confidence`. Publishing an
indicative date as confirmed is the fastest way to burn a programme's credibility. Where the
answer is "indicative", the draft must hedge it in words, not just in the JSON.

**"Who's signing it, and why them?"** → `governance.sender.why_this_messenger`. The messenger
is content. If the answer is "the programme mailbox" for a high-impact change, that is worth
one challenge before accepting it.

**"What can't we say?"** → `constraints.prohibited_terms` and `key_messages[].sensitivity`.
Every organisation has words that carry unintended freight — "restructure", "efficiencies", a
term of art from a previous failed programme. Ask directly.

**"Does this segment have to do anything at all?"** → `required_action.optional`. "Nothing to
do" is a legitimate answer and must be recorded as `optional: true` with the action describing
what they should simply be aware of. An empty action string is not the same thing, and the
schema rejects it.

**"Do managers need to know first?"** → `manager_cascade_required`. For any `high` impact
segment the default answer is yes.

## Assigning IDs

Three ID spaces, all stable for the life of the brief:

- `A1, A2, …` audience segments
- `M1, M2, …` key messages
- `T1, T2, …` milestones

These are the spine. Stage 2 maps every part of the draft to them and Stage 4 proves nothing
went unaddressed. **Never renumber**: a run's `qa_report.md` references them, and a plan written
against `M3` meaning one thing and re-read against `M3` meaning another is worse than no
traceability at all. Add `M7`; do not recycle `M3`.

Every `key_messages[]` entry carries `audience_ids`. This is what lets a single-audience run
compute its own coverage denominator — an email to `A1` alone is not failed for omitting a
message aimed only at `A2`.

## Confidence and gaps

Never invent an audience, a date, or a required action. Where the practitioner is unsure:

- A rationale they are inferring rather than quoting → `change.rationale_confidence: "inferred"`.
  It must not then be written as though the sponsor said it.
- A date that is not locked → `date_confidence: "indicative"`.
- Anything else unanswered → `open_questions[]`, which flows through to a visible `[GAP]` in
  the draft.

A draft that visibly flags a date as unconfirmed is worth more than one that confidently states
the wrong date. The `[GAP]` is doing its job when it is uncomfortable to look at.

## Reporting back

After writing the brief, report: the change and its type, the audience segments with their
impact levels, how many key messages and how many are `must-land`, the confirmed and indicative
dates, the sender, the help route, and anything in `open_questions`.

This is a transparency checkpoint, not an approval gate — continue into Stage 2 unless the
practitioner redirects.
