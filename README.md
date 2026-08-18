# CM Workspace

Change-management working tools, packaged as a Claude Code plugin.

| Skill | What it does |
|---|---|
| `cm-proposal-generator` | **v0.1 (MVP)** — RFP + client inputs → a CM proposal deck, populated from a knowledge bank |
| `change-impact-assessment` | **MVP** — a programme's own documents → a baseline change impact assessment in the client's CIA template |

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
```

Proposal-generator scripts are stdlib-only. `generate_cia.py` needs `openpyxl`. Each runs
standalone with `--help`.

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
