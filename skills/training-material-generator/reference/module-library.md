# Training Module Library

How Stage 2 chooses, names, orders, and sizes the deck's modules.

Read the rules first — they govern everything below. The catalogue is raw material, not a
template to fill in order. Not every module belongs in every deck; a two-screen approval
tweak doesn't need a "roles and responsibilities" module, and a brand-new system does.

---

## Rule 1 — Use the client's own terminology, not ours

The canonical module names below are internal handles for finding the right guidance —
they are not slide titles. A field is named what the FSD names it; a screen is named what
the FSD names it; a role is named what the FSD names it. If the FSD calls a status
"Pending Level 2 Approval," the slide says that, not "awaiting further sign-off." A
learner searching the live system for a button you renamed fails the task, and a
facilitator using terminology the FSD contradicts undermines the whole deck's authority.

## Rule 2 — Size modules by procedural weight, not symmetry

Count what the FSD actually dwells on. A process described in one paragraph with no
screenshots gets a bullet inside a broader module, not a module of its own. A process the
FSD spends eleven sub-clauses and six screenshots on gets a dedicated module, split across
multiple slides if the steps don't fit one. Resist making every task the same length for
the sake of a tidy-looking outline — an uneven deck that matches the spec's own emphasis
is more useful than a uniform one that doesn't.

## Rule 3 — Every `procedure` section from `source_map.json` gets a home

A module, or an entry in `training_brief.json`'s `out_of_scope` with a stated reason.
Never silently dropped. This is the rule Stage 5's source-coverage check enforces
mechanically — build the mapping as you plan, not after.

## Rule 4 — Every learning objective maps to at least one slide

An objective with no slide at the end of Stage 2 means the outline is wrong, not that the
objective was unimportant. Go back and add a slide, or reconsider whether the objective
belongs in this run at all (raise it with the practitioner rather than quietly deleting it
— an objective usually exists because someone asked for it).

---

## The canonical arc

Presented in typical order, but entry criteria matter more than position — skip a module
whose criteria aren't met, and don't force one in that doesn't apply.

### 1. Welcome / opening
**Always include.** One slide. Use the `hook-maker` skill (question or story option) for
the actual hook; this module also states the deck's scope in one sentence ("this covers
creating and approving standard purchase orders in \[system\]") so learners self-select in
or out immediately.

### 2. What's changing and why (WIIFM)
**Include when this training accompanies a change** (a new system, a process redesign, a
policy update) rather than pure onboarding for an unchanged process. Answers "what's
different" and "what does this mean for me" before any procedural content — learners tune
out procedure they don't yet believe applies to them.

### 3. Learning objectives
**Always include.** State every LO from `training_brief.json` in learner-facing language
("by the end of this session, you will be able to..."). This is also the slide the
knowledge checks are implicitly promising to test — if an objective doesn't appear here,
its questions will feel unmotivated later.

### 4. End-to-end process overview
**Include whenever the source procedure has more than ~3 steps or spans more than one
role.** A `process` or `swimlane` diagram (see `reference/diagram-patterns.md`) belongs
here, before the walkthrough modules — learners need the map before the turn-by-turn
directions. Skip this module only for a single-screen, single-role task.

### 5. Key terms / glossary
**Include when the FSD introduces domain vocabulary the audience won't already have** —
new field names, new status values, new role titles. Pull directly from
`training_brief.json`'s `glossary`. Skip if the process uses only vocabulary the audience
already knows.

### 6. Roles and responsibilities
**Include whenever more than one audience/role touches the process.** A `swimlane`
diagram or a simple table works well here — who does what, and (critically for approval
workflows) who does *not* have authority to do something, since that's the FSD detail
learners most often get wrong on the job.

### 7. Task walkthrough modules
**The core of the deck; always include, one module per named procedure (Rule 2 decides
the split).** Each walkthrough module pairs numbered steps with the screenshot that
illustrates each one (`reference/screenshot-placement.md`), in the FSD's own step order.
Where the FSD documents an approval threshold, a routing rule, or any other conditional
logic, render it as a `decision` diagram rather than prose — see
`reference/diagram-patterns.md`.

### 8. Knowledge check (per module)
**Include one per task-walkthrough module**, immediately after it, while the procedure is
fresh. See `reference/knowledge-checks.md`. Don't defer all checks to the end of the
deck — spaced, module-local checks catch a misunderstanding before it compounds into the
next module.

### 9. Exceptions and common errors
**Include when the FSD documents error states, validation rules, or edge cases** — what
happens when a PO exceeds budget, what an error message means, what to do when an
approver is unavailable. These are exactly the situations training that only covers the
happy path leaves learners unable to handle. Skip only if the FSD genuinely has none.

### 10. Where to get help
**Always include.** Support contact, escalation path, where documentation lives after the
session ends. One slide; don't pad it.

### 11. Summary and next steps
**Always include.** Recap the learning objectives (mirror module 3's language exactly —
this is a callback, not a rewrite), state what happens next (go-live date, further
training, where to practice).

### 12. Facilitator answer key
**Always include when a question bank exists.** A back-of-deck (or facilitator-guide-only,
if the delivery mode separates them) module listing every question, its correct answer,
and the rationale with its source anchor. Not learner-facing — mark it clearly for
facilitator use only.

---

## Diagnostic note: when the FSD itself is thin

An FSD that's mostly a data dictionary (heavy on `reference`-classified sections, light on
`procedure`) usually can't support a full walkthrough-style deck. Say so rather than
padding a thin deck with generated filler — a shorter, honest deck plus a request for a
better source document beats an inflated one built on inference.
