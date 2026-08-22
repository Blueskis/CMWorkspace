# CM Workspace

Change-management working tools, packaged as a Claude Code plugin.

| Skill | What it does |
|---|---|
| `cm-proposal-generator` | **v0.1 (MVP)** — RFP + client inputs → a CM proposal deck, populated from a knowledge bank |
| `status-update-agent` | **v0.1 (MVP)** — last week's documents vs. this week's → the status update for the cadence meeting |

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

## Status update agent (v0.1, MVP)

Takes the recurring programme documents a consultant already has — a CM plan in Word, a
training-completion tracker in Excel, a RICEFWA status deck in PowerPoint — in this week's
version and last week's, and drafts the update they'll deliver at the weekly cadence.

Five stages, each writing an inspectable artifact:

```
week N-1 + week N docs ─▶ snapshots ─▶ changes ─▶ change_brief ─▶ status_update.md ─▶ qa_report.md
       EXTRACT              DIFF       MERGE          WRITE               QA
```

Every format normalises into one snapshot shape, so the diff never branches on document
type. Matching is by item key first — an activity ID, a learner, a RICEFWA object — then by
similarity, so a renamed activity reads as a rename rather than a deletion plus an addition.

Two invariants the QA stage enforces mechanically:

- **Attribution** — every claim in the update carries a `[C#]` citation with a specific
  before and after, or an explicit `[JUDGEMENT]` marker. There's no third state, so an
  invented movement can't hide among real ones, and the consultant's interpretation stays
  visibly distinct from the tracker's contents.
- **Coverage** — every high-materiality change is mentioned or explicitly waived with a
  recorded reason. Silence fails the run.

Stages 1, 2, 3 and 5 are deterministic scripts. Stage 4 — the writing — is the only stage
the model does, which is the only stage worth a person's judgement.

### Try it

A complete worked example ships in `examples/weekly-status/` — fictional programme, invented
data, real `.docx`/`.xlsx`/`.pptx` inputs:

```bash
cd examples/weekly-status
python ../../skills/status-update-agent/scripts/write_update.py run/changes/*.json \
    -o /tmp/brief.json --md /tmp/brief.md

python ../../skills/status-update-agent/scripts/qa_update.py \
    /tmp/brief.json run/status_update.md -o /tmp/qa_report.md
```

35 changes across three documents, 3 rated high, QA passing with 6 changes explicitly
waived. That folder's README has the full pipeline and what each part demonstrates.

### What v0.1 does not do

PDFs and legacy `.doc`/`.xls`/`.ppt`, live sources (Jira, Smartsheet, Google), trends across
more than two periods, and anything carried by formatting rather than text — cell colour as
RAG, charts, tracked changes, speaker notes. Output is always a **draft for the consultant
to review before the meeting**, never a client-ready readout.


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
skills/status-update-agent/
├── SKILL.md              # the five-stage process
├── reference/            # extraction/keying guide, materiality rules, narrative patterns
├── schemas/              # snapshot, changes, change_brief contracts
└── scripts/              # extract, diff_snapshots, write_update, qa_update
examples/acme-erp/        # worked example — fictional client
examples/weekly-status/   # worked example — fictional programme, three documents, two weeks
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
