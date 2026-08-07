# Strategic Change

A Claude Code plugin bundling 12 change-management consulting framework skills plus a multi-framework assessment orchestrator, built for a Strategic Change presentation and consulting workflow.

## What's included

| Skill | Framework |
|---|---|
| `dice-framework` | BCG DICE |
| `technical-adaptive-change` | Heifetz Technical vs. Adaptive |
| `theory-e-o-change` | Beer & Nohria Theory E/O |
| `kotter-8-step` | Kotter's 8-Step Change Model |
| `persuasion-case-for-change` | Garvin & Roberto Four-Stage Persuasion |
| `tipping-point` | Gladwell's Tipping Point |
| `immunity-to-change` | Kegan & Lahey Immunity to Change |
| `six-steps-change` | Beer, Eisenstat & Spector Six Steps |
| `productive-distress` | Heifetz's Productive Zone of Disequilibrium |
| `critical-few-behaviours` | McKinsey Influence Model |
| `dual-operating-system` | Kotter's Dual Operating System (Accelerate) |
| `network-position` | Organizational network analysis / stakeholder mapping |
| `strategic-change-assessment` | Orchestrator — runs a project narrative through whichever of the above are suitable and synthesizes findings across them |
| `cm-proposal-generator` | **v0.1 (MVP)** — RFP + client inputs → a CM proposal deck built on the firm's approved template, populated from a knowledge bank |

Each framework skill's frontmatter `name:` field carries a `-v1.0` suffix (e.g. `dice-framework-v1.0`), marking this as the post-review baseline — all 12 framework skills were live-tested via the Skill tool before this bundle was packaged. `cm-proposal-generator` is at `-v0.1`; see below.

## Proposal generator (v0.1, MVP)

Takes an RFP (plus briefing notes, stakeholder lists, whatever else the client sent) and
produces a first-draft change-management proposal deck on the firm's approved PowerPoint
template, written from the firm's own knowledge bank.

Five stages, each writing an inspectable artifact so a run can be resumed or audited from
any point:

```
RFP + client inputs ─▶ rfp_brief.json ─▶ proposal_plan.json ─▶ proposal.html ─▶ qa_report.md
      INTAKE              PLAN + RETRIEVE          BUILD              QA
```

Stage 4 has two render targets off the same plan: a self-contained **HTML deck** on a
generic business template (the current default, for proof of concept) and a **.pptx** on
the firm's approved template (the eventual target). Both validate against the same
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

### Layout

```
skills/cm-proposal-generator/
├── SKILL.md              # the five-stage process
├── reference/            # section library, RFP extraction guide, KB guide
├── schemas/              # rfp_brief, proposal_plan, kb_entry contracts
└── scripts/              # index_kb, retrieve, profile_template, build_deck,
                          #   render_html, qa_deck
proposal-assets/
├── templates/
│   └── html-generic/     # PoC template: 9 layouts, theme, vendored reveal.js (MIT)
└── knowledge-bank/       # methodology, case-studies, credentials, team, commercials, boilerplate
examples/acme-erp/        # worked example — fictional client
```

Scripts are stdlib-only and each runs standalone with `--help`.

## Installing on another machine

**Option A — direct install (simplest):**
1. Copy this entire `strategic-change-plugin/` folder to the other machine.
2. Point Claude Code at it as a plugin source (e.g. a local path or a git remote once this folder is pushed to a repo) using whatever plugin-install command your Claude Code version provides.

**Option B — via the marketplace listing:**
This folder also includes `.claude-plugin/marketplace.json`, so once it's pushed to a git repository, others should be able to run something like:
```
/plugin marketplace add <your-repo-url>
```
then install the `strategic-change` plugin from that marketplace.

⚠️ **Caveat on `marketplace.json`**: this was built from general Claude Code plugin conventions and one real `plugin.json` example found locally — I did not have a verified `marketplace.json` reference to check the exact schema against in this environment. Before relying on this for distribution, test the install on a second machine (or a fresh Claude Code profile) and adjust the schema if it doesn't load as expected.

## Source project

Built in the "Strategic Change Project" working directory alongside reference PDFs (Kotter's *Leading Change*, *HBR's 10 Must Reads on Change Management*, Cameron & Green's *Making Sense of Change Management*, and *The Theory and Practice of Change Management*) used to ground each skill's framework background.
