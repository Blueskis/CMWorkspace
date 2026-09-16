# Writing the update

The brief is evidence. This is about turning it into three minutes a consultant can stand
up and deliver — and the difference is mostly aggregation, causation and the ask.

## Structure

Five sections, in this order. It matches how the room listens: where we are, what's wrong,
what's new, what I need, what changed underneath.

1. **Headline** — two sentences. The one thing that moved and the one thing you need.
   Almost always `[JUDGEMENT]`; it is your read, not a change record.
2. **Where we are** — aggregate progress. Roll-ups, not row-by-row.
3. **What moved the wrong way** — slips, regressions, deteriorating RAG. Every high-rated
   change lands here or in the asks.
4. **New this week** — added scope, new risks, new people, new objects.
5. **Asks** — decisions needed, numbered, each with the change it comes from.

Anything low-rated that survives into the update is usually a mistake. Omit it explicitly
with `<!-- omit: C# reason -->` rather than dropping it silently, so QA can tell the
difference between a decision and an oversight.

## Aggregate before you enumerate

Five `status_forward` changes on a training sheet is not five sentences. It's "completions
went from one to four of eight" with the five IDs cited on that one line. The `rollups` in
the brief exist for exactly this — quote the movement, cite the changes underneath it.

Enumerate only when the individual item is the point: a named person blocking a go-live, a
single object that went red.

## Say what changed, then what it means — and mark which is which

Every claim carries either a `[C#]` citation or `[JUDGEMENT]`. That's the whole
discipline, and it survives contact with a sceptical client: anything you assert about the
documents can be traced to a specific cell, row or slide, and anything you assert about
what it *means* is visibly your professional read.

> Both warehouse leads moved from 11 to 25 September `[C10]` `[C11]`, and neither had
> started as of Week 11. This is the super-user availability problem showing up in the
> training plan rather than a scheduling choice. [JUDGEMENT]

The first sentence is checkable. The second is the reason anyone needs a consultant in the
room. Keep them adjacent and keep them distinguishable.

## Connect changes across documents

The value of merging three documents into one brief is the connections nobody looking at a
single file would make: a risk that opened in the plan, an activity added to carry it, and
a learner added to the tracker are one story. Look for these before writing — same names,
same dates, same workstream appearing in more than one document in the same week.

Cite every change involved in the connection, and mark the connection itself as judgement.

## Things not to do

- **Don't narrate the diff.** "Cell D4 changed from 60 to 100" is not an update.
- **Don't imply causation the documents don't show.** A slip appearing the same week as an
  escalation is a connection worth raising and a hypothesis, not a finding.
- **Don't quietly upgrade "not started" to "on track."** A status the documents don't
  assert is an invention, and QA will catch it as an unattributed claim.
- **Don't hide a removal.** An item that vanished from the tracker is rated high for a
  reason — either it was completed and dropped, or it was quietly descoped, and the room
  should be told which.
