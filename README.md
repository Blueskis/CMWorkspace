# CM Workspace

Change-management working tools, packaged as a Claude Code plugin.

| Skill | What it does |
|---|---|
| `cm-proposal-generator` | **v0.1 (MVP)** — RFP + client inputs → a CM proposal deck, populated from a knowledge bank |
| `cm-effort-estimator` | **v0.5** — scope drivers → a manday estimate, with an open-ended judgement layer for adjustments the drivers alone don't capture |

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

## Effort estimator (v0.5)

Sizes a change management pursuit in mandays, bottom-up from ten scope drivers (impacted
people, business units, sites, languages, deployment waves, programme duration, training
modules) through an itemised hours library of 53 catalogue deliverables and 189 costed
tasks. Reads an RFP the same way the proposal generator's Stage 1 does — in the browser,
nothing leaves it — and produces effort by workstream, by consultant rank, and average FTE.

**v0.5 adds an open-ended judgement layer.** A practitioner types what they know that the
estimate doesn't — "the Authority has no dedicated change lead", "three unions sit on the
impact assessment", "five onboarding waves, not two" — and the assistant proposes named,
reviewable adjustments to the drivers and lines the estimate already has, never a
free-floating multiplier bolted on top. Each proposal carries a rationale and a predicted
manday delta shown before anything moves; accept, reject or revert each individually, with
an exact, order-independent revert and a running audit trail. See
`skills/cm-effort-estimator/reference/judgement-layer.md` for the full mechanics, including
why the judgement layer is barred — in validation, not just by asking nicely — from ever
touching the hours library, rank mix or vocabulary, which are shared admin configuration
across every future pursuit rather than one pursuit's to change.

Ships as a single self-contained HTML file — no build, no server, opens straight from disk.

### Try it

```bash
node --test skills/cm-effort-estimator/tests/judgement.test.js
```

Then open `skills/cm-effort-estimator/estimator.html` in a browser. Two anonymised sample
RFPs are built in (a public-authority tender and a rail operator's depot maintenance
system) to exercise the scope-reading and judgement flow end to end without a real client
document.

### Placeholder norms

The hours library ships with defensible starting values, not the firm's calibrated
benchmarks — the same posture this repo already takes with the proposal generator's
`-EXAMPLE.md` knowledge-bank entries and its generic HTML template. Say so on handover
until the admin tab's past-project effort table has enough logged engagements to
recalibrate against.

## Layout

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

skills/cm-effort-estimator/
├── SKILL.md              # what it does, what it doesn't, the placeholder-norms caveat
├── estimator.html         # the whole tool — data, engine, judgement layer, UI
├── tests/                # node:test, sliced straight out of estimator.html
└── reference/
    └── judgement-layer.md  # the adjustment schema, validation, the admin-config boundary
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
