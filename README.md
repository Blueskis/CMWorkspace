# CM Workspace

Change-management working tools, packaged as a Claude Code plugin.

| Skill | What it does |
|---|---|
| `cm-proposal-generator` | **v0.1 (MVP)** — RFP + client inputs → a CM proposal deck, populated from a knowledge bank |
| `readiness-insights-agent` | **v0.1 (MVP)** — training, comms and readiness feedback → an evidence-traced readiness brief, read against the programme timeline |

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

## Readiness insights agent (v0.1, MVP)

Compiles the feedback a programme already has — training evaluations (scores and
comments), comms channel feedback forms, change readiness assessments, pulse surveys —
into one readiness brief, and reads it against the programme calendar so every finding
carries a "by when" rather than just a score.

```
feedback files ─▶ signals.json ─▶ analysis.json ─▶ insights.json ─▶ qa_report.md ─▶ brief.html
    INGEST         + programme.json    ANALYSE       INTERPRET         AUDIT          RENDER
                      CONTEXT
```

Three invariants the audit stage enforces mechanically:

- **Evidence** — every insight cites signal IDs, analysis cells, or themes that resolve,
  or is flagged `[GAP]`. A theme needs at least two quotes.
- **Coverage** — every segment × dimension cell with no data or too thin a base is
  declared as a blind spot. Silence never renders as green, and a segment nobody surveyed
  is a finding rather than an absence.
- **Timing** — every insight is anchored to a real milestone with a remediation lead time.
  Where the action needs longer than remains, it is banded `too_late` and presented as a
  descope-or-delay decision, four weeks before the deadline rather than after it.

### Try it

A complete worked example ships in `examples/northwind-readiness/` — fictional programme,
generated responses:

```bash
python skills/readiness-insights-agent/scripts/analyze_quant.py \
    examples/northwind-readiness/signals.json \
    --programme examples/northwind-readiness/programme.json --markdown

python skills/readiness-insights-agent/scripts/qa_insights.py \
    examples/northwind-readiness/{signals,analysis,insights}.json \
    --programme examples/northwind-readiness/programme.json

python skills/readiness-insights-agent/scripts/render_brief.py \
    examples/northwind-readiness/{insights,analysis,programme}.json -o /tmp/nw/brief.html
```

915 signals, 5 segments, 7 insights, 9 declared blind spots, 1 `too_late` verdict. See
that folder's README for what each part demonstrates.

### What v0.1 does not do

Live survey-platform APIs, PDF report scraping, significance testing or driver analysis,
automatic topic modelling, and PowerPoint output. Ingest is CSV plus one adapter per
source; themes are written by the model over a listed worksheet, not clustered. Output is
always a **draft read for practitioner challenge** — the audit checks the sourcing, not
the judgement.

## Layout

```
skills/cm-proposal-generator/
├── SKILL.md              # the five-stage process
├── reference/            # section library, RFP extraction guide, KB guide
├── schemas/              # rfp_brief, proposal_plan, kb_entry contracts
└── scripts/              # index_kb, retrieve, profile_template, build_deck,
                          #   render_html, qa_deck
skills/readiness-insights-agent/
├── SKILL.md              # the six-stage process
├── reference/            # readiness dimensions, source adapters, insight-writing standard
├── schemas/              # signals, programme, insights contracts
└── scripts/              # ingest_feedback, analyze_quant, prepare_verbatims,
                          #   timeline_join, qa_insights, render_brief
proposal-assets/
├── templates/
│   └── html-generic/     # PoC template: 9 layouts, theme, vendored reveal.js (MIT)
└── knowledge-bank/       # methodology, case-studies, credentials, team, commercials, boilerplate
examples/acme-erp/        # worked example — fictional client
```

Scripts are stdlib-only and each runs standalone with `--help`.

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
