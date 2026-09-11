# Knowledge Check Quality Rules

How to write `question_bank.json` entries in Stage 3. Read `schemas/question_bank.schema.json`
for the exact field contract; this covers what makes a question actually worth asking.

## Every question needs an objective and a source

`objective_id` must reference a real `LO` from `training_brief.json`, and `sources` must
cite the `source_map.json` section(s) where the FSD actually states the answer. **A
question the source documents don't answer is a `[GAP]` on the deck plan, not a guess** —
never write a question whose key you can't point to in the source text. If a Stage 2
module wants a knowledge check on something the FSD leaves ambiguous, that's a sign the
content slide itself is thin, not just the question.

## Test the task, not the trivia

A good question mirrors what the learner will actually have to decide on the job. A weak
question tests whether they memorized a fact that doesn't drive a decision.

| Weak (trivia) | Strong (task) |
|---|---|
| "How many approval tiers exist?" | "A $12,000 PO is submitted. Who approves it?" |
| "What is the name of the approval screen?" | "You need to reassign an approval that's stuck with an absent manager. What's the correct action?" |
| "True/False: the system has a Comments field." | "A requester enters an invalid vendor code. What does the system do, and what should the requester check first?" |

The strong-column pattern: put the learner in the situation the FSD describes, then ask
what happens or what to do — not what a UI element is called.

## Distractors are plausible, not throwaways

For `mcq` (minimum 4 options: 1 correct + at least 3 distractors), every wrong option
should be something a learner who half-understood the material might actually pick — a
neighbouring threshold, an adjacent status value, a role that's close but not quite
authorized. Never pad with an obviously absurd option just to hit the option count; a
distractor nobody would pick isn't testing anything and wastes the learner's attention.

Pull distractors from adjacent spec content: if the correct answer is "Manager approval"
for a $5,000 PO, good distractors are the *other* thresholds' outcomes ("Auto-approved,"
"Director approval"), not an invented role the FSD never mentions.

## Question types

- **`mcq`** — single correct answer, ≥4 options. The default for most task-based checks.
- **`multi`** — more than one correct answer, when the task genuinely has multiple valid
  actions (e.g., "which of the following require Director approval? select all that
  apply"). Don't use `multi` just to make a question harder — only when multiple options
  are actually, simultaneously correct.
- **`true-false`** — use sparingly. Good for a single sharp factual check ("a PO over
  $10,000 can be self-approved by the requester: True/False") but easy to guess and weak
  at testing task performance. Prefer `mcq` when the content supports it.
- **`scenario`** — a longer stem describing a situation, then a question about the correct
  action. Use for exception-handling content (module 9) where the "correct answer" is a
  judgement call the FSD's exception rules actually settle, not a simple lookup.

## Placement

One knowledge-check slide closing each task-walkthrough module (see
`reference/module-library.md`, module 8), while the procedure is still fresh — not all
checks deferred to a single slide at the end of the deck. A consolidated review slide
before the summary module is a reasonable addition on top of the module-local checks, not
a replacement for them.

## Rationale and the facilitator answer key

Every question's `rationale` should name *why* the key is correct, citing the source
section — this is what becomes both the speaker note on the check slide and the entry in
the facilitator answer-key module (`reference/module-library.md`, module 12). A rationale
that just restates the correct option without explaining the underlying rule isn't useful
to a facilitator fielding a learner's follow-up question.

## What `qa_training.py` checks mechanically, and what it doesn't

The script verifies structure — every key references a real option, `mcq` has enough
options, every `objective_id` and `sources` entry actually exists — because those are
objectively checkable. It **cannot** verify that a question actually tests its stated
objective, that the key is genuinely correct per the cited source, or that the distractors
are plausible rather than throwaway. That's exactly what the `training-qa-agent` skill's
assessment-quality check does in Stage 5 — read its findings, written into the deck's
speaker notes, before treating the question bank as finished.
