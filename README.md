# CM Workspace

Change-management working tools, packaged as a Claude Code plugin.

| Skill | What it does |
|---|---|
| `cm-proposal-generator` | **v0.1 (MVP)** — RFP + client inputs → a CM proposal deck, populated from a knowledge bank |
| `cutover-comms-plan` | Delivery tool — builds a cutover communications plan workbook from complexity-based cadence rules |

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

skills/cutover-comms-plan/
├── SKILL.md              # cadence rules and the build process
├── assets/               # editable artifact (browser, exports .xlsx)
└── scripts/              # workbook builder
```

Scripts are stdlib-only and each runs standalone with `--help`.

## Cutover comms plan

`cutover-comms-plan` takes a description of a cutover and produces an Excel communications plan — one row per
comms, with Purpose, Audience, Channel, Sender, Owner, Approver and Dependencies,
plus a deliberately blank `Comms Content Link` column for later linkage to the
drafted content.

How many comms a cutover gets is rule-driven rather than guessed:

- **Brand-new system → 2** (pre go-live awareness, go-live)
- **Upgrade or change to an existing system → 5** (T-14, T-7, T-1, cutover begins, go-live)
- Decommission → 4; silent migration → 2
- Plus modifiers for downtime, required user action, external audiences, hypercare,
  multi-wave rollouts, long cutover windows, go/no-go gates, regulated contexts and
  training prerequisites — with a floor of 2 and a ceiling of 6 push comms per audience.

Two ways to build it:

- **`assets/cutover-comms-plan.html`** — an editable artifact. Applies the rules live,
  runs nine validation checks as you type, and exports to `.xlsx` in the browser with
  no library or server involved. Edits persist locally between sessions.
- **`scripts/build_comms_plan.py`** (requires `openpyxl`) — generates the same workbook
  from a JSON spec, or populates the member's own existing template, matching their
  column names by synonym and preserving their formatting.

The artifact's "Export spec JSON" produces exactly the spec the script consumes, so the
two compose: draft and edit in the browser, then push the result into a client template.

### Working against a client template

A client "template" is usually a *previous* cutover's completed plan, not a blank form,
so the script refuses to write into one that already has rows and makes you choose
`--append` or `--replace-rows`. It never writes into merged ranges, and only ever
appends columns — inserting them would shift values out from under the template's
merged cells, autofilter and dropdowns.

`--list-profiles` shows the built-in client formats (auto-detected from the headers). A
profile pins ambiguous columns, translates the plan into the client's own category and
status vocabulary, splits a multi-audience comms into one row per audience where that
format expects it, snaps generated wording onto the template's own strings so their
filters keep grouping, and flags any value with no precedent in the file. `eng-cutover`
covers cutover activity task lists, where comms are rows among other cutover activities.

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
