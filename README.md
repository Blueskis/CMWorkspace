# CM Workspace

Change-management working tools, packaged as a Claude Code plugin.

| Skill | What it does |
|---|---|
| `cm-proposal-generator` | **v0.1 (MVP)** — RFP + client inputs → a CM proposal deck, populated from a knowledge bank |
| `training-video-generator` | **v0.1 (PoC)** — a consultant's screen recording → a narrated, annotated training module built in Synthesia |

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

## Training video generator (v0.1, PoC)

Turns a screen recording a functional consultant made of a live system into a narrated,
annotated training module, assembled in Synthesia with the practitioner's AI avatar.

The division of labour is forced by access, and the design follows it:

```
consultant records ─▶ capture_map.json ─▶ video_script.json ─▶ build_sheet.md ─▶ qa_report.md
   (system access)        INGEST               SCRIPT             SHEET            QA
                                                            └─ Synthesia editor ─┘
```

Claude cannot record the demo — the client system is behind the consultant's credentials —
and Synthesia does the compositing, avatar and voice. What sits in between is the slow,
error-prone part: reading the footage frame by frame, writing narration that fits each scene's
measured duration, and proving the result matches.

**The narration is the consultant's own words, cleaned — not rewritten.** They explain the
system while demonstrating it, and that explanation carries what the screen cannot: why a
field is mandatory, what breaks if you skip it, which of two similar options is right.
Fillers, false starts and wrong turns come out; nothing gets added.

Three invariants the QA stage enforces mechanically:

- **Screen provenance** — every narration sentence asserting something about the system
  traces to a keyframe someone actually read, or carries an explicit `[GAP]`. There's no
  third state, so narration can't confidently say "click Save" over a screen with no Save
  button.
- **Capture coverage** — every second of the recording belongs to a scene, kept footage is
  narrated, and dropped footage carries a stated reason. Nothing the consultant recorded
  vanishes by accident.
- **Fidelity** — narration is diffed against the guide transcript, so content that appears
  from nowhere gets flagged. "Lightly cleaned" is checked, not claimed.

Plus fit and consistency. Fit is the counter-intuitive one: people speak faster casually
(~190 wpm) than an avatar delivers at a training pace (~145), so faithful narration routinely
needs *more* time than the clip. Synthesia sets scene length from the script, so the footage
holds its last frame and **the built video runs longer than the recording** — which is what
credits bill on, and what the tooling reports.

### Try it

A complete worked example ships in `examples/fixture-demo/` — invented system, invented data.
Stages 2–4 need no ffmpeg and no video:

```bash
cd examples/fixture-demo
S=../../skills/training-video-generator/scripts

python $S/fit_narration.py video_script.json
python $S/qa_video.py capture_map.json video_script.json -o /tmp/qa_report.md
```

6 scenes, 66s of footage building to an 81s module, one open `[GAP]`, three frame holds. See
that folder's README for what each part demonstrates, and run its `check_invariants.py` to
confirm all 16 checks actually fire.

### Setup before real use

1. **Send `reference/recording-guide.md` to the consultant before they record.** It is the
   highest-leverage file in the skill — a recording made without it usually has to be redone.
2. **Build the Synthesia template once** — avatar bottom-right, annotation styles, captions on
   — per `reference/synthesia-build.md`. Every module inherits it.
3. **Install ffmpeg** (Stage 1 only; `scripts/preflight.py` checks and tells you how).

### What v0.1 does not do

Record the demo, drive Synthesia by API (that needs Creator tier — there is no Synthesia MCP,
and Starter has no API at all), speech recognition, multi-language, SCORM packaging, or
batching modules. Output is always a **draft for practitioner review** — only the consultant
who recorded the demo can confirm the narration is factually right about their system.

## Layout

```
skills/cm-proposal-generator/
├── SKILL.md              # the five-stage process
├── reference/            # section library, RFP extraction guide, KB guide
├── schemas/              # rfp_brief, proposal_plan, kb_entry contracts
└── scripts/              # index_kb, retrieve, profile_template, build_deck,
                          #   render_html, qa_deck
skills/training-video-generator/
├── SKILL.md              # the four-stage process
├── reference/            # recording guide (for the consultant), Synthesia build guide
├── schemas/              # capture_map, video_script contracts
└── scripts/              # preflight, ingest_capture, fit_narration, build_sheet, qa_video
proposal-assets/
├── templates/
│   └── html-generic/     # PoC template: 9 layouts, theme, vendored reveal.js (MIT)
└── knowledge-bank/       # methodology, case-studies, credentials, team, commercials, boilerplate
examples/acme-erp/        # worked example — fictional client
examples/fixture-demo/    # worked example — synthetic screen recording
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
