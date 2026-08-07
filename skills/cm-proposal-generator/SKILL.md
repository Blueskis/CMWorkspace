---
name: cm-proposal-generator-v0.1
description: Generates a change-management proposal deck (.pptx) from an RFP and other client inputs, built on the firm's approved PowerPoint template and populated from a curated knowledge bank of methodology, case studies, credentials, team bios, and commercial boilerplate. Runs a five-stage pipeline — parse the RFP into a structured brief, plan the proposal sections against the client's stated requirements and evaluation criteria, retrieve matching knowledge-bank content, build the deck on the approved template, then QA it for requirement coverage and template fidelity. Use whenever a CM practitioner wants to draft, assemble, or respond to an RFP, ITT, RFI, or client brief with a proposal, pitch, or bid deck — phrases like "generate a proposal from this RFP", "draft a CM proposal", "respond to this tender", "build a pitch deck for this client", "we've been invited to bid". Do NOT use for diagnosing an existing change initiative — that's the strategic-change-assessment skill.
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
| The firm's approved `.potx`/`.pptx` template | Generating a template, or restyling an off-template deck |
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
2. **Weight slide count by evaluation criteria.** If "approach to stakeholder engagement"
   is 40% of the score, it gets more than one slide. If price is 10%, the commercials
   section stays short.
3. **Every requirement ID maps to at least one section.** Build the map explicitly as you
   go; an unmapped requirement at the end of Stage 2 means the outline is wrong, not that
   the requirement is unimportant.
4. **Keep it to the length the RFP allows.** Page/slide limits are a hard constraint, and
   over-length submissions get disqualified. If the plan won't fit, cut sections by
   evaluation weight — lowest weight goes first — and say what you cut.

### Framework integration

The proposal's methodology and approach sections should draw on this plugin's diagnostic
framework skills where the RFP gives grounds for it — e.g. citing a DICE-based delivery
risk review as part of the governance offer, or a technical-vs-adaptive read to justify
the shape of the engagement. Reference them as *methods we would apply*, not as findings:
we haven't run them on this client yet, and claiming otherwise in a bid is a real problem.
If the practitioner wants an actual diagnostic run on the client's situation first, invoke
`strategic-change-assessment-v1.0` and feed its output in as a client input.

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

Profile the approved template first — it tells you which layouts exist and what
placeholders each one has:

```bash
python scripts/profile_template.py proposal-assets/templates/<firm>.potx -o proposals/<run>/template_profile.json
```

Then invoke the **`pptx` skill** and follow its template workflow to build the deck. Two
non-negotiables specific to this skill:

- **Build from the approved template, never from scratch.** The deck must inherit the
  firm's master, theme, fonts, and colours. That means the unzip → edit
  `ppt/slides/slideN.xml` → rezip route the `pptx` skill documents for templates, *not*
  `pptxgenjs`. A visually similar deck built from scratch is not an approved-template
  deck, and someone will notice.
- **Don't override the template's design.** The `pptx` skill's "Design Ideas" section —
  palettes, motifs, typography — is for decks built from nothing. Here the firm's template
  has already made those decisions. Follow the template's own conventions and the layout
  mapping in `template_map.json`.

`scripts/build_deck.py` is the intended automation for the mechanical part of this
(duplicating layouts, filling placeholders from `proposal_plan.json`). See its docstring
for the current state — where it can't yet do a slide, do that slide by hand through the
`pptx` skill rather than degrading the plan to fit the script.

## Stage 5 — QA

Three checks, all required. Write results to `qa_report.md`.

**1. Requirement coverage.** Every requirement ID in `rfp_brief.json` appears against at
least one slide in `proposal_plan.json`, and that slide's content actually answers it —
mapping a requirement to a slide that merely mentions the topic is not coverage. Report
any uncovered ID explicitly; do not quietly drop it.

**2. Provenance and gaps.** Every content block has sources or a `[GAP]`. List every
`[GAP]` in the report as an action item for the practitioner, with what's missing and
which requirement it leaves exposed.

**3. Template fidelity and deck health.** Run the `pptx` skill's QA in full — content QA
(`markitdown`, including the placeholder-text grep), file QA
(`validate.py output.pptx --original <template>` — always pass `--original` for a
template-derived deck), and visual QA on the rendered slides. Additionally confirm no
slide has drifted off-template: fonts, colours, and layouts should all still be the
template's.

Then deliver: the deck, the QA report, and a plain statement of what's still open — the
`[GAP]`s, any uncovered requirement, anything cut for length, and the reminder that this
is a draft for their review.

## Notes

- **The knowledge bank is the product.** A thin bank produces a deck full of `[GAP]`s, and
  that's the correct behaviour — it's telling the practitioner what the firm hasn't
  written down yet. Don't paper over a thin bank with generated filler; point them at
  `reference/knowledge-bank-guide.md` to add entries instead.
- If there's no approved template available, stop and ask for one rather than building an
  approximation. "Company-approved template" is the whole requirement for this deliverable;
  a lookalike fails it.
- Deadlines in RFPs are real. Surface the submission deadline early and mention it when
  you hand over the draft, especially if it's close.
