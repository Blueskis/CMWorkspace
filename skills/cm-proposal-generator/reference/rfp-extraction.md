# RFP Extraction Guide

How to turn an RFP document into `rfp_brief.json`. Read this in Stage 1.

## What to pull out

### Client & engagement metadata
Legal entity name (not the trading name — bids get rejected on this), RFP reference
number, issuing department, engagement title, contract term, and start date.

### Requirements
The core of the brief. Every distinct thing the client asks us to do, be, or evidence
gets its own entry with a stable ID (`R1`, `R2`, …).

Requirements hide in at least five places, and only the first is obvious:

1. **The numbered requirement schedule** — easy, if it exists.
2. **The scope of work narrative** — prose paragraphs containing "the supplier shall,"
   "must be able to," "is expected to." Each is a requirement.
3. **The evaluation criteria** — anything scored is a requirement, even if it appears
   nowhere in the scope section.
4. **The response format instructions** — "responses must include a named engagement
   lead" is a requirement about the deck itself.
5. **Terms, annexes, and attachments** — insurance levels, security clearance, data
   handling, subcontractor declarations.

Classify each as `mandatory` (shall/must/required) or `desirable` (should/preferred/
desirable). Mandatory failures are usually disqualifying; desirables are scored. If the
RFP uses its own terminology (M/D, Essential/Desirable, Pass-Fail), record that in
`raw_priority` alongside the normalised value.

### Evaluation criteria and weights
Capture the criteria and their percentage weights verbatim. Stage 2 sizes the deck from
these. If weights aren't stated, record `"weight": null` — don't guess one.

### Constraints
Submission deadline (with timezone — RFP deadlines are precise and unforgiving), page or
slide limit, file format, font/size minimums, naming convention for the submitted file,
portal or email address for submission, question-deadline for clarifications.

Slide limits and font minimums directly constrain Stage 2 and Stage 4. Extract them even
when they feel like boilerplate.

### Client context
Drivers for the change, the systems or reorganisation involved, affected population size,
geography, incumbent supplier if named, known pain points, stated success measures.
This feeds "Our Understanding of Your Situation," which is where a proposal most visibly
proves it read the document.

## Handling ambiguity

Mark `"confidence": "inferred"` and write a `note` when:
- The requirement is implied by evaluation criteria but not stated in scope.
- Scope and annex contradict each other — record both readings and flag it.
- A term is undefined ("comprehensive change support") in a way that materially changes
  the size of the work.

**Never resolve a material ambiguity silently.** Surface it in the Stage 1 read-back — it
is often worth a clarification question to the client before the question deadline, and
that deadline is usually well before the submission deadline.

## Anti-patterns

- **Don't merge requirements to tidy the list.** "Provide training and communications
  support" is two requirements; they'll be scored separately and may be covered by
  different sections.
- **Don't drop requirements we can't meet.** Extract them, then let Stage 3 flag the
  `[GAP]`. A requirement we can't meet is a bid/no-bid decision for the practitioner, not
  something to quietly omit.
- **Don't paraphrase mandatory language.** Keep the client's own wording in `text` — it's
  what the evaluator matches against.
- **Don't skip the annexes** because the main document reads complete. Insurance levels
  and clearance requirements live there and are routinely disqualifying.
