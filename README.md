# CM Workspace

Change-management working tools, packaged as a Claude Code plugin.

| Skill | What it does |
|---|---|
| `cm-proposal-generator` | **v0.1 (MVP)** — RFP + client inputs → a CM proposal deck, populated from a knowledge bank |
| `training-material-generator` | **v0.1 (MVP)** — an FSD + supporting documents → a first-draft system training deck |

Both run the same five-stage shape: every stage writes an inspectable artifact, so a run can
be resumed, audited or re-run from any point, and both enforce their guarantees
mechanically rather than by eye. Neither produces a finished document — the output is always
**a draft for a practitioner to review**.

## Proposal generator (v0.1, MVP)

Takes an RFP (plus briefing notes, stakeholder lists, whatever else the client sent) and
produces a first-draft change-management proposal deck, written from the firm's own
knowledge bank.

```
RFP + client inputs ─▶ rfp_brief.json ─▶ proposal_plan.json ─▶ proposal.html ─▶ qa_report.md
      INTAKE              PLAN + RETRIEVE          BUILD              QA
```

Stage 4 has two render targets off the same plan: a self-contained **HTML deck** on a
generic business template (the current default, for proof of concept) and a **.pptx** on
an approved PowerPoint template (the eventual target). Both validate against the same
template profile, so switching changes nothing upstream.

Two invariants the QA stage enforces mechanically, and the reason the intermediate
artifacts exist at all:

- **Provenance** — every content block traces to a knowledge-bank entry ID or carries an
  explicit `[GAP]` marker. There's no third state, so an invented claim can't hide among
  real credentials.
- **Coverage** — every requirement extracted from the RFP maps to a section, and an
  uncovered mandatory requirement fails the run rather than being quietly dropped.

### Try it

A complete worked example ships in `examples/acme-erp/` — fictional client, invented RFP:

```bash
python skills/cm-proposal-generator/scripts/render_html.py \
    examples/acme-erp/proposal_plan.json \
    proposal-assets/templates/html-generic -o /tmp/acme/proposal.html

python skills/cm-proposal-generator/scripts/qa_deck.py \
    examples/acme-erp/rfp_brief.json examples/acme-erp/proposal_plan.json \
    -o /tmp/acme/qa_report.md
```

12 slides, 8/8 requirements covered, 1 open `[GAP]`. See that folder's README for what
each part demonstrates.

### Setup before real use

1. **Fill the knowledge bank** at `proposal-assets/knowledge-bank/` — see the README
   there, and delete the `*-EXAMPLE.md` format exemplars so they can't be retrieved into a
   real bid. A thin bank produces a deck full of `[GAP]`s, which is correct behaviour: it
   reports what the firm hasn't written down yet.
2. **Drop the firm's approved template** into `proposal-assets/templates/` when switching
   off the PoC HTML renderer — see the README there. The skill will stop and ask rather
   than build a lookalike.

### What v0.1 does not do

Pricing calculation, multi-lot bids, semantic search over the bank (retrieval is literal
tag matching), and automated OOXML assembly — `build_deck.py` validates and sequences the
build, then the `pptx` skill's template workflow executes it.

## Training material generator (v0.1, MVP)

Takes a functional specification (plus configuration workbooks, process maps, status
matrices) and produces a first-draft system training deck: objectives, process context,
screenshot-led walkthroughs, business rules, diagrams, and a knowledge check closing every
module.

```
source documents ─▶ source_index.json ─▶ training_plan.json ─▶ training.html ─▶ qa_report.md
      INGEST            PLAN + AUTHOR             BUILD              QA
```

`.docx` and `.xlsx` are read directly — both are ZIPs of XML, so text, tables and images
come out with no dependencies and no re-encoding. Screenshots are extracted byte-identical
with their captions, headings and document position, which is what lets the Create PO
capture land on the Create PO slide rather than being guessed at.

Three invariants the QA stage enforces:

- **Provenance** — every content block cites a document anchor (`FSD#4.2@p17`) or carries an
  explicit `[GAP]`. Stricter than the proposal generator's, because the source is in the
  room: a business rule nobody can point at in the spec becomes a wrong transaction.
- **Coverage** — every learning objective is both taught by a module *and* tested by a
  question. An objective the deck teaches but never checks is one nobody finds out they
  missed.
- **Screenshot triage** — every screenshot the documents contain is placed on a slide or
  listed in `excluded_assets` with a reason. A capture cannot be silently dropped.

Knowledge checks are fixed at **five questions, mixing multiple-choice and True/False**,
with the answer, rationale and source anchor in the speaker notes. `--answers hidden`
renders a participant copy off the same plan.

Diagrams are stored as **Mermaid source** — reviewable in a diff, regenerable when the
process changes — rendered client-side in the HTML deck from a vendored `mermaid.min.js`,
and rasterised via `mermaid-cli` for the `.pptx` path.

### Try it

`examples/po-training/` is a complete run on an invented Purchase Order specification,
including the `.docx` and `.xlsx` that produced it:

```bash
python skills/training-material-generator/scripts/render_html.py \
    examples/po-training/training_plan.json \
    training-assets/templates/html-training -o /tmp/po/training.html

python skills/training-material-generator/scripts/qa_training.py \
    examples/po-training/source_index.json examples/po-training/training_plan.json \
    -o /tmp/po/qa_report.md
```

17 slides, 2 screenshots, 1 diagram, 2 knowledge checks, 5/5 objectives taught and tested,
1 open `[GAP]`. Regenerate the source documents and re-run the ingest with
`make_sample_fsd.py` and `ingest_docs.py` — see that folder's README.

To check the guarantees still hold after changing anything:

```bash
python skills/training-material-generator/scripts/selftest.py
```

It breaks the worked example one way at a time — an unattributed block, an untested
objective, a dropped screenshot, a malformed check, a citation that does not resolve — and
confirms the pipeline rejects each one.

### What v0.1 does not do

Audience curation (the schema records `audiences` on every module and slide, but the build
ignores it — that is the main v0.2 candidate), PDF image extraction, image cropping or
annotation burn-in, native editable PowerPoint diagram shapes, LMS/SCORM export, and
semantic search (retrieval is literal heading and keyword matching).

## Layout

```
skills/cm-proposal-generator/
├── SKILL.md              # the five-stage process
├── reference/            # section library, RFP extraction guide, KB guide
├── schemas/              # rfp_brief, proposal_plan, kb_entry contracts
└── scripts/              # index_kb, retrieve, profile_template, build_deck,
                          #   render_html, qa_deck
skills/training-material-generator/
├── SKILL.md              # the five-stage process
├── reference/            # module library, document extraction, image placement,
│                         #   diagram patterns, question writing
├── schemas/              # source_index, training_plan, knowledge_check contracts
└── scripts/              # ingest_docs, retrieve_source, profile_template, build_deck,
                          #   render_diagram, render_html, qa_training, selftest,
                          #   make_sample_fsd
lib/deckkit/              # shared: template profiling, plan→manifest sequencing,
                          #   the HTML template dialect
proposal-assets/
├── templates/html-generic/   # PoC template: 9 layouts, theme, vendored reveal.js (MIT)
└── knowledge-bank/           # methodology, case-studies, credentials, team, commercials
training-assets/
└── templates/html-training/  # PoC template: 14 layouts, theme, vendored reveal.js +
                              #   mermaid.js (both MIT)
examples/acme-erp/        # worked example — fictional client, invented RFP
examples/po-training/     # worked example — invented Purchase Order specification
```

Scripts are stdlib-only and each runs standalone with `--help`. `lib/deckkit/` holds the
parts both skills share, so a plan from either is validated against a template by the same
code and the two cannot drift apart.

## Installing on another machine

**Option A — direct install:** copy this folder to the other machine and point Claude Code
at it as a plugin source (a local path or a git remote).

**Option B — via the marketplace listing:** this folder includes
`.claude-plugin/marketplace.json`, so once pushed to a git repository others can run:

```
/plugin marketplace add <your-repo-url>
```

then install the `cm-workspace` plugin from that marketplace.

⚠️ **Caveat on `marketplace.json`**: it was built from general Claude Code plugin
conventions rather than a verified schema reference. Test the install on a second machine
(or a fresh Claude Code profile) before relying on it for distribution.
