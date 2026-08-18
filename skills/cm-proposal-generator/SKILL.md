---
name: cm-proposal-generator-v0.2
description: Generates a change-management proposal deck (.pptx) from an RFP and the context of a project bid, built on an approved slide template and populated from a curated knowledge bank of methodology, case studies, credentials, team bios and commercial boilerplate, with past tenders and past decks held in Airtable as source documents. Runs a six-stage pipeline — triage a full tender to find the sections that are CM's to answer, parse those into a structured brief, plan the proposal's sections against the client's stated requirements and their own naming, retrieve matching knowledge-bank content, build the .pptx on the template, then QA it for requirement coverage, provenance and template fidelity. Use whenever a CM practitioner wants to draft, assemble, or respond to an RFP, ITT, RFI, or client brief with a proposal, pitch, or bid deck — phrases like "generate a proposal from this RFP", "draft a CM proposal", "respond to this tender", "build a pitch deck for this client", "which parts of this RFP are ours", "we've been invited to bid". Do NOT use for diagnosing or assessing an existing change initiative — this skill writes bids, it does not analyse programmes.
---

# CM Proposal Generator

Turns an RFP plus the context of a bid — briefing notes, incumbent history, stakeholder
lists, budget guidance — into a client-ready change-management proposal deck, built on the
firm's approved template and written from the firm's own knowledge bank rather than
invented from scratch.

**The point of this skill is provenance and coverage, not prose.** Anyone can write a
proposal deck. What makes this useful to a practitioner is that (a) every claim traces back
to a knowledge-bank entry or an explicit `[GAP]` flag, (b) every requirement in the RFP is
provably answered somewhere in the deck, and (c) the deck is demonstrably the firm's
template rather than something that resembles it. All three are checked in Stage 6, and
none is optional.

## MVP scope (read this before promising anything)

This is v0.2. What it does and does not do:

| In scope | Out of scope |
|---|---|
| One deck, one client, one RFP per run | Multi-lot / multi-workstream bids split across decks |
| Triage of a full multi-part tender to find the CM sections | Answering the non-CM parts of a tender |
| Sections from the section library, named the client's way | Free-form custom sections invented per bid |
| Knowledge-bank retrieval by section + tag match | Semantic/embedding search over the bank |
| A real `.pptx` on the firm's approved `.potx`, or on the generic stand-in | Generating a template, or restyling an off-template deck |
| Requirement-coverage, provenance and template-fidelity QA | Pricing calculation, resourcing models, legal review |
| A draft for the practitioner to edit | A submission-ready final document |

Always hand the output over as **a first draft for the practitioner to review**, never as
a finished submission. Say so explicitly when you deliver it.

## Pipeline

```
  Stage 1  TRIAGE      whole RFP ────────────────────▶ rfp_triage.json
  Stage 2  INTAKE      CM sections + bid context ────▶ rfp_brief.json
  Stage 3  PLAN        brief + section library ──────▶ proposal_outline (in plan)
  Stage 4  RETRIEVE    kb_index + outline ───────────▶ proposal_plan.json  (content + sources)
  Stage 5  BUILD       plan + template ──────────────▶ proposal.pptx
  Stage 6  QA          coverage + provenance + fidelity ─▶ deliver
```

Each stage writes a file to the run workspace, so a run can be resumed, inspected, or
re-run from any stage without redoing the ones before it. Never skip straight from an RFP
to a deck — the intermediate artifacts are what make the output auditable.

### Run workspace

Create `proposals/<client-slug>-<YYYYMMDD>/` in the user's current working directory:

```
proposals/acme-20260807/
├── inputs/              # copies of the RFP and any client inputs
├── rfp_triage.json      # Stage 1
├── rfp_brief.json       # Stage 2
├── kb_index.json        # Stage 4
├── proposal_plan.json   # Stages 3-4
├── proposal.pptx        # Stage 5
└── qa_report.md         # Stage 6  (+ qa_pptx.md)
```

## Stage 1 — Triage: what in this RFP is ours?

Skip this only when the input is already a CM-specific chapter. On anything larger it is
the stage that stops the bid answering the obvious chapter and missing the training
obligation buried in the service-levels annex.

Extract the document to text first — the `pdf` skill for a PDF, `docx` for Word — then:

```bash
python scripts/triage_rfp.py proposals/<run>/inputs/*.txt -o proposals/<run>/rfp_triage.json
```

It splits the tender on its own clause numbering, scores each section for CM relevance
against a published vocabulary, and prints two lists: the CM-relevant sections, and the
ones it set aside.

**Read both.** The set-aside list is the useful half — a section that appears in neither
list was never read at all, which is a different problem from one that was read and
dismissed. Scoring is literal term matching, exactly as explainable and exactly as
limited as `retrieve.py`: it is a shortlist, and a `not-cm` verdict on a section whose
heading looks interesting is a prompt to open it, not permission to skip it.

Two outputs deserve specific attention:

- **`deliverable_cues`** — sections containing "shall provide", "shall develop" and
  friends. These are where named deliverables live, and named deliverables drive Stage 3's
  sizing and naming.
- **`cross_references`** — other parts of the tender this one points at. Check we have
  each. A requirement we cannot answer because the annex was never sent is a clarification
  question, and the clarification deadline is usually weeks before submission.

Record the result in the brief's `cm_scope`, including `reviewed_and_excluded` and
`not_supplied`. The point of writing down what was excluded is that the decision becomes
reviewable.

## Stage 2 — Intake

Ask for, or locate, the inputs. At minimum the RFP itself; also ask what else exists
(briefing call notes, incumbent/history, named stakeholders, budget or day-rate guidance,
submission deadline and format rules). Then extract the CM-relevant sections into
`rfp_brief.json` against `schemas/rfp_brief.schema.json`. See
`reference/rfp-extraction.md` for what to look for and how to handle the things RFPs
habitually bury.

**Every requirement gets a stable ID** (`R1`, `R2`, …). These IDs are the spine of the
whole run — Stage 3 maps sections to them and Stage 6 checks none went unanswered.

**Every requirement also gets a `kind`**, because "answering" means different things:

| kind | What answering it means |
|---|---|
| `proposal-content` | The response describes something. A slide covers it. |
| `delivery-obligation` | We must do it after award. The deck commits to it, inside the relevant approach section. |
| `commercial-constraint` | A pricing or cost condition. Belongs in commercials. |
| `submission-rule` | Governs the response document itself — format, page limit, file naming. No slide covers it; Stage 6 checks the deck against it. |

Getting this wrong in the safe direction is cheap; getting it wrong the other way is not.
When unsure, mark it `proposal-content` so it must be covered.

Report back a short read of the brief before moving on: client, scope, how many
requirements extracted and of what kinds, the evaluation criteria and their weights if
stated, the deadline, and anything the RFP asks for that the knowledge bank plainly can't
cover. This is a transparency checkpoint, not a request for approval — continue straight
into Stage 3 unless the practitioner redirects.

### Confidence and gaps

Never invent a requirement the RFP doesn't state, and never soften one it does. Where the
RFP is ambiguous, record the requirement with `"confidence": "inferred"` and a note on
what's ambiguous. Where the RFP asks for something with no knowledge-bank coverage, that's
a `[GAP]` — it flows through to the deck as a visible placeholder, not a
plausible-sounding paragraph.

## Stage 3 — Section plan

Select and order the proposal's sections from the section library in
`reference/section-library.md`. That file carries each section's purpose, when to include
it, what evidence it needs, and its typical slide count.

Rules that matter more than the library itself:

1. **Follow the RFP's own structure when it dictates one.** Many RFPs prescribe a response
   format or a scoring schedule. If so, mirror it — the evaluators score against their
   structure, not ours. Note the deviation in the plan if we add anything beyond it.
2. **Use the client's naming convention, not the firm's.** The library's labels are
   internal handles, not slide titles. If the client asks for a "Change Sustenance Plan,"
   that is the section's name. Evaluators score by finding their own requirements, and a
   deliverable we have renamed reads as one we have not answered. Note the terminology
   trap: in a tender document "the Tenderer" is the *bidder* — this rule is about the
   *client's* words (the Authority, the Tenderee, the Purchaser).
3. **Size by evaluation weight where weights are published; by named deliverables where
   they are not.** Most CM tenders publish no weights — do not invent them. Instead, let
   the RFP's own emphasis do the sizing: a deliverable it names earns a slide, one it
   spends fourteen sub-clauses on earns several, one it never mentions earns none even if
   the canonical list carries it. Stage 1's per-section scores are a usable proxy for that
   emphasis.
4. **Every named deliverable gets a home**, whether or not the canonical list has a slot
   for it. Give it its own section or fold it into the nearest one and say so — never drop
   it for not fitting the template.
5. **Shape the approach to the delivery methodology.** Agile and waterfall programmes need
   genuinely different change plans — rolling versus one-off impact assessment,
   just-in-time versus pre-go-live training, release cadence versus stage gates. Read it
   from the RFP's vocabulary and mirror that vocabulary back. Getting this wrong reads as
   a template response. See Rule 3 in the section library for the full contrast.
6. **Every requirement ID that needs a slide maps to at least one section.** Build the map
   explicitly as you go; an unmapped requirement at the end of Stage 3 means the outline is
   wrong, not that the requirement is unimportant. `submission-rule` requirements are the
   exception — they constrain the document, not its contents.
7. **Keep it to the length the RFP allows.** Page/slide limits are a hard constraint, and
   over-length submissions get disqualified. If the plan won't fit, cut by evaluation
   weight where weights exist, otherwise by how little the RFP dwells on the deliverable —
   and say what you cut.

### Diagnostic methods in the approach sections

Methodology and approach sections often need to name the diagnostic methods we'd apply — a
structured delivery-risk review at phase gates, a read on whether the change is technical
or adaptive, a stakeholder-network analysis. Take these from the knowledge bank's
`methodology` entries like any other content, so they carry sources like any other content.

Two rules regardless of where a method comes from:

- **Reference them as *methods we would apply*, not as findings.** We haven't run anything
  on this client yet, and implying otherwise in a bid is a real problem.
- **If the practitioner wants an actual diagnostic run on the client's situation first**,
  that's separate work — run it, then feed its output in as a client input at Stage 2.

## Stage 4 — Knowledge-bank retrieval

The knowledge bank lives at `proposal-assets/knowledge-bank/` (or a path the practitioner
gives). Build or refresh its index, then retrieve per section:

```bash
python scripts/index_kb.py proposal-assets/knowledge-bank -o proposals/<run>/kb_index.json
python scripts/retrieve.py proposals/<run>/kb_index.json --section methodology --tags erp,workday --top 5
```

Six sections are available: `methodology`, `case-studies`, `credentials`, `team`,
`commercials`, `boilerplate`.

**Past tenders and past decks are not among them — they are documents, and they live in
Airtable** (`CM Knowledge Bank → Proposals and Tenders`). Nothing on a slide can cite a
PDF. When a tender resembles one we have bid before, open that record, download what it
holds, and run `ingest_source.py` to extract entries into the six sections above; carry
`bid.outcome` across as you go, because language from a losing bid reads exactly as well
as language from a winning one.

For each planned slide, pull candidate entries, choose what actually fits, and write the
slide into `proposal_plan.json` with its `sources` — the KB entry IDs the content came
from. Then adapt the content to this client: swap in their sector language, their system
names, their stated pain points. Adaptation is expected; fabrication is not.

**Provenance rule.** Every content block on every slide carries either a non-empty
`sources` array or a `[GAP]` marker. There is no third state. A slide body with neither is
a Stage 6 failure, and the practitioner has no way to tell an invented claim from a real
credential once it's in a deck.

Case studies and credentials are the highest-risk content here: client names, metrics, and
dates come from the KB entry verbatim or not at all. Never round a number up, never
generalise "reduced onboarding time by 22%" into "by around a quarter," and never attach a
real client's name to a result recorded against a different engagement. Check `clearance`
before naming any client and `metrics_verified` before quoting any number.

## Stage 5 — Build the deck

**Profile the template first.** This is what a plan is validated against, so a plan can
only ever reference layouts the template actually has:

```bash
python scripts/profile_template.py proposal-assets/templates/<firm>.potx \
    -o proposals/<run>/template_profile.json
```

Then render:

```bash
python scripts/render_pptx.py proposals/<run>/proposal_plan.json \
    proposal-assets/templates/<firm>.potx \
    --map proposal-assets/templates/template_map.json \
    -o proposals/<run>/proposal.pptx
```

The deck **is** the template: master, layouts, theme, fonts and table styles are carried
across untouched, and only slides are added. Content goes into the layout's own
placeholders, and slide XML sets no fonts and no colours — everything inherits. That is
what makes "built on the approved template" checkable rather than merely intended.

Three things the renderer will not do quietly, and they are the reason to use it rather
than assembling slides by hand:

- A block flagged `gap: true` becomes a **visible amber `[GAP]` panel**. Never substitute
  text, never a silent omission.
- Text that will not fit its placeholder is **reported and autofit-shrunk**, so it cannot
  clip away unseen. If the shrink hits its floor the run says so — that means cut content,
  not shrink further.
- Every slide's knowledge-bank source IDs go in the footer. Use `--sources hidden` only for
  a client-facing copy, once the practitioner has reviewed the provenance.

### If there is no approved template yet

Build on `proposal-assets/templates/pptx-generic/pptx-generic.potx` — a plain generated
stand-in with the same nine layouts and the same placeholder names, so nothing upstream
changes when the real template arrives.

**Say so at handover, every time.** It is not the firm's template, and a deck built on it
must never be presented as though it were. If the practitioner asks for a deck on the
firm's approved template and there isn't one, stop and ask for it rather than building an
approximation: "company-approved template" is that deliverable's whole requirement, and a
lookalike fails it.

`scripts/render_html.py` renders the same plan to a self-contained HTML deck on
`templates/html-generic` — useful for a quick look in a browser, or a PDF via `?print-pdf`.
It is a viewer, not the deliverable.

### When the renderer can't express a slide

Run `scripts/build_deck.py` to emit the build manifest and construct that one slide by hand
through the **`pptx` skill**, following its template workflow (unzip → edit
`ppt/slides/slideN.xml` → rezip, *not* `pptxgenjs`). Don't override the template's design:
the `pptx` skill's "Design Ideas" section is for decks built from nothing, and here the
template has already made those decisions. Never degrade the plan to fit the tooling.

## Stage 6 — QA

Two scripts, both required.

```bash
python scripts/qa_deck.py proposals/<run>/rfp_brief.json proposals/<run>/proposal_plan.json \
    -o proposals/<run>/qa_report.md
python scripts/qa_pptx.py proposals/<run>/proposal.pptx \
    --original proposal-assets/templates/<firm>.potx -o proposals/<run>/qa_pptx.md
```

`qa_deck.py` checks **requirement coverage** — every requirement that needs a slide maps to
one, with `submission-rule` requirements listed separately as a document checklist — and
**provenance**, that every content block has sources or a `[GAP]`. Mapping is necessary but
not sufficient: confirm each mapped slide's content actually answers the requirement rather
than merely mentioning the topic.

`qa_pptx.py` checks the file: package integrity, **template fidelity**, text overflow and
leftover scaffolding. Always pass `--original` — without it nothing confirms the template's
own master, layouts and theme were left alone, and that is the check that makes the
template claim true.

Then open the deck and look at it. The mechanical checks catch what is mechanical; they do
not catch a slide that is technically fine and says nothing.

Then deliver: the deck, both QA reports, and a plain statement of what's still open — the
`[GAP]`s, any uncovered requirement, anything cut for length, whether the deck is on the
firm's template or the stand-in, and the reminder that this is a draft for their review.

## Notes

- **The knowledge bank is the product.** A thin bank produces a deck full of `[GAP]`s, and
  that's the correct behaviour — it's telling the practitioner what the firm hasn't written
  down yet. Don't paper over a thin bank with generated filler; point them at
  `reference/knowledge-bank-guide.md` to add entries instead. The Stage 6 QA report, read
  another way, is a prioritised backlog for the bank.
- **Ingesting past material is a drafting aid, not a shortcut.** `scripts/ingest_source.py`
  turns a past deck or tender into a draft entry, marked `internal-only` with metrics
  unverified, so it cannot reach a bid until a human splits it, checks it, and clears it.
  Those defaults are inconvenient on purpose.
- Deadlines in RFPs are real. Surface the submission deadline early and mention it when you
  hand over the draft, especially if it's close. Surface the *clarification* deadline too —
  it is earlier, and Stage 1's unanswerable cross-references are what it exists for.
