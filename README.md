# CM Workspace

Change-management working tools, packaged as a Claude Code plugin.

| Skill | What it does |
|---|---|
| `cm-proposal-generator` | **v0.1 (MVP)** — RFP + client inputs → a CM proposal deck, populated from a knowledge bank |
| `cm-comms-generator` | **v0.1 (scaffold)** — change brief → a change-communications pack, drafted per audience and routed to each channel's producer |

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

## Comms generator (v0.1, scaffold)

Takes a change brief (often prose, often the Change Comms Console's handoff) and produces
a first-draft change-communications pack — per audience, not one draft broadcast to
everyone — written from the firm's own knowledge bank.

Five stages, the same shape as the proposal generator's, with a three-axis id spine
instead of one because a comms pack has to answer who, what, and when separately before
it can answer through which channel:

```
change brief + inputs ─▶ change_brief.json ─▶ comms_plan.json ─▶ build/ ─▶ qa_report.md
      INTAKE                 PLAN + DRAFT           BUILD          QA
```

`A1..` audiences, `M1..` messages (the six mandatory questions, plus what's not changing,
plus open unknowns), `T1..` timeline events, each flagged confirmed or not.

Two invariants, identical in spirit to the proposal generator's and non-negotiable here
too:

- **Provenance** — every content block traces to a message id or a knowledge-bank entry
  id, or carries an explicit `[GAP]` marker. No third state.
- **Coverage** — every mandatory message reaches every audience it applies to through at
  least one selected channel. An uncovered message x audience pair fails the run.

**Honest status on the two integrations the plan behind this skill investigated:**

- **Canva** — connected and authenticated, but this account has **no brand kits** and **no
  brand templates** (both calls returned empty), so the on-brand autofill route is
  unavailable regardless of how a run is configured. The newsletter uses
  `generate-design` with `design_type: "doc"` and `verbatim: true` — the one Canva route
  where supplied copy survives with no AI rewriting. The banner uses `design_type:
  "poster"`, where `verbatim` is **ignored** — Canva always rewords poster copy — so the
  banner ships as a design plus QA'd copy to paste in by hand, never as an autofilled
  design.
- **ElevenLabs (video narration)** — not integrable in this session: the connector isn't
  enabled in chat, so its tools aren't loaded and no real call shape can be observed.
  Both video channels (`short_form_video`, `explainer_video`) stay **planned**: the skill
  produces a script, captions, and a `narration_spec.json` instead of a rendered file, so
  wiring a narration engine later is a build step against an already-QA'd spec.

### What this scaffold does and does not include yet

This commit is the **scaffold**: `SKILL.md`, the three schemas, `channel_registry.json`,
the two reference guides, and the comms knowledge bank. It deliberately does **not**
include `scripts/qa_comms.py`, `scripts/route_channels.py`, or a worked example under
`examples/` — those are test-driven and tracked separately. Until they land, Stage 5's
checks are run by hand against the rules `SKILL.md` states, not by a script.

## Layout

```
skills/cm-proposal-generator/
├── SKILL.md              # the five-stage process
├── reference/            # section library, RFP extraction guide, KB guide
├── schemas/              # rfp_brief, proposal_plan, kb_entry contracts
└── scripts/              # index_kb, retrieve, profile_template, build_deck,
                          #   render_html, qa_deck
skills/cm-comms-generator/
├── SKILL.md              # the five-stage process, A/M/T id spine
├── reference/             # channel library, brief-interrogation guide
└── schemas/               # change_brief, comms_plan, channel_registry contracts
                          #   (scripts/ — qa_comms.py, route_channels.py — not yet built)
proposal-assets/
├── templates/
│   └── html-generic/     # PoC template: 9 layouts, theme, vendored reveal.js (MIT)
└── knowledge-bank/       # methodology, case-studies, credentials, team, commercials, boilerplate
comms-assets/
└── knowledge-bank/       # narrative, channel-examples, tone-and-style, faqs, glossary
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
