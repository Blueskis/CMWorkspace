# CM Workspace

Change-management working tools, packaged as a Claude Code plugin.

| Skill | What it does |
|---|---|
| `cm-proposal-generator` | **v0.2** — RFP + bid context → a change-management proposal deck as a real `.pptx`, populated from a knowledge bank |

## Proposal generator (v0.2)

Takes an RFP and the context of a bid (briefing notes, incumbent history, stakeholder
lists, budget guidance), works out which parts of the tender are change management's to
answer, and produces a first-draft proposal deck written from the firm's own knowledge
bank.

Six stages, each writing an inspectable artifact so a run can be resumed or audited from
any point:

```
whole RFP ─▶ rfp_triage.json ─▶ rfp_brief.json ─▶ proposal_plan.json ─▶ proposal.pptx ─▶ qa_report.md
   TRIAGE          INTAKE          PLAN + RETRIEVE          BUILD               QA
```

Three invariants the QA stage enforces mechanically, and the reason the intermediate
artifacts exist at all:

- **Provenance** — every content block traces to a knowledge-bank entry ID or carries an
  explicit `[GAP]` marker. There's no third state, so an invented claim can't hide among
  real credentials.
- **Coverage** — every requirement extracted from the RFP maps to a section, and an
  uncovered mandatory requirement fails the run rather than being quietly dropped.
- **Template fidelity** — the built `.pptx` carries the approved template's master,
  layouts and theme byte-for-byte, and no slide sets a font or colour of its own. "Built on
  the approved template" is a checked fact, not an intention.

### What's new in v0.2

- **A real `.pptx`.** `render_pptx.py` writes the deck directly onto the approved
  template — no manual OOXML step. v0.1 emitted a build manifest for a human to execute.
- **CM triage over a full tender.** `triage_rfp.py` splits a multi-part RFP on its own
  clause numbering and scores each section for CM relevance, reporting what it set aside as
  well as what it selected. It exists to catch the training obligation buried in the
  service-levels annex.
- **A generated stand-in template**, `pptx-generic.potx`, with the same nine layouts and
  the same placeholder names as the HTML one — so a single `proposal_plan.json` renders to
  either target unchanged, and switching to the firm's template is a config change.
- **Requirement kinds.** A rule about the response document is not answered by a slide; a
  post-award delivery obligation is answered differently from proposal content. QA now
  scores them separately instead of failing forever on requirements no slide can cover.
- **Past RFPs and past decks in the knowledge bank**, with `ingest_source.py` to draft
  entries from `.pptx`/`.docx`/`.md`/`.txt`, and a `bid.outcome` field — because language
  from a losing bid reads exactly as well as language from a winning one.

### Try it

A complete worked example ships in `examples/acme-erp/` — fictional client, invented RFP:

```bash
python skills/cm-proposal-generator/scripts/render_pptx.py \
    examples/acme-erp/proposal_plan.json \
    proposal-assets/templates/pptx-generic/pptx-generic.potx -o /tmp/acme/proposal.pptx

python skills/cm-proposal-generator/scripts/qa_deck.py \
    examples/acme-erp/rfp_brief.json examples/acme-erp/proposal_plan.json \
    -o /tmp/acme/qa_report.md

python skills/cm-proposal-generator/scripts/qa_pptx.py /tmp/acme/proposal.pptx \
    --original proposal-assets/templates/pptx-generic/pptx-generic.potx \
    -o /tmp/acme/qa_pptx.md
```

12 slides, 7/7 slide-needing requirements covered, 1 open `[GAP]`, 0 fidelity failures.
The same plan renders to HTML with `render_html.py` and no edits. See that folder's README
for what each part demonstrates.

Two real tender extracts ship as standing samples, both anonymised, and they fail in
different ways on purpose:

- `examples/cfs-ch8/` — a public-sector chapter written in "shall", page-marked, with a
  table of contents and running headers to see past.
- `examples/transport-erp/` — a commercial ERP tender written in **"should"**, nested six
  clause levels deep, with headings welded to their body text by Word.

### Setup before real use

1. **Fill the knowledge bank** at `proposal-assets/knowledge-bank/` — see the README
   there, and delete the `*-EXAMPLE.md` format exemplars so they can't be retrieved into a
   real bid. A thin bank produces a deck full of `[GAP]`s, which is correct behaviour: it
   reports what the firm hasn't written down yet.
2. **Drop the firm's approved template** into `proposal-assets/templates/` and profile it
   — see the README there. Until then the generic stand-in produces a real `.pptx`, but it
   is not the firm's template and must never be handed over as one.

### What v0.2 does not do

Pricing calculation, multi-lot bids, and semantic search over the bank (retrieval is
literal tag matching). Output is always a **draft for practitioner review**, never a
submission-ready document.

## Layout

```
skills/cm-proposal-generator/
├── SKILL.md              # the six-stage process
├── reference/            # section library, RFP extraction guide, KB guide
├── schemas/              # rfp_brief, proposal_plan, kb_entry contracts
└── scripts/              # triage_rfp, index_kb, ingest_source, retrieve,
                          #   profile_template, make_pptx_template, build_deck,
                          #   render_pptx, render_html, qa_deck, qa_pptx
proposal-assets/
├── templates/
│   ├── pptx-generic/     # generated stand-in .potx: 9 layouts, 16:9
│   └── html-generic/     # the same 9 layouts as HTML, vendored reveal.js (MIT)
└── knowledge-bank/       # methodology, case-studies, credentials, team, commercials,
                          #   boilerplate, past-rfps, presentations
examples/
├── acme-erp/             # worked example — fictional client
├── cfs-ch8/              # real tender chapter, anonymised — "shall", page-marked
└── transport-erp/        # real ERP tender, anonymised — "should", deeply nested
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
