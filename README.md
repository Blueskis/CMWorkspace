# CM Workspace

Change-management working tools, packaged as a Claude Code plugin.

| Skill | What it does |
|---|---|
| `cm-proposal-generator` | **v0.1 (MVP)** — RFP + client inputs → a CM proposal deck, populated from a knowledge bank |
| `training-material-generator` | **v0.2 (MVP)** — an FSD (or similar spec doc) → a first-draft training deck, with placed screenshots, native diagrams, and knowledge-check questions |

## Proposal generator (v0.1, MVP)

Takes an RFP (plus briefing notes, stakeholder lists, whatever else the client sent) and
produces a first-draft change-management proposal deck, written from the firm's own
knowledge bank.

Five stages, each writing an inspectable artifact so a run can be resumed or audited from
any point:

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
build, then the `pptx` skill's template workflow executes it. Output is always a **draft
for practitioner review**, never a submission-ready document.

## Training material generator (v0.2, MVP)

Takes a functional specification document (or similar — a BRD, a process guide, system
documentation with screenshots) and produces a first-draft training deck on the client's
approved template: screenshots placed by the procedure step they illustrate, native
PowerPoint diagrams (process flows, swimlanes, decision trees, org hierarchies,
timelines) built from the spec's own prose logic, and knowledge-check questions derived
from — and cited back to — the spec.

Five stages, same discipline as the proposal generator — every stage writes an
inspectable artifact:

```
docs + template ─▶ source_map.json ─▶ training_brief.json ─▶ deck_plan.json ─▶ training.pptx ─▶ qa_report.md
      INTAKE            BRIEF               PLAN                 FILL + BUILD          QA
```

Two invariants enforced mechanically in Stage 5:

- **Provenance** — every content block traces to a source-document section or carries an
  explicit `[GAP]` marker.
- **Coverage, in both directions** — every learning objective reaches a content slide
  *and* a knowledge-check question, and every procedural section of the source document
  reaches a module or an explicit, reasoned exclusion. The document's own outline drives
  the module plan; retrieval only fills slides — top-k never decides what the course
  covers.

See `skills/training-material-generator/SKILL.md` for the full pipeline, and
`tests/run_tests.py` for a runnable check of the extraction, retrieval, diagram-rendering,
and QA logic against synthetic fixtures (`python tests/run_tests.py -v`).

### What v0.2 does not do

Multi-system curricula, audience-*filtered* decks (audiences are tagged now, filtering is
v0.3), scored/tracked assessments or LMS packaging, and automated cropping/upscaling of
extracted screenshots. Output is always a **draft for practitioner review**.

## Layout

```
skills/cm-proposal-generator/
├── SKILL.md              # the five-stage process
├── reference/            # section library, RFP extraction guide, KB guide
├── schemas/              # rfp_brief, proposal_plan, kb_entry contracts
└── scripts/              # index_kb, retrieve, build_deck, render_html, qa_deck
skills/training-material-generator/
├── SKILL.md              # the five-stage process
├── reference/            # module library, FSD extraction, screenshot placement,
│                         #   diagram patterns, knowledge-check quality rules
├── schemas/              # source_map, asset_index, training_brief, deck_plan,
│                         #   question_bank contracts
└── scripts/              # map_source, extract_assets, index_chunks, retrieve_chunks,
                          #   render_diagram, inject_slide_xml, build_training_deck,
                          #   qa_training
lib/                      # shared, stdlib-only — used by both skills
├── profile_template.py   # profiles a .potx/.pptx or HTML template's layouts/placeholders/theme
└── section_walk.py       # shared heading-stack walker, so a section_id means the same
                          #   thing across a skill's own outline and asset-index outputs
proposal-assets/
├── templates/
│   └── html-generic/     # PoC template: 9 layouts, theme, vendored reveal.js (MIT)
└── knowledge-bank/       # methodology, case-studies, credentials, team, commercials, boilerplate
examples/acme-erp/        # worked example — fictional client
tests/                    # unit tests for training-material-generator, against synthetic fixtures
```

Scripts are stdlib-only and each runs standalone with `--help`, except
`training-material-generator`'s `inject_slide_xml.py`, which uses `defusedxml` (falls back
to stdlib `xml.dom.minidom` with a warning if absent).

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
