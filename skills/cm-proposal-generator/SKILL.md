---
name: cm-proposal-generator-v0.1
description: Generates a change-management proposal deck from an RFP and other client inputs, built on an approved slide template and populated from a curated knowledge bank of methodology, case studies, credentials, team bios, and commercial boilerplate. Runs a five-stage pipeline — parse the RFP into a structured brief, plan the proposal sections against the client's stated requirements and evaluation criteria, retrieve matching knowledge-bank content, build the deck on the template, then QA it for requirement coverage and template fidelity. Use whenever a CM practitioner wants to draft, assemble, or respond to an RFP, ITT, RFI, or client brief with a proposal, pitch, or bid deck — phrases like "generate a proposal from this RFP", "draft a CM proposal", "respond to this tender", "build a pitch deck for this client", "we've been invited to bid". Do NOT use for diagnosing or assessing an existing change initiative — this skill writes bids, it does not analyse programmes.
---

# CM Proposal Generator

Turns an RFP (plus whatever else the client gave us — briefing notes, incumbent
context, stakeholder lists, budget guidance) into a client-ready change-management
proposal deck, built on the firm's approved template and written from the firm's own
knowledge bank rather than invented from scratch.

**The point of this skill is provenance and coverage, not prose.** Anyone can write a
proposal deck. What makes this useful to a practitioner is that (a) every claim traces
back to a knowledge-bank entry or an explicit `[GAP]` flag, and (b) every requirement in
the RFP is provably answered somewhere in the deck. Both are checked in Stage 5, and
neither is optional.

## MVP scope (read this before promising anything)

This is v0.1. What it does and does not do:

| In scope | Out of scope (v0.1) |
|---|---|
| One deck, one client, one RFP per run | Multi-lot / multi-workstream bids split across decks |
| Sections from the section library below | Free-form custom sections invented per bid |
| Knowledge-bank retrieval by section + tag match | Semantic/embedding search over the bank |
| A self-contained HTML deck on a generic business template (PoC default), or the firm's approved `.potx` | Generating a template, or restyling an off-template deck |
| Requirement-coverage and provenance QA | Pricing calculation, resourcing models, legal review |
| A draft for the practitioner to edit | A submission-ready final document |

Always hand the output over as **a first draft for the practitioner to review**, never
as a finished submission. Say so explicitly when you deliver it.

## Pipeline

```
  Stage 1  INTAKE      RFP + client inputs ──▶ rfp_brief.json
  Stage 2  PLAN        rfp_brief + section library ──▶ proposal_outline (in plan)
  Stage 3  RETRIEVE    kb_index + outline ──▶ proposal_plan.json  (content + sources)
  Stage 4  BUILD       proposal_plan + template_profile ──▶ proposal.pptx
  Stage 5  QA          coverage + provenance + template fidelity ──▶ deliver
```

Each stage writes a file to the run workspace, so a run can be resumed, inspected, or
re-run from any stage without redoing the ones before it. Never skip straight from an RFP
to a deck — the intermediate artifacts are what make the output auditable.

### Run workspace

Create `proposals/<client-slug>-<YYYYMMDD>/` in the user's current working directory:

```
proposals/acme-20260807/
├── inputs/              # copies of the RFP and any client inputs
├── rfp_brief.json       # Stage 1
├── proposal_plan.json   # Stages 2-3
├── proposal.pptx        # Stage 4
└── qa_report.md         # Stage 5
```

## Stage 1 — Intake

Ask for, or locate, the inputs. At minimum the RFP itself; also ask what else exists
(briefing call notes, incumbent/history, named stakeholders, budget or day-rate guidance,
submission deadline and format rules).

Parse each input with the appropriate skill — `pdf` for PDFs, `docx` for Word,
`xlsx` for spreadsheets, plain read for text. Then extract into `rfp_brief.json`
against `schemas/rfp_brief.schema.json`. See `reference/rfp-extraction.md` for what to
look for and how to handle the things RFPs habitually bury.

**Every requirement gets a stable ID** (`R1`, `R2`, …). These IDs are the spine of the
whole run — Stage 2 maps sections to them and Stage 5 checks none went unanswered.

Report back a short read of the brief before moving on: client, scope, how many
requirements extracted, the evaluation criteria and their weights if stated, the
deadline, and anything the RFP asks for that the knowledge bank plainly can't cover.
This is a transparency checkpoint, not a request for approval — continue straight into
Stage 2 unless the practitioner redirects.

### Confidence and gaps

Never invent a requirement the RFP doesn't state, and never soften one it does. Where the
RFP is ambiguous, record the requirement with `"confidence": "inferred"` and a note on
what's ambiguous. Where the RFP asks for something with no knowledge-bank coverage,
that's a `[GAP]` — it flows through to the deck as a visible placeholder, not a
plausible-sounding paragraph.

## Stage 2 — Section plan

Select and order the proposal's sections from the section library in
`reference/section-library.md`. That file carries each section's purpose, when to include
it, what evidence it needs, and its typical slide count.

Rules that matter more than the library itself:

1. **Follow the RFP's own structure when it dictates one.** Many RFPs prescribe a response
   format or a scoring schedule. If so, mirror it — the evaluators score against their
   structure, not ours. Note the deviation in the plan if we add anything beyond it.
2. **Name each section the way this tender names the deliverable.** The library's labels
   are internal handles, not slide titles. If the RFP asks for a "Change Sustenance Plan,"
   that is the section's name. Evaluators score by finding their requirements, and a
   renamed deliverable reads as a missing one.
3. **Size by evaluation weight where weights are published; by named deliverables where
   they are not.** Most CM tenders publish no weights — do not invent them. Instead, let
   the RFP's own emphasis do the sizing: a deliverable it names earns a slide, one it
   spends fourteen sub-clauses on earns several, one it never mentions earns none even if
   the canonical list carries it.
4. **Every named deliverable gets a home**, whether or not the canonical list has a slot
   for it. Give it its own section or fold it into the nearest one and say so — never drop
   it for not fitting the template.
5. **Shape the approach to the delivery methodology.** Agile and waterfall programmes need
   genuinely different change plans — rolling versus one-off impact assessment, just-in-time
   versus pre-go-live training, release cadence versus stage gates. Read it from the RFP's
   vocabulary and mirror that vocabulary back. Getting this wrong reads as a template
   response. See Rule 3 in the section library for the full contrast.
6. **Every requirement ID maps to at least one section.** Build the map explicitly as you
   go; an unmapped requirement at the end of Stage 2 means the outline is wrong, not that
   the requirement is unimportant.
7. **Keep it to the length the RFP allows.** Page/slide limits are a hard constraint, and
   over-length submissions get disqualified. If the plan won't fit, cut by evaluation
   weight where weights exist, otherwise by how little the RFP dwells on the deliverable —
   and say what you cut.

### Diagnostic methods in the approach sections

Methodology and approach sections often need to name the diagnostic methods we'd apply —
a structured delivery-risk review at phase gates, a read on whether the change is
technical or adaptive, a stakeholder-network analysis. Take these from the knowledge
bank's `methodology` entries like any other content, so they carry sources like any other
content.

Two rules regardless of where a method comes from:

- **Reference them as *methods we would apply*, not as findings.** We haven't run anything
  on this client yet, and implying otherwise in a bid is a real problem.
- **If the practitioner wants an actual diagnostic run on the client's situation first**,
  that's separate work — run it, then feed its output in as a client input at Stage 1.

## Stage 3 — Knowledge-bank retrieval

The knowledge bank lives at `proposal-assets/knowledge-bank/` (or a path the practitioner
gives). Build or refresh its index, then retrieve per section:

```bash
python scripts/index_kb.py proposal-assets/knowledge-bank -o proposals/<run>/kb_index.json
python scripts/retrieve.py proposals/<run>/kb_index.json --section methodology --tags erp,workday --top 5
```

For each planned slide, pull candidate entries, choose what actually fits, and write the
slide into `proposal_plan.json` with its `sources` — the KB entry IDs the content came
from. Then adapt the content to this client: swap in their sector language, their system
names, their stated pain points. Adaptation is expected; fabrication is not.

**Provenance rule.** Every content block on every slide carries either a non-empty
`sources` array or a `[GAP]` marker. There is no third state. A slide body with neither is
a Stage 5 failure, and the practitioner has no way to tell an invented claim from a real
credential once it's in a deck.

Case studies and credentials are the highest-risk content here: client names, metrics, and
dates come from the KB entry verbatim or not at all. Never round a number up, never
generalise "reduced onboarding time by 22%" into "by around a quarter," and never attach a
real client's name to a result recorded against a different engagement.

## Stage 4 — Build the deck

Two render targets. Both consume the same `proposal_plan.json` and are validated against
the same template profile, so switching between them changes nothing upstream.

**Profile the template first**, whichever kind it is — this is what a plan gets validated
against, so a plan can only ever reference layouts the template actually has:

```bash
# HTML template (a directory)
python scripts/profile_template.py proposal-assets/templates/html-generic/ \
    -o proposal-assets/templates/html-generic/template_profile.json

# PowerPoint template (a file)
python scripts/profile_template.py proposal-assets/templates/<firm>.potx \
    -o proposals/<run>/template_profile.json
```

### 4a. HTML deck — the current default

```bash
python scripts/render_html.py proposals/<run>/proposal_plan.json \
    proposal-assets/templates/html-generic -o proposals/<run>/proposal.html
```

Produces one self-contained `.html` (CSS and JS inlined, no network, no server) that opens
from disk. Arrow keys or space to advance; append `?print-pdf` to the URL and print to get
a paginated PDF.

The renderer refuses to paper over the plan's invariants: a `gap: true` block renders as a
visible amber `[GAP]` panel, never as substitute text, and each slide's knowledge-bank
source IDs render in the footer by default. Use `--sources hidden` only for a client-facing
copy, once the practitioner has reviewed the provenance.

**This is a proof-of-concept renderer on a generic business template, not the firm's
approved one.** Say so when handing over. If the RFP mandates a file format — most do, and
it is usually PDF — the HTML has to be printed to that format before it is submittable.

Layouts live in `proposal-assets/templates/html-generic/layouts.html` and styling in
`theme.css`. Both are editable without touching Python; re-run `profile_template.py` after
changing layouts so the profile stays in step.

### 4b. PowerPoint deck — the eventual target

Run `scripts/build_deck.py` to validate and sequence the plan into a build manifest, then
invoke the **`pptx` skill** and follow its template workflow. Two non-negotiables:

- **Build from the approved template, never from scratch.** The deck must inherit the
  firm's master, theme, fonts, and colours. That means the unzip → edit
  `ppt/slides/slideN.xml` → rezip route the `pptx` skill documents for templates, *not*
  `pptxgenjs`. A visually similar deck built from scratch is not an approved-template
  deck, and someone will notice.
- **Don't override the template's design.** The `pptx` skill's "Design Ideas" section —
  palettes, motifs, typography — is for decks built from nothing. Here the firm's template
  has already made those decisions. Follow the template's own conventions and the layout
  mapping in `template_map.json`.

Where the manifest can't express a slide, build that slide by hand through the `pptx`
skill rather than degrading the plan to fit the script.

## Stage 5 — QA

Three checks, all required. Write results to `qa_report.md`.

**1. Requirement coverage.** Every requirement ID in `rfp_brief.json` appears against at
least one slide in `proposal_plan.json`, and that slide's content actually answers it —
mapping a requirement to a slide that merely mentions the topic is not coverage. Report
any uncovered ID explicitly; do not quietly drop it.

**2. Provenance and gaps.** Every content block has sources or a `[GAP]`. List every
`[GAP]` in the report as an action item for the practitioner, with what's missing and
which requirement it leaves exposed.

**3. Deck health.** `qa_deck.py` prints the right checklist for whichever render target
the plan used.

For the **HTML** deck, open it and step through every slide. Text overflow is the defect
to hunt first: `.slide-body` clips rather than spilling, so an overflowing slide drops
content silently rather than visibly. Case-study slides carry the most text and overflow
first.

For the **.pptx** deck, run the `pptx` skill's QA in full — content QA (`markitdown`,
including the placeholder-text grep), file QA (`validate.py output.pptx --original
<template>` — always pass `--original` for a template-derived deck), and visual QA on the
rendered slides. Additionally confirm no slide has drifted off-template: fonts, colours,
and layouts should all still be the template's.

Then deliver: the deck, the QA report, and a plain statement of what's still open — the
`[GAP]`s, any uncovered requirement, anything cut for length, and the reminder that this
is a draft for their review.

## Notes

- **The knowledge bank is the product.** A thin bank produces a deck full of `[GAP]`s, and
  that's the correct behaviour — it's telling the practitioner what the firm hasn't
  written down yet. Don't paper over a thin bank with generated filler; point them at
  `reference/knowledge-bank-guide.md` to add entries instead.
- **The HTML template is a stand-in, and saying so is part of the handover.** It exists so
  the pipeline can be exercised before the firm's approved template is available. Once
  that template exists, profile it and switch to the `.pptx` path — nothing upstream of
  Stage 4 changes. Never present an HTML deck built on the generic template as though it
  were on the firm's template.
- If the practitioner asks for a `.pptx` and there's no approved template available, stop
  and ask for one rather than building an approximation. "Company-approved template" is
  the whole requirement for that deliverable; a lookalike fails it.
- Deadlines in RFPs are real. Surface the submission deadline early and mention it when
  you hand over the draft, especially if it's close.
