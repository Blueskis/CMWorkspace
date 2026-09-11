# CM Workspace

Change-management working tools, packaged as a Claude Code plugin.

| Skill | What it does |
|---|---|
| `cm-proposal-generator` | **v0.1 (MVP)** — RFP + client inputs → a CM proposal deck, populated from a knowledge bank |
| `cm-comms-generator` | **v0.2** — a change + a chosen channel → a comms draft, routed to the tool that builds it (.docx / .pptx / Canva) |
| `cm-effort-estimator` | **v0.5** — scope drivers → a manday estimate, with an open-ended judgement layer for adjustments the drivers alone don't capture |
| `change-impact-assessment` | **MVP** — a programme's own documents → a baseline change impact assessment in the client's CIA template |
| `training-material-generator` | **v0.2 (MVP)** — an FSD (or similar spec doc) → a first-draft training deck, with placed screenshots, native diagrams, and knowledge-check questions |
| `brand-template-creator` | A published claude.ai Artifact — capture a client's brand once (colours, fonts, style, logo, voice, messaging) and export a `.json` + `.md` brand guide to reuse across sessions |
| `cm-proposal-reference-tool` | A published claude.ai Artifact (not a skill): drop in a tender, get the firm's most similar past proposals ranked, read live from Airtable. See `artifacts/cm-proposal-reference-tool/README.md` |
| `prompt-engineer` | A single-file HTML Artifact (not a skill): describe what you want an AI to do, answer a few optional questions, get one ready-to-paste prompt back. Generic, for any AI user. See `prompt-engineer/README.md` |

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
## Change impact assessment (MVP)

Reads a system implementation's own source material — interview and workshop notes, meeting
recordings and transcripts, Signavio/BPMN process design, functional specifications, slide decks,
spreadsheets, org design — and writes a baseline assessment into **the client's own CIA
template**.

**Source ingestion.** `ingest_sources.py` normalises a folder of mixed client files into readable
text plus a source manifest, using the standard library alone: `.docx` and `.pptx` (including
speaker notes), `.xlsx`/`.csv`, `.vtt`/`.srt` transcripts as speaker turns with timestamps, and
BPMN exports broken out by **lane — the lanes are the impacted roles**, which is the most useful
thing a process model gives a CIA. PDFs and images are flagged for Claude to read natively rather
than text-extracted, because a process diagram is often the most informative thing in the pack.

**Voice recordings** need a transcript first — Claude cannot listen to audio. The skill asks for
the meeting platform's own transcript (Teams, Zoom and Meet generate one automatically, with
speaker labels and correctly spelled names), and otherwise transcribes locally with
`transcribe_interview.py`. A cloud ASR service is treated as a data-protection decision rather
than a default — interview recordings contain named employees discussing job security.

`transcribe_interview.py` is built for evidence rather than captions:

- **Names and jargon are biased in.** The attendee roster and a domain vocabulary
  (`reference/asr-vocabulary.txt`) are fed to the model as decoding context, because ASR fails
  hardest on exactly the proper nouns a CIA runs on — system names, module names, acronyms.
- **Doubt is surfaced.** Turns the model was unsure about, and turns showing the repetition
  signature of a hallucination, are flagged inline. So is every turn stating a quantity —
  in digits *or* spelled out, since people say "a hundred and fifty", not "150".
- **Attribution is a first-class step.** Machine transcription cannot tell who is speaking, so
  the tool emits a turn worksheet; you label it while skimming the audio, and
  `--apply-speakers` merges it back into a `.vtt` that flows on into ingestion.
- **Setup is verifiable before it matters.** `--check` reports what's installed,
  `--download-model` caches the weights up front, and `--selftest` runs the whole pipeline
  stage by stage so a failure points at backend, decoder, probe, model load or output writing
  rather than a stack trace. `--dry-run` estimates the time before you commit to a batch, and
  long recordings checkpoint so a failure at minute 80 resumes rather than restarting.
- **The likeliest setup failure is handled by name.** Whisper weights come from Hugging Face
  and enterprise proxies routinely deny that host; the tool recognises the blocked download,
  says it is a network policy rather than a broken install, and gives the pre-staging steps.

Reading verbatim transcripts is a different job from reading notes, covered in
`reference/interview-evidence.md`: attribution (who said it decides whether it is testimony, a
claim, design intent or hearsay), harvesting quotes, reading hesitation and contradiction, and
never banking a number heard only in speech.

**The template owns the model.** Four-level process taxonomy (L1–L4 with codes), three
dimensions — People, Process, Technology — each scored 0–3 against the anchors on the
template's own rubric sheet, averaged unweighted into Overall Impact. The generator loads
`skills/change-impact-assessment/templates/CIA_Template.xlsx` and writes rows into it, so its
headers, theme colours, merges and `Change Impact Ratings` rubric come through untouched —
checked against the original file on every run. Point `--template` at a different client
template to use theirs instead.

Output sheets:

- **CIA Template** — the deliverable, in the client's format. One row per process change ×
  stakeholder group: L1–L4 taxonomy, current roles and headcount, as-is → to-be, a description
  and 0–3 score for each of People/Process/Technology, the Overall Impact average, and the
  training, communications and other (policy, engagement) responses
- **Change Impact Ratings** — the client's scoring rubric, carried through unchanged
- **Impact Heatmap** — where the change lands, by stakeholder group and by L1 area
- **Training Plan** — delivery method, duration and effort roll-up in person-hours and days
- **Comms Plan** — key messages by audience and wave, with named senders
- **Traceability** — the source documents behind each row, and the open questions for
  business validation
- **Assessment Info** — programme metadata, impact profile, and the assumptions being made

Overall Impact, heatmap counts and the roll-ups are live Excel formulas, so re-scoring a Degree
of Impact in a validation workshop updates the whole pack. `--extended` appends eight governance
columns (impact ID, stakeholder group, resistance, champion, source ref, confidence, status,
notes) for the CM team's working copy, leaving the default output matching the client template
exactly.

One assumption to confirm with a client before baselining: the template defines the 0–3
dimension scale but not the cut-offs on the overall average. The generator uses High ≥ 2.50 /
Medium 1.50–2.49 / Low 0.50–1.49 / No-Minimal < 0.50, states this on the Assessment Info sheet,
and it is changeable in one constant.

`skills/change-impact-assessment/examples/` holds a complete worked example for an SAP S/4HANA
and Ariba implementation — seven sources, including a real Teams `.vtt` transcript, and the
21-impact assessment they produce. Two of those rows exist to show what a transcript gives you
that a note cannot, including one finding that surfaced only because a colleague corrected a
headline number mid-sentence.

**Airtable as a live alternative.** `push_to_airtable.py` publishes the same assessment as
two linked tables — `Sources` and `Change Impacts` — so traceability works in both directions
(open a source, see every impact derived from it), and the workbook's roll-up sheets become
filtered views that cannot drift from the register. Records upsert on Impact ID, so the JSON
stays the master and re-running syncs rather than duplicating. `Overall Impact` and `Rating` are created as formula fields, so re-scoring a dimension in a
validation workshop updates the rating live, as it does in the workbook. Standard library
only; the official Airtable connector is the no-token alternative. See
`reference/airtable-workspace.md` — including why importing the workbook straight into
Airtable produces a base that looks right and is not.

Requires `openpyxl` (`pip install openpyxl`).
## Training material generator (v0.2, MVP)

Takes a functional specification document (or similar — a BRD, a process guide, system
documentation with screenshots) and produces a first-draft training deck on the client's
approved template: screenshots placed by the procedure step they illustrate, native
PowerPoint diagrams (process flows, swimlanes, decision trees, org hierarchies,
timelines) built from the spec's own prose logic, and knowledge-check questions derived
from — and cited back to — the spec.

Five stages, same discipline as the proposal generator — every stage writes an
inspectable artifact:

```
docs + template ─▶ source_map.json ─▶ training_brief.json ─▶ deck_plan.json ─▶ training.pptx ─▶ qa_report.md
      INTAKE            BRIEF               PLAN                 FILL + BUILD          QA
```

Two invariants enforced mechanically in Stage 5:

- **Provenance** — every content block traces to a source-document section or carries an
  explicit `[GAP]` marker.
- **Coverage, in both directions** — every learning objective reaches a content slide
  *and* a knowledge-check question, and every procedural section of the source document
  reaches a module or an explicit, reasoned exclusion. The document's own outline drives
  the module plan; retrieval only fills slides — top-k never decides what the course
  covers.

See `skills/training-material-generator/SKILL.md` for the full pipeline, and
`tests/run_tests.py` for a runnable check of the extraction, retrieval, diagram-rendering,
and QA logic against synthetic fixtures (`python tests/run_tests.py -v`).

### What v0.2 does not do

Multi-system curricula, audience-*filtered* decks (audiences are tagged now, filtering is
v0.3), scored/tracked assessments or LMS packaging, and automated cropping/upscaling of
extracted screenshots. Output is always a **draft for practitioner review**.

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
└── scripts/              # index_kb, retrieve, build_deck, render_html, qa_deck
skills/training-material-generator/
├── SKILL.md              # the five-stage process
├── reference/            # module library, FSD extraction, screenshot placement,
│                         #   diagram patterns, knowledge-check quality rules
├── schemas/              # source_map, asset_index, training_brief, deck_plan,
│                         #   question_bank contracts
└── scripts/              # map_source, extract_assets, index_chunks, retrieve_chunks,
                          #   render_diagram, inject_slide_xml, build_training_deck,
                          #   qa_training
lib/                      # shared, stdlib-only — used by both skills
├── profile_template.py   # profiles a .potx/.pptx or HTML template's layouts/placeholders/theme
└── section_walk.py       # shared heading-stack walker, so a section_id means the same
                          #   thing across a skill's own outline and asset-index outputs
proposal-assets/
├── templates/
│   └── html-generic/     # PoC template: 9 layouts, theme, vendored reveal.js (MIT)
├── brand-profiles/       # one approved brand profile per client
└── knowledge-bank/       # methodology, case-studies, credentials, team, commercials,
                          #   boilerplate, comms-collateral, comms-tone, comms-boilerplate
examples/acme-erp/        # worked example — proposal, fictional client
examples/northwind-payroll/  # worked example — comms, fictional client, five channels
└── knowledge-bank/       # methodology, case-studies, credentials, team, commercials, boilerplate
examples/acme-erp/        # worked example — fictional client

skills/cm-effort-estimator/
├── SKILL.md              # what it does, what it doesn't, the placeholder-norms caveat
├── estimator.html         # the whole tool — data, engine, judgement layer, UI
├── tests/                # node:test, sliced straight out of estimator.html
└── reference/
    └── judgement-layer.md  # the adjustment schema, validation, the admin-config boundary
skills/change-impact-assessment/
├── SKILL.md              # the assessment process
├── templates/            # the client CIA template the generator populates
├── reference/            # source ingestion, interview evidence, extraction guide,
│                         #   rating methodology, response playbook, input schema
├── scripts/              # transcribe_interview.py — recordings → attributed transcripts
│                         # ingest_sources.py       — mixed client files → text + manifest
│                         # generate_cia.py         — validator and workbook builder
│                         # push_to_airtable.py     — same assessment as a live Airtable base
└── examples/             # worked example — six source documents + the assessment
artifacts/brand-template-creator/  # Brand Vault — published Artifact, its schema and tests
artifacts/cm-proposal-reference-tool/  # published Artifact — tender in, ranked past-proposal shortlist out
```

Proposal-generator scripts are stdlib-only. `generate_cia.py` needs `openpyxl`. Each runs
standalone with `--help`.
tests/                    # unit tests for training-material-generator, against synthetic fixtures
artifacts/brand-template-creator/  # Brand Vault — published Artifact, its schema and tests
```

Indexing, retrieval, template profiling and deck validation are reused from
`cm-proposal-generator` unchanged — `profile_template.py` and `build_deck.py` validate a comms
deck plan against a client `.potx` exactly as they do a bid. `render_html.py` is no longer part
of the comms path, and is untouched.

Scripts are stdlib-only and each runs standalone with `--help`.
Scripts are stdlib-only and each runs standalone with `--help`, except
`training-material-generator`'s `inject_slide_xml.py`, which uses `defusedxml` (falls back
to stdlib `xml.dom.minidom` with a warning if absent).

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
