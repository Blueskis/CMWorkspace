# CM Workspace

Change-management working tools, packaged as a Claude Code plugin.

| Skill | What it does |
|---|---|
| `cm-proposal-generator` | **v0.1 (MVP)** — RFP + client inputs → a CM proposal deck, populated from a knowledge bank |
| `cm-comms-generator` | **v0.2** — a change + a chosen channel → a comms draft, routed to the tool that builds it (.docx / .pptx / Canva) |

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

### What v0.1 does not do

Pricing calculation, multi-lot bids, semantic search over the bank (retrieval is literal
tag matching), and automated OOXML assembly — `build_deck.py` validates and sequences the
build, then the `pptx` skill's template workflow executes it. Output is always a **draft
for practitioner review**, never a submission-ready document.

## Comms generator (v0.2)

Takes a change — what's changing, who it affects, when, what they must do — plus the client's
approved brand, produces a first-draft communication for one channel, and **routes it to the
tool that actually builds the artifact**.

| Channel | Builds as | Producer | Status |
|---|---|---|---|
| `email`, `article` | `.docx` | `docx` skill | live |
| `briefing_deck` | `.pptx` | `pptx` skill | live |
| `newsletter`, `banner` | Canva design | Canva MCP | needs the connector authorized |
| `short_form_video` | scene spec + captions | ElevenLabs MCP | planned, v0.3 |
| `explainer_video` | scene spec + captions | ElevenLabs MCP (narration only) | planned, v0.3 |

```
change inputs ─▶ change_brief.json ──┐
                                     ├─▶ comms_plan.json ─▶ draft.md ─▶ qa_report.md ─▶ route ─▶ artifact
client brand  ─▶ brand_profile.json ─┘
   INTAKE / BRAND                          PLAN (3a)         QA (4)      ROUTE (3b)
```

The brief is authored **once per change** and the brand profile **once per client**; only the
plan, QA and routing stages repeat per channel. That is what stops two channels disagreeing
about a go-live date.

**QA gates production.** `route_channel.py` re-runs the audit itself and emits no production
route while a hard failure stands — production is where a comm becomes expensive and externally
visible, and the plan is where defects are cheap.

**An unreachable producer is not a failed run.** When Canva is unauthorized or a video lane has
no connector, the run exits 0 and the handoff artifact — a design brief with per-field copy, or
a video spec with scene timing and captions — *is* the deliverable. The routing table lives in
`schemas/channel_registry.json` as data, so a channel whose producer does not exist yet is a
declared, supported state rather than a TODO.

**Copy and design are approved separately.** `design_provenance` records when a tool invented
the layout — a generated Canva design, a from-scratch deck. QA can pass the copy while the
design still needs client sign-off, and the handover says so.

Provenance has **three** valid states, not the proposal generator's two: a knowledge-bank entry
ID, a `brief:` reference into the change brief, or an explicit `[GAP]`. Dangling `brief:`
references fail the run, so the third state cannot become a loophole. Coverage is computed
against the run's target audiences, and against the channel's `coverage_mode` — a banner is a
signpost, not a full comm, and is scored as one.

### Try it

```bash
python skills/cm-comms-generator/scripts/route_channel.py --list

python skills/cm-comms-generator/scripts/qa_comms.py \
    examples/northwind-payroll/change_brief.json \
    examples/northwind-payroll/email/comms_plan.json \
    --brand examples/northwind-payroll/brand_profile.json -o /tmp/nw/qa.md

python skills/cm-comms-generator/scripts/build_docx.py \
    examples/northwind-payroll/email/comms_plan.json \
    --brand examples/northwind-payroll/brand_profile.json -o /tmp/nw/email
NODE_PATH="$(npm root -g)" node /tmp/nw/email/build.js
python skills/cm-comms-generator/scripts/verify_docx.py /tmp/nw/email/draft.docx \
    --plan examples/northwind-payroll/email/comms_plan.json \
    --brief examples/northwind-payroll/change_brief.json
```

One brief, five channel runs, four different producers. See that folder's README for what each
demonstrates and the seventeen negative tests. The `.docx` builds need `npm install -g docx`.

### What v0.2 does not do

A sequenced multi-channel campaign, channels beyond the seven, sending or publishing anything,
a rendered video, or any judgement about whether the tone lands. Output is always a **draft for
practitioner review**, never an approved send — and a design a tool generated is never a design
the client has approved.

## Self-serve: from the artifact, without copying a prompt

The comms console artifact (`comms-console.html`) lets a practitioner describe a change, pick
channels, and submit — but a published artifact runs in a sandboxed browser page with no way to
execute Python, so submitting still needs somewhere to send the work. Two ways to get there,
in order of setup effort:

1. **Generate in the artifact, via Gamma** — the console now drafts email, article, newsletter
   and briefing decks straight through the viewer's own **Gamma** connector. Nothing to deploy:
   Gamma is hosted, the viewer adds it once in claude.ai, and the deck lane exports to `.pptx`.
   **Email comes back as a real `.docx`**: the page walks Gamma's content tree and packages it
   with docx-js — the same library `build_docx.py` drives — then hands it over through the
   `downloads` capability, so the channel keeps the `.docx` format the registry specifies.
   **But Gamma writes the copy**, so those drafts have no QA gate and no provenance — in testing
   it invented a portal URL that was never in the input. Treat them as fast first drafts to
   react to, never as checked comms.

2. **Install the plugin** — `/plugin marketplace add <this-repo-url>` then install
   `cm-workspace`, and run the pipeline by describing the change to Claude directly. No
   artifact, no server, no shared API key. This works today with nothing built.

If Gamma isn't connected, the artifact degrades to a copy/paste request block — route (2) with
extra steps, but inside the same page. `service/` (the `cm-comms` MCP server) is still in the
tree and still the only route that puts the **checked** pipeline behind the page: deploy it and
the artifact can be pointed back at it. It is correct, verified-booting code; it simply has
never been hosted.

## Setup before real use

Shared by both skills.

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

## Layout

```
skills/cm-proposal-generator/
├── SKILL.md              # the five-stage process
├── reference/            # section library, RFP extraction guide, KB guide
├── schemas/              # rfp_brief, proposal_plan, kb_entry contracts
└── scripts/              # index_kb, retrieve, profile_template, build_deck,
                          #   render_html, qa_deck
skills/cm-comms-generator/
├── SKILL.md              # the four-stage process, with routed production
├── reference/            # channel library, routing, change intake, brand profile guide
├── schemas/              # change_brief, brand_profile, comms_plan, channel_registry
└── scripts/              # render_markdown, route_channel, qa_comms, apply_brand,
                          #   build_docx, build_pptx, verify_docx, canva_brief, video_spec
proposal-assets/          # shared asset root (named for the first skill that used it)
├── templates/
│   └── html-generic/     # PoC template: 9 layouts, theme, vendored reveal.js (MIT)
├── brand-profiles/       # one approved brand profile per client
└── knowledge-bank/       # methodology, case-studies, credentials, team, commercials,
                          #   boilerplate, comms-collateral, comms-tone, comms-boilerplate
examples/acme-erp/        # worked example — proposal, fictional client
examples/northwind-payroll/  # worked example — comms, fictional client, five channels
```

Indexing, retrieval, template profiling and deck validation are reused from
`cm-proposal-generator` unchanged — `profile_template.py` and `build_deck.py` validate a comms
deck plan against a client `.potx` exactly as they do a bid. `render_html.py` is no longer part
of the comms path, and is untouched.

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
