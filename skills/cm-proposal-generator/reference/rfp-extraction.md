# RFP Extraction Guide

How to turn an RFP document into `rfp_brief.json`. Read this in Stage 2, after triage.

## Before extracting: which parts are ours?

On anything bigger than a CM-specific chapter, run `scripts/triage_rfp.py` first and read
both of its lists. Extraction is expensive attention, and spending it on the procurement
timetable while the training obligation sits unnoticed in the service-levels annex is the
failure this guards against.

Record the outcome in `cm_scope`: the sections in scope, the sections **read and
excluded** with a reason, and the parts the tender cross-references that we were never
sent. The excluded list is what makes the read auditable — a section in neither list was
never looked at, which is not the same as a section that was looked at and dismissed.

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

**A tender written entirely in "should" is a trap, not a light touch.** The transport ERP
sample says `should` 85 times, `must` 30, and `shall` never — so a faithful read produces a
brief that is almost all `desirable`. Every one of those clauses is still scored. Record
the document's own modal in `raw_priority`, and say plainly at the read-back that priority
here reflects the tender's wording rather than how hard it will be marked; a team that
reads "should" as optional under-answers the whole document.

### Requirement `kind` — what answering it actually means

Priority says how badly we need to answer. `kind` says what answering *is*, and they are
independent:

| kind | Reads like | Answered by |
|---|---|---|
| `proposal-content` | "the Tenderer shall provide a Transition Management plan" | A slide describing it |
| `delivery-obligation` | "the Contractor shall collect evaluation forms within seven days" | A commitment inside the relevant approach section |
| `commercial-constraint` | "at no additional cost to the Authority" | An explicit acknowledgement in commercials |
| `submission-rule` | "responses must be PDF, 20 pages maximum, named `<ref>`-CM.pdf" | The deck itself. No slide covers it. |

**The tender's own pronouns usually tell you.** Where a document distinguishes *the
Tenderer* (the bidder, writing this response) from *the Contractor* (the party after
award), that distinction maps almost directly onto the first two kinds. Where it doesn't
distinguish, read the verb: describing, proposing and evidencing are proposal content;
collecting, delivering and maintaining are delivery obligations.

Only `submission-rule` is exempt from slide coverage in Stage 6 — the other three all need
a home in the deck. So when a requirement could plausibly be two kinds, the cost of
choosing wrong is small in every direction except one: do not mark something
`submission-rule` unless it genuinely governs the document rather than the work.

### Evaluation criteria and weights
Capture the criteria and their percentage weights verbatim. If weights aren't stated,
record `"weight": null` — don't guess one.

**Most CM tenders publish no weights at all.** That is normal, not a gap in your reading.
When there are none, Stage 3 sizes the deck from `named_deliverables` instead, so capturing
those well becomes the important job.

### Named deliverables
Every deliverable the RFP names, **verbatim and with its clause reference**, into
`named_deliverables`. These do two jobs: they give each section its name (Stage 3 uses the
client's term rather than imposing ours), and they size the deck when weights are absent.

**Capture the name exactly as the client writes it** — capitalisation, qualifiers and all.
"Detailed Stakeholder Engagement Plan" is not "Stakeholder Engagement Plan". This field is
what the slide title is built from, so a paraphrase here becomes a paraphrase on the deck,
and the evaluator looking for their deliverable does not find it.

Record `emphasis_clauses` — how many clauses the RFP spends on each. That ratio is the
sizing signal: a deliverable specified across fourteen sub-clauses matters more to this
client than one mentioned once, and the deck should show it.

Mark `optional_scope: true` for anything the RFP asks to be priced as an option the client
may or may not exercise. It still needs a home in the response, but it is not core scope.

Deliverables that don't match the canonical section list still get recorded — leave
`canonical_section` empty. Transition Management plans, Change Intervention plans and
Change Sustenance Plans are all common and none is in the canonical ten.

### Delivery methodology
Read whether the programme is **agile, waterfall, or hybrid**, and record the evidence in
`methodology_evidence` so the call is auditable.

- *Agile*: sprint, backlog, ceremonies, Product Owner, user stories, Definition of Done,
  increments, releases, MVP.
- *Waterfall*: phases, stage gates, sign-off, baselined requirements, UAT windows, a single
  go-live.
- *Hybrid*: both present — commonly agile build inside phase-gated governance. Name it
  rather than forcing a choice.

This shapes the entire CM approach, so if the RFP is genuinely silent record `not-stated`
and raise it as an open question. Do not default to either.

### Constraints
Submission deadline (with timezone — RFP deadlines are precise and unforgiving), page or
slide limit, file format, font/size minimums, naming convention for the submitted file,
portal or email address for submission, question-deadline for clarifications.

Slide limits and font minimums directly constrain Stage 3 and Stage 5. Extract them even
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

**Never resolve a material ambiguity silently.** Surface it in the Stage 2 read-back — it
is often worth a clarification question to the client before the question deadline, and
that deadline is usually well before the submission deadline.

## Anti-patterns

- **Don't merge requirements to tidy the list.** "Provide training and communications
  support" is two requirements; they'll be scored separately and may be covered by
  different sections.
- **Don't drop requirements we can't meet.** Extract them, then let Stage 4 flag the
  `[GAP]`. A requirement we can't meet is a bid/no-bid decision for the practitioner, not
  something to quietly omit.
- **Don't paraphrase mandatory language.** Keep the client's own wording in `text` — it's
  what the evaluator matches against.
- **Don't skip the annexes** because the main document reads complete. Insurance levels
  and clearance requirements live there and are routinely disqualifying.
