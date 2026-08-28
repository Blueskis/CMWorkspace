# Writing knowledge checks

## The shape

**Every knowledge check carries exactly five questions, mixing multiple-choice and
True/False.** The default shape is **3 MCQ and 2 True/False**. A check that is all of one
type fails Stage 5, and so does one with four or six questions.

Every question carries three things besides its stem: the answer, a rationale, and the
source anchor that proves it. All three go in the **speaker notes** — never on the slide —
so the participant copy carries the questions and no key.

If a module cannot yield five real questions, the module is too thin. Merge it into its
neighbour at Stage 2. Padding a check to five with filler is worse than a shorter module,
because it teaches learners that the checks are not worth taking seriously.

## What to ask about

Ask about the things people get wrong in the system:

- **Business rules with a boundary.** Thresholds, date rules, character limits. "An order
  totalling 48,000 routes to whom?" tests something they will do.
- **Mandatory versus optional.** The most consulted fact in any system training.
- **Sequencing.** What runs on save versus on submit. What can be edited in which state.
- **Exception paths.** What happens when the supplier is blocked, the approver is away, the
  transmission fails. These are what people hit under pressure and least often remember.
- **The negative permission.** What a role *cannot* do. Approvers reliably expect to be able
  to fix a line rather than reject it.

What not to ask about: anything whose answer is not in the source documents. There is no
`[GAP]` escape hatch for a question — if the specification does not say, you cannot test it.
Stage 5 fails a question without a resolving source anchor.

## Multiple choice

- **Three or four options, exactly one correct.**
- **Distractors come from the specification**, not from imagination. The neighbouring status
  value, the adjacent approval band, the field that looks similar. A distractor nobody would
  pick tests nothing and turns a four-option question into a two-option one.
- **Never "all of the above" or "none of the above."** They test test-taking.
- **Never a negative stem.** "Which of these is NOT mandatory?" tests careful reading. Ask
  "Which of these can you leave empty?" instead — same knowledge, no trap.
- **Keep options parallel** in length and grammar. The longest option being correct is the
  oldest tell in assessment writing.

## True/False

True/False earns its place on rules, not on facts. "Delivery Date is mandatory" is a
flashcard; "A draft order can be saved even when there is not enough budget for it" makes
the learner reason about when the budget check runs.

- **Aim for roughly half false.** Stage 5 warns when every True/False answer in a check is
  the same, because the set becomes guessable.
- **A false statement must be plausibly false** — a distortion of a real rule, not an
  absurdity. "An order can be split to stay under your approval threshold" is a good false
  statement because it is what someone would try. "Purchase orders are approved by the
  supplier" is not, because nobody believes it.
- **State the rule positively and let the truth value do the work.** Negation inside a
  True/False statement is normal and fine — "Order Total cannot be typed directly" is a
  perfectly good statement — but a double negative is not.
- **The rationale for a false statement says what the rule actually is.** "False. The budget
  check runs on submit, not on save" is the teaching moment; "False." is not.

## The rationale

Written for the trainer to read aloud when someone gets it wrong. One or two sentences,
saying why the answer is right and — for a false statement or a plausible distractor — why
the tempting answer is wrong. It is the most-used part of a knowledge check and the most
often left empty; Stage 5 fails a question without one.

## Cognitive level

Tag each question `recall` or `apply`, and prefer `apply`. A check made entirely of recall
tests whether they read the slide five minutes ago. One or two recall questions per check
is reasonable — a mandatory-field list is worth knowing cold — but a question that puts the
learner in a situation is worth more:

> *Recall:* "Which fields are mandatory on the PO header?"
> *Apply:* "You set a Delivery Date of yesterday and try to save. What happens?"

Same knowledge. The second one tells you whether they can use it.

## Coverage

Every learning objective must be tested by at least one question — Stage 5 fails on an
objective that is taught but never checked. Tag each question with the `objective_ids` it
tests, and check the union across all checks covers every `LO` before you finish Stage 3.
