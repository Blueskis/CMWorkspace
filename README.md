# CM Workspace

Change-management working tools, packaged as a Claude Code plugin.

| Skill | What it does |
|---|---|
| `cm-proposal-generator` | **v0.1 (MVP)** — RFP + client inputs → a CM proposal deck, populated from a knowledge bank |
| `cm-comms-generator` | **v0.1 (MVP)** — a change + a chosen channel → a comms draft, on the client's approved brand |

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
   real bid or a real staff email. A thin bank produces output full of `[GAP]`s, which is
   correct behaviour: it reports what the firm hasn't written down yet.
2. **Drop the firm's approved template** into `proposal-assets/templates/` when switching
   off the PoC HTML renderer — see the README there. The skill will stop and ask rather
   than build a lookalike.
3. **Author a brand profile per client** in `proposal-assets/brand-profiles/` before drafting
   any comms — palette, voice, and channel specs. `apply_brand.py` and `qa_comms.py` both
   refuse a profile with no named approver.
4. **Always pass `--strict-section`** when retrieving. The bank is shared between both skills
   and the section is the only thing keeping a past staff email out of a live bid.

### What v0.1 does not do

Pricing calculation, multi-lot bids, semantic search over the bank (retrieval is literal
tag matching), and automated OOXML assembly — `build_deck.py` validates and sequences the
build, then the `pptx` skill's template workflow executes it. Output is always a **draft
for practitioner review**, never a submission-ready document.

## Comms generator (v0.1, MVP)

Takes a change — what's changing, who it affects, when, what they must do — plus the client's
approved brand, and produces a first-draft communication for one requested channel: **email**,
**SharePoint banner**, **slide deck**, or **short-form video outline**.

Four stages, and two of the artifacts are reusable assets rather than per-run output:

```
change inputs ─▶ change_brief.json ──┐
                                     ├─▶ comms_plan.json ─▶ draft.md (+ deck.html) ─▶ qa_report.md
client brand  ─▶ brand_profile.json ─┘
   INTAKE / BRAND                          DRAFT                                          QA
```

The brief is authored **once per change** and the brand profile **once per client**; only the
draft and QA stages repeat per channel. That is what stops two channels disagreeing about a
go-live date.

Provenance works differently here than in a bid, and it is the thing most likely to look like a
bug. A comms draft is new writing about a new change, so most copy has no knowledge-bank
ancestor. There are **three** valid states, not two: a knowledge-bank entry ID, a `brief:`
reference into the change brief, or an explicit `[GAP]`. Dangling `brief:` references fail the
run, so the third state cannot become a loophole.

Coverage is computed against the run's **target audiences**, so a single-audience email is not
failed for omitting messages aimed at a different segment.

The slide-deck channel reuses `cm-proposal-generator`'s renderer **unmodified** — a comms deck
plan is written in the same shape — with `apply_brand.py` recolouring the PoC template to the
client's palette first, refusing any palette that fails the WCAG contrast floor.

### Try it

```bash
python skills/cm-comms-generator/scripts/render_markdown.py \
    examples/northwind-payroll/email/comms_plan.json \
    --brand examples/northwind-payroll/brand_profile.json -o /tmp/nw/email/draft.md

python skills/cm-comms-generator/scripts/qa_comms.py \
    examples/northwind-payroll/change_brief.json \
    examples/northwind-payroll/email/comms_plan.json \
    --brand examples/northwind-payroll/brand_profile.json -o /tmp/nw/email/qa_report.md

python skills/cm-comms-generator/scripts/apply_brand.py \
    examples/northwind-payroll/brand_profile.json \
    proposal-assets/templates/html-generic -o /tmp/nw/deck/template

python skills/cm-proposal-generator/scripts/render_html.py \
    examples/northwind-payroll/deck/comms_plan.json \
    /tmp/nw/deck/template -o /tmp/nw/deck/deck.html
```

One brief, two channels: a 10-part email to all colleagues and a 9-slide manager cascade deck.
One honest `[GAP]` in each. See that folder's README for what each part demonstrates and the
nine negative tests.

### What v0.1 does not do

A sequenced multi-channel campaign, channels beyond the four, a sendable email or a built
banner image, a `.pptx` on the client's own template, or any judgement about whether the tone
lands. Output is always a **draft for practitioner review**, never an approved send.

## Layout

```
skills/cm-proposal-generator/
├── SKILL.md              # the five-stage process
├── reference/            # section library, RFP extraction guide, KB guide
├── schemas/              # rfp_brief, proposal_plan, kb_entry contracts
└── scripts/              # index_kb, retrieve, profile_template, build_deck,
                          #   render_html, qa_deck
skills/cm-comms-generator/
├── SKILL.md              # the four-stage process
├── reference/            # channel library, change intake, brand profile guide
├── schemas/              # change_brief, brand_profile, comms_plan contracts
└── scripts/              # render_markdown, apply_brand, qa_comms
proposal-assets/          # shared asset root (named for the first skill that used it)
├── templates/
│   └── html-generic/     # PoC template: 9 layouts, theme, vendored reveal.js (MIT)
├── brand-profiles/       # one approved brand profile per client
└── knowledge-bank/       # methodology, case-studies, credentials, team, commercials,
                          #   boilerplate, comms-collateral, comms-tone, comms-boilerplate
examples/acme-erp/        # worked example — proposal, fictional client
examples/northwind-payroll/  # worked example — comms, fictional client, two channels
```

The comms skill adds only three scripts. Indexing, retrieval, template profiling, deck
validation and HTML rendering are all reused from `cm-proposal-generator` unchanged.

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
