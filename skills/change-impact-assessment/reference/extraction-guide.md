# Extraction Guide — Mining Source Documents for Change Impacts

How to get from a folder of unstructured project documents to a populated
`cia_input.json`. Each source type carries different evidence; the quality of the
assessment comes from combining them, not from reading any one of them well.

## What each source type gives you

| Source | Reliably gives you | Does **not** give you |
|---|---|---|
| **Interview / workshop notes** | The real as-is (including workarounds not in any document), pain points, anticipated resistance, headcounts, who actually decides | The to-be. Interviewees speculate; don't record speculation as design. |
| **Process design models** (Signavio BPMN, process hierarchy exports) | The to-be flow, swimlanes → impacted roles, hand-offs, approval paths, process IDs for traceability | Why it changed, how people feel, whether the roles named actually exist yet |
| **Functional specifications** | System behaviour, configuration decisions, field-level change, approval matrices, integrations, what is now *enforced* vs. discretionary | Volume of people affected, the as-is it replaces, business rationale in plain language |
| **Org design / RACI docs** | Role changes, new positions, shared-service moves | — |
| **Solution scope / blueprint** | Module scope, wave/geography phasing, go-live dates | — |

**The core move: an impact row is usually one as-is statement (from interviews)
joined to one to-be statement (from Signavio or the FS).** If you only have one
side, the row is incomplete — mark it Low confidence and put the missing side in
`notes` as an open question. Do not invent an as-is to make a row look finished.

## Working through the documents

### Pass 1 — Build the process spine

Read the process design documents first and list every process in scope. This becomes the
skeleton: impacts hang off processes, not off documents. Working document-first produces a
duplicated, unstructured register.

The client template's taxonomy runs to **four levels**, each with a numeric code:

| Level | What it holds | Example |
|---|---|---|
| **L1** | Process area | Procure-to-Pay |
| **L2** | Process group | Requisitioning |
| **L3** | Process | Raise Requisition |
| **L4** | Activity or variant | Catalogue Purchase — Occasional User |

**L4 is where the register earns its keep.** It is the level at which one process splits into
the several different things it means for different people — the same "Raise Requisition"
process is a different experience for an occasional requisitioner, a daily Facilities
coordinator, and an engineer who has just lost free-text buying. If every L4 is a restatement
of its L3, the rows have not been split finely enough.

Keep L1 and L2 consistent with whatever the programme already uses in its own governance —
do not invent a parallel taxonomy. Codes are numeric and unique within their parent.

### Pass 2 — Attach the to-be

For each L3/L4 activity, pull from the process model and functional spec:
- The to-be flow in one or two sentences of *business* language, not system language.
  "Buyer creates a requisition in Guided Buying and it routes automatically on value"
  — not "REQ_CREATE triggers workflow WF_APPR_01".
- Which **swimlanes/roles** perform it → these are your impacted roles.
- The target module/solution.
- What the system now **enforces** that used to be discretionary. This is the single
  richest source of impacts and the one most often missed — and because the template has no
  policy dimension, it lands in **Others** rather than in a score.

### Pass 3 — Attach the as-is and the human signal

Go through interview and workshop notes and, for each L3/L4 activity, capture:
- How it works **today**, including the workarounds ("we keep a side spreadsheet",
  "we call the buyer directly"). Workarounds that the new system blocks are impacts,
  even when no document mentions them.
- Headcounts and geography — how many people, in which entities.
- **Verbatim quotes** signalling resistance, loss, or fear. Keep the quote in the relevant
  dimension description (`people_impact` is usually the right home) or in `notes`; a real
  sentence from a real interviewee moves a steering committee far more than an assessment
  adjective does.
- What they'd *gain* — this becomes `benefit_narrative`, the raw material for the
  "what's in it for me" message. If nobody named a benefit, say so; a change with
  no articulable benefit for the affected group is itself a finding.

### Pass 4 — Split and merge

Split a candidate row into several when different stakeholder groups experience the
same process change differently. "Requisition creation moves to Guided Buying"
is one process but at least two impacts: casual requisitioners (Technology-heavy, People-light
— a new tool for an occasional task) and procurement buyers (People- and Process-heavy — the
job itself changes). Each becomes its own L4. **One row = one process change × one stakeholder
group**, because the training and comms response is per-audience.

Merge rows when the same group experiences several near-identical micro-changes in
one process — a register with 400 rows nobody reads is worse than one with 60 that
gets validated.

**Target size for a baseline:** roughly 40–120 rows for a full ERP/Ariba implementation.
Under ~30 rows on a full-scope programme usually means whole process areas or stakeholder
groups were missed; over ~200 means you're recording system features rather than human
impacts.

### Pass 5 — Score, then derive the response

Score **People, Process and Technology 0-3** against the anchors on the template's own
`Change Impact Ratings` sheet, restated in `rating-methodology.md`. Write the matching
description for each dimension as you score it — the template pairs every score with a
description column, and a score with no explanation is the first thing a client challenges.

Then set the training and comms response from the rating band (see `response-playbook.md`).
Score first — deriving the score backwards from a training decision already made is the most
common way these assessments lose credibility.

Record everything the three dimensions don't cover — policy, control, compliance, data
ownership, engagement, commercial exposure — in **Others**. On a system implementation with
enforced controls this is often where the most contentious material sits.

## Coverage checks before you generate

Run these against the register and report anything that fails:

1. **Every in-scope L1 process area has at least one impact, and at least one High.** A
   silent area means unread documents, not an unaffected business.
2. **Every stakeholder group named in any interview appears at least once.**
3. **Every impact has both an as-is and a to-be**, or a Low confidence flag and an
   open question.
4. **Indirect groups are represented.** Approvers, requisitioners, AP clerks, and
   suppliers are impacted by process changes they never asked about and are rarely
   interviewed. Suppliers in particular are systematically missed on Ariba
   implementations — supplier onboarding, catalogue enablement, and network
   registration all land outside the client's own org chart.
5. **Every High-rated row has a named change champion and comms owner**, and every
   High-resistance row has a mitigation action.
6. **Every source document supplied is cited by at least one row.** If a document
   produced nothing, say so explicitly — it usually means it was scoped out or
   misread, and either is worth flagging.

## Traceability

`source_ref` is not decoration. Every row carries the reference IDs of the documents
it came from (e.g. `INT-03; FS-014`), and the **Traceability** sheet in the output
counts impacts per document. When a business owner challenges a row in a validation
workshop — and they will — the reference is what turns the conversation from
"we disagree" into "let's look at what the spec says".

Use short stable IDs (`INT-01`, `SIG-04`, `FS-012`) declared once in `meta.source_documents`,
and cite multiple with `; ` between them.

## Things to avoid

- **Recording system features as impacts.** "Ariba supports multi-round auctions" is
  not an impact. "Category managers must now run second-round negotiation in the
  system rather than by email, and lose the ability to negotiate offline" is.
- **Copying spec language into the register.** The audience is a business lead, not
  a configurer. Every description should survive being read aloud in a town hall.
- **Uniform ratings.** A register where everything is High is a register nobody will
  act on — it gives the programme no way to prioritise. Expect a spread; if you don't
  have one, re-score against the anchors rather than adjusting to taste. On a greenfield
  implementation the Technology score will sit at 3 almost everywhere, which is the anchor
  working correctly — but it means People and Process are doing all the discriminating, so
  score those two carefully.
- **Silent inference.** Anything not in a document is Medium or Low confidence and
  gets an open question. Inference is expected and useful; undeclared inference is
  what gets an assessment thrown out.
