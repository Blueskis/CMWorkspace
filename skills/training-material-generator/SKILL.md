---
name: training-material-generator-v0.1
description: Generates a first-draft system training deck from a functional specification and other source documents, built on a slide template. Runs a five-stage pipeline — ingest the documents into an addressable index of text, tables and screenshots; plan learning objectives and modules; author slides that place the specification's own screenshots, draw diagrams from its prose, and close each module with a five-question knowledge check; build the deck; then QA it for objective coverage, source provenance, screenshot triage and question integrity. Use whenever someone wants training or enablement material drafted from a specification or design document — phrases like "build training material from this FSD", "create a training deck for the new system", "draft end-user training for this release", "turn this spec into a course", "we go live next month and need training". Do NOT use for reviewing or QA-ing training material that already exists, and do NOT use for proposals or bids.
---

# Training Material Generator

Turns a functional specification (plus whatever else exists — configuration workbooks,
process maps, status matrices) into a first-draft training deck: objectives, process
context, screenshot-led walkthroughs, business rules, diagrams, and a knowledge check at
the end of every module.

**The point of this skill is that the deck is checkable, not that it is fast.** Anyone can
generate slides from a document. What makes this useful is that (a) every statement on
every slide traces back to a numbered clause in the specification or carries an explicit
`[GAP]`, (b) every screenshot the document contains is either used or explicitly dismissed,
and (c) every learning objective is both taught and tested. All three are checked in
Stage 5, and none is optional.

That matters more here than in a proposal. A proposal that overclaims loses a bid. Training
material that states a business rule slightly wrong produces wrong transactions, and the
people running them believe they were trained correctly.

## MVP scope (read this before promising anything)

This is v0.1.

| In scope | Out of scope (v0.1) |
|---|---|
| One deck, one system, one release per run | Multi-system or multi-release curricula |
| `.docx` and `.xlsx` first-class; `.txt`/`.md` as text | PDF image extraction, OCR, legacy `.doc` |
| Modules from the library in `reference/module-library.md` | Free-form modules invented per run |
| Literal heading/keyword retrieval over the documents | Semantic or embedding search |
| Original screenshots placed beside numbered callouts | Cropping, annotation burn-in, image editing |
| Mermaid diagrams, rendered from source | Native editable PowerPoint diagram shapes |
| Five-question checks, MCQ + True/False, key in the notes | Scored assessments, LMS/SCORM export, branching |
| A self-contained HTML deck (PoC default) or the client's `.potx` | Generating a template, or restyling an off-template deck |
| A draft for the trainer to review | Material to put in front of learners |

**Audience curation is v0.2.** The schema already records `audiences` on every module and
slide, and the module library says what to write there, but the v0.1 build ignores it. Do
not promise a PO-approver deck and a PO-creator deck out of one run yet; do record the
audiences as you plan, so that when it arrives it is a render flag rather than a re-run.

Always hand the output over as **a first draft for the trainer to review**. Say so
explicitly, and say the two things a person still has to do: check every business rule
against the specification, and check every screenshot against the build learners will
actually see.

## Pipeline

```
  Stage 1  INGEST    source documents ─────────▶ source_index.json
  Stage 2  PLAN      index + module library ───▶ objectives + module outline
  Stage 3  AUTHOR    retrieval + placement ────▶ training_plan.json
  Stage 4  BUILD     plan + template_profile ──▶ training.html  /  training.pptx
  Stage 5  QA        coverage + provenance ────▶ qa_report.md
```

Each stage writes a file, so a run can be resumed, inspected or re-run from any stage.
Never go straight from a specification to a deck — the intermediate artifacts are what make
the output auditable, and the source index in particular is what every citation resolves
against.

### Run workspace

Create `training/<system-slug>-<YYYYMMDD>/` in the user's current working directory:

```
training/po-module-20260828/
├── inputs/              # copies of the FSD and supporting documents
├── assets/              # images extracted from them, by asset ID
├── source_index.json    # Stage 1
├── training_plan.json   # Stages 2-3
├── training.html        # Stage 4
└── qa_report.md         # Stage 5
```

## Stage 1 — Ingest

Ask for, or locate, the inputs. At minimum the functional specification; also ask what else
exists — configuration workbooks, process maps, a glossary, the release note saying what
changed, and **which build or release the material is for**. Training goes stale against a
moving system, so record the release in the plan.

```bash
python scripts/ingest_docs.py training/<run>/inputs \
    -o training/<run>/source_index.json --assets training/<run>/assets
```

`.docx` and `.xlsx` are read directly. For a `.pdf`, extract the text with the `pdf` skill
and pass that through as `.txt` — and say at handover that its images were never looked at,
because the index records `images_extracted: false` and Stage 5's screenshot triage can
only speak for the documents it could see.

See `reference/document-extraction.md` for what to look for and what specifications
habitually bury. Read the ingest summary before moving on: how many chunks and tables, how
many images and how they classified, which topics were ruled out of scope. Correct the
classifications now if any are wrong — a screenshot filed as an icon will not be placed.

Report back a short read of the source: what the system is, how many teachable topics, how
many screenshots, and anything the documents plainly do not cover. This is a transparency
checkpoint, not a request for approval — continue into Stage 2 unless redirected.

## Stage 2 — Objectives and modules

**Write the learning objectives first**, before selecting a single slide. Objectives are
observable and task-shaped — "raise a purchase order against a blanket agreement", not
"understand the PO module". Give each a stable ID (`LO1`, `LO2`, …). These IDs are the
spine of the run: modules map to them, questions test them, and Stage 5 fails if one is
taught but never checked.

Then select and order modules from `reference/module-library.md`. Rules that matter more
than the library itself:

1. **Use the system's own labels, verbatim.** Screen names, field labels, button text,
   status values, transaction codes — exactly as the specification writes them. A field
   renamed between spec and deck is a support ticket on day one, and a learner who cannot
   find "Delivery Date" because we called it "Required date" concludes the training was
   wrong. This is the single highest-value rule in this skill.
2. **Size by what the specification dwells on.** A screen described in one line earns a
   mention; one with fourteen field rules earns a walkthrough and a rules table. Never
   invent emphasis, and never pad a thin section to fill a module slot.
3. **Every in-scope topic gets a home**, or goes in `deferred_topics` with a reason.
   Dropping content has to be a decision, not an oversight.
4. **Order by task flow, not by specification structure.** Specifications are written in
   spec-writing order — data model, then screens, then rules. Learners need end-to-end task
   order. Where the two differ, follow the task and note the deviation in the plan.
5. **Process before system.** A walkthrough is preceded by the process context it sits in.
   Clicks without the why is the classic defect in system training, and it is why people
   cannot cope the first time the screen looks slightly different.
6. **A module must be able to sustain a five-question check.** Every check is exactly five
   questions, so a module with two testable facts is the wrong unit — merge it into its
   neighbour now. Catching this here is what stops Stage 3 inventing filler to hit the
   count.
7. **Record `audiences` on every module and slide** even though v0.1 ignores it — the
   library says which audiences each module serves.

## Stage 3 — Author the slides

Retrieve per slide, then write:

```bash
python scripts/retrieve_source.py training/<run>/source_index.json \
    --heading "Purchase Order Approval" --keywords approval,threshold --top 5
python scripts/retrieve_source.py training/<run>/source_index.json \
    --anchor POFSD#5.1 --context 2 --full
```

Retrieval is literal — no synonyms, no embeddings. It is a shortlist, not a decision: read
the shortlisted chunks and write the slide from them. When a search comes back thin, read
around a nearby anchor with `--context` before concluding the document is silent. A `[GAP]`
must mean the specification does not say, not that our search term was ours rather than
theirs.

Write each slide into `training_plan.json` against `schemas/training_plan.schema.json`,
with its `sources` — the document anchors the content came from.

**Provenance rule.** Every content block carries either a non-empty `sources` array or
`gap: true`. There is no third state. Adapting the specification's prose into teachable
language is the job; adding a rule it does not state is not. If you find yourself writing a
sentence you cannot point at, that sentence is a `[GAP]` — and a `[GAP]` on a business rule
is a question for the process owner, not a sentence for us to write.

Three authoring concerns, each with its own reference file:

- **Screenshots** — `reference/image-placement.md`. Which capture belongs on which slide,
  when a capture is unusable, and why callouts are text beside the image rather than
  annotations burned onto it.
- **Diagrams** — `reference/diagram-patterns.md`. The five Mermaid patterns and when each
  applies. A diagram is an interpretation of the text, so it carries the anchors of the text
  it was drawn from like any other block.
- **Knowledge checks** — `reference/question-writing.md`. **Exactly five questions per
  check, always a mix of multiple-choice and True/False** — the default shape is 3 MCQ and
  2 True/False, and a check that is all of one type fails Stage 5. Every question carries
  its answer, a rationale and the source anchor that proves it; all three go in the speaker
  notes, never on the slide.

Never invent a business rule, never soften a mandatory field into an optional one, and never
round a threshold. Values, statuses and field names come from the document verbatim or not
at all.

## Stage 4 — Build the deck

Two render targets. Both consume the same `training_plan.json` and are validated against the
same template profile, so switching between them changes nothing upstream.

**Profile the template first** — this is what a plan gets validated against, so a plan can
only ever reference layouts the template actually has:

```bash
# HTML template (a directory)
python scripts/profile_template.py training-assets/templates/html-training/ \
    -o training-assets/templates/html-training/template_profile.json

# PowerPoint template (a file)
python scripts/profile_template.py training-assets/templates/<client>.potx \
    -o training/<run>/template_profile.json
```

The profiler warns when a template has no obvious layout for a screenshot walkthrough, a
knowledge check or a diagram. Map those to the nearest layout the template does have and say
so in the plan — never plan a slide onto a layout that cannot hold it.

### 4a. HTML deck — the current default

```bash
python scripts/render_html.py training/<run>/training_plan.json \
    training-assets/templates/html-training -o training/<run>/training.html
```

One self-contained `.html` — CSS, JS and every screenshot inlined, no network, no server.
Arrow keys or space to advance; append `?print-pdf` to the URL and print for a paginated
PDF. Diagrams render from the vendored `mermaid.min.js`; if it is absent they degrade to a
visible labelled panel of their source, never to a blank space.

Two copies come off the same plan:

```bash
# trainer copy (default): answer key in the speaker notes, source anchors in the footer
python scripts/render_html.py <plan> <template> -o training.html

# participant copy: no key, no anchors
python scripts/render_html.py <plan> <template> -o participant.html \
    --answers hidden --sources hidden
```

**This is a proof-of-concept renderer on a generic template, not the client's.** Say so when
handing over.

### 4b. PowerPoint deck — the eventual target

```bash
python scripts/render_diagram.py training/<run>/training_plan.json \
    -o training/<run>/diagrams --write-back
python scripts/build_deck.py training/<run>/training_plan.json \
    training/<run>/template_profile.json -o training/<run>/build_manifest.json
```

`render_diagram.py` rasterises the Mermaid via `npx @mermaid-js/mermaid-cli`; if that is
unavailable it writes the source out and stops rather than building a deck with a figure
missing. `build_deck.py` then validates and sequences the plan into a manifest naming, per
slide, which layout to use, what to put in each placeholder, which image file to insert, and
the answer-key text for the notes pane.

Execute that manifest through the **`pptx` skill**'s template workflow. Three
non-negotiables:

- **Build from the client's template, never from scratch.** That means the unzip → edit
  `ppt/slides/slideN.xml` → rezip route the `pptx` skill documents for templates, *not*
  `pptxgenjs`. A visually similar deck is not the client's template, and someone will notice.
- **Don't override the template's design.** The `pptx` skill's "Design Ideas" section —
  palettes, motifs, typography — is for decks built from nothing. Here the template has made
  those decisions.
- **Insert every screenshot as the original file.** Do not re-encode, resize or crop on the
  way in. The image in the deck should be byte-identical to the one ingest pulled out of the
  specification.

If the trainer asks for a `.pptx` and there is no client template available, stop and ask
for one rather than building an approximation.

## Stage 5 — QA

```bash
python scripts/qa_training.py training/<run>/source_index.json \
    training/<run>/training_plan.json -o training/<run>/qa_report.md
```

Six checks. The script exits non-zero on any hard failure and prints the checklist for
whichever render target the plan used.

1. **Objective coverage** — every `LO` reaches a module *and* is tested by a question. An
   objective the deck teaches but never checks is one nobody finds out they missed.
2. **Topic coverage** — every in-scope topic is taught or deferred with a reason.
3. **Provenance** — every block has sources or a `[GAP]`, and every cited anchor actually
   resolves. A citation that does not resolve is worse than none: it looks checked.
4. **Screenshot triage** — every screenshot, diagram and chart in the documents is placed or
   excluded with a reason. Also flags placed images too low-resolution to be legible.
5. **Question integrity** — five per check, both types present, per-type option rules,
   rationale and source anchor on every question, no guessable True/False runs.
6. **Deck health** — the checklist a person has to run by eye.

Then step through the deck. Text overflow is the defect to hunt first: `.slide-body` clips
rather than spilling, so an overflowing slide drops content silently. Knowledge checks and
business-rules tables carry the most text and overflow first.

Deliver: the deck, the QA report, and a plain statement of what is still open — the
`[GAP]`s, any topic deferred, anything cut for length, and the reminder that this is a draft
for their review.

## Notes

- **The specification is the product.** A thin spec produces a deck full of `[GAP]`s, and
  that is the correct behaviour — it is telling the trainer what the project has not decided
  yet. Don't paper over it with plausible filler; list the gaps and who needs to answer them.
- **Screenshots go stale faster than text.** A capture from an earlier build teaches a screen
  that no longer exists, and it is the most common reason a deck has to be reworked after
  its first delivery. Record the release in the plan, flag any capture the specification
  itself says has changed, and say at handover that screenshots need checking against the
  build learners will see.
- **The HTML template is a stand-in, and saying so is part of the handover.** It exists so
  the pipeline can be exercised before the client's template is available. Once that template
  exists, profile it and switch to the `.pptx` path — nothing upstream of Stage 4 changes.
- **Go-live dates are real.** Surface the release date early and mention it when handing over
  the draft, especially if it is close. Training is usually the last thing scheduled and the
  first thing compressed.
