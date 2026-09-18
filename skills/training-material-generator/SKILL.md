---
name: training-material-generator-v0.3
description: Generates a first-draft training deck (.pptx) from a functional specification document (FSD) or similar system/process documentation, built on the client's approved slide template. Runs a five-stage pipeline — map every input document's complete outline, write a training brief (audiences, learning objectives, scope), plan a module-by-module deck against that outline, fill each slide with retrieved content plus extracted screenshots and native-shape diagrams plus generated knowledge-check questions, then build and QA the deck. Screenshots can carry native-shape annotations — highlight boxes, numbered callouts, pointer arrows, redaction masks, zoom insets — layered over the untouched picture so a learner sees exactly where to look and what to click at each step, with every callout number checked mechanically against the slide's own instruction list. Use whenever a practitioner wants to draft, assemble, or generate training material, an enablement deck, a user guide deck, or a knowledge-transfer deck from an FSD, BRD, process document, or system documentation, or wants to highlight, callout, number, or annotate a system screenshot (S/4HANA Fiori and similar) for training slides — phrases like "turn this FSD into a training deck", "build training material from these specs", "generate a training deck for this system", "make an enablement deck from this documentation", "create knowledge-check questions from this spec", "highlight where to click on this screenshot", "add step numbers to this screen", "annotate this Fiori screen for the training deck", "redact the vendor name in this screenshot". Do NOT use for a persuasive pitch/bid deck (that's cm-proposal-generator) or for reviewing/QA-ing training material that already exists (that's the training-qa-agent skill).
---

# Training Material Generator

Turns a functional specification document (or FSD-like input — a BRD, a process guide,
system documentation with screenshots) into a first-draft training deck, built on the
client's approved template. Same discipline as `cm-proposal-generator`: **provenance and
coverage, not prose.** Every content block traces to a source-document anchor or carries a
visible `[GAP]`, and coverage is checked in *both* directions — every learning objective
reaches a slide and a question, and every procedural section of the source document reaches
a slide or an explicit, reasoned exclusion. Neither is optional, and both are checked
mechanically in Stage 5, not by eye.

## MVP scope (v0.3 — read this before promising anything)

| In scope | Out of scope |
|---|---|
| One deck, one system/process area, per run | Multi-system curricula, learning paths |
| Screenshot extraction + placement from `.docx`, `.pptx`, `.pdf` inputs | Auto-cropping or upscaling a screenshot outside an explicit `zoom` annotation |
| Five native-shape diagram types (process, swimlane, decision, hierarchy, timeline) | Arbitrary diagrams, SmartArt, animation |
| Screenshot annotation: highlight, numbered callout, pointer arrow, redaction, zoom inset — all native PowerPoint shapes over an untouched picture (see `reference/annotation-patterns.md`) | Annotating an asset with no readable pixel dimensions (EMF/WMF/SVG, interlaced or 16-bit PNG) — rebuild as a diagram or place unannotated instead |
| True pixel redaction of 8-bit, non-interlaced PNG/JPEG screenshots (`png_ops.py`) | Bulk/automatic redaction with no practitioner-reviewed rect — every mask is authored, never inferred |
| Knowledge checks: MCQ, multi-select, true/false, scenario | Scored/tracked assessments, LMS/SCORM packaging |
| Audience **tagged** on every objective and slide | Audience-**filtered** decks (a `--audience` build flag — planned for v0.4) |
| A `.pptx` on the client's approved template | Generating or approximating a template |
| Facilitator speaker notes | A separate facilitator guide document |

Audience curation is deliberately half-built: `training_brief.json`'s `audiences[]` and
each objective's/slide's `audience_ids` are populated now, just not filtered on at build.
That judgement — who needs which content — is cheapest to make once, in Stage 1, while
the FSD is in context; v0.4 turns it into a build-time filter over the same plan rather
than a re-plan.

**v0.3 reverses part of an earlier rule.** `reference/screenshot-placement.md` used to
forbid callout numbering on a screenshot outright ("this repo has no image-editing step").
That objection was to burning shapes into the screenshot's *pixels* — it still holds, and
nothing in v0.3 paints on a raster image except the one deliberate exception, redaction,
which destroys pixels by design rather than by accident. Everything else an annotation
draws is a native, editable, re-themeable PowerPoint shape layered over an untouched
picture. See `reference/annotation-patterns.md` for the full vocabulary.

Always hand the output over as **a first draft for the practitioner to review**, never as
finished training material. Say so explicitly at delivery.

## Pipeline

```
Stage 0  INTAKE     docs + template ─▶ source_map.json · chunk_index.json
                                        asset_index.json · template_profile.json
Stage 1  BRIEF      source_map + practitioner ─▶ training_brief.json  (audiences, LOs, scope)
Stage 2  PLAN       brief + module library + profile ─▶ deck_plan.json (outline, LO map, empty slots)
Stage 3  FILL       retrieval + assets + diagrams + questions ─▶ deck_plan.json + question_bank.json
Stage 4  BUILD      deck_plan + template ─▶ training.pptx
Stage 5  QA         coverage + provenance + instructional ─▶ qa_report.md
```

Every stage writes a file, so a run resumes or is audited from any point. Never skip
straight from an FSD to a deck.

### Run workspace

Create `training/<system-slug>-<YYYYMMDD>/` in the user's current working directory:

```
training/po-approval-20260829/
├── inputs/                 # copies of the FSD and any other source documents
├── assets/                 # extracted images, one file per asset_id
├── diagrams/                # rendered diagram fragments (.xml) + previews (.svg)
├── source_map.json  chunk_index.json  asset_index.json  template_profile.json
├── training_brief.json  deck_plan.json  question_bank.json  build_manifest.json
├── training.pptx
└── qa_report.md
```

### The invariants, restated for training

- **Provenance** — every content block carries a non-empty `sources` array of
  `source_map.json` section IDs, or `gap: true` with a `gap_note`. No third state. A
  training deck that states a field is mandatory when the FSD says optional is worse than
  one with a visible hole in it.
- **Coverage, in both directions** — every learning objective reaches at least one
  content slide *and* at least one knowledge-check question; and every source section
  classified `procedure` is either taught in a module or explicitly listed in
  `training_brief.json`'s `out_of_scope` with a reason.

The second direction is the design's departure from naive RAG: retrieval answers
questions you thought to ask; a training deck fails when nobody thought to ask about the
approval-delegation clause. **`source_map.json` (the complete document outline) drives the
module plan; retrieval only fills slides.** Top-k never decides what the course covers —
see `map_source.py`'s own docstring for the reasoning.

## Stage 0 — Intake

Ask for, or locate, the inputs: at minimum the FSD; also ask whether there's a template
already profiled, additional documents (an addendum, a UI style guide, a glossary), and
who the audiences are if not obvious from the FSD's own role model.

```bash
python scripts/map_source.py training/<run>/inputs/ -o training/<run>/source_map.json
python scripts/extract_assets.py training/<run>/inputs/ --assets training/<run>/assets \
    -o training/<run>/asset_index.json
python scripts/index_chunks.py training/<run>/source_map.json -o training/<run>/chunk_index.json
python ../../lib/profile_template.py <approved-template>.potx -o training/<run>/template_profile.json
```

`map_source.py` handles `.docx`, `.pptx` (as a source document), and `.pdf` (needs either
a `<stem>.txt` sidecar with pre-extracted text — the pattern `cm-proposal-generator`'s
`examples/cfs-ch8/` already uses — or `pdftotext` on PATH). It produces the **complete
outline**: every heading-delimited section, classified as `procedure | reference |
narrative | config | non-functional`. `extract_assets.py` pulls every embedded image
*with the anchoring context that makes it placeable* — which section it fell under, the
nearest heading, a caption candidate from the following paragraph — and drops obvious
noise (a letterhead repeated more than twice, anything under 20px). Both scripts share
`lib/section_walk.py`'s heading-stack walker, so a section_id means the same thing in both
outputs — that's what lets Stage 3 place a screenshot by the section it illustrates.

Profile the template with `pptx` skill's `thumbnail.py` too, so you've actually *seen*
the house style before mapping modules onto layouts:

```bash
cp <approved-template>.potx /tmp/tmpl.pptx
python ~/.claude/skills/pptx/scripts/thumbnail.py /tmp/tmpl.pptx tmpl-thumbs
```

If `template_profile.json` reports no layout with `has_picture_placeholder: true`, know
that before planning — screenshot placement will fall back to a free-floating picture
positioned into a content placeholder's geometry rather than a native picture slot.

Report back before continuing: section/document counts by classifier, how many
`procedure` sections were found (each needs a home later), how many screenshots survive
noise-filtering, and whether the template has a picture-capable layout. Transparency
checkpoint, not an approval gate — continue into Stage 1 unless redirected.

## Stage 1 — Brief

Write `training_brief.json` against `schemas/training_brief.schema.json`: system name,
process scope, delivery mode, session duration, prerequisites, a glossary, and the two
spines:

- **`audiences[]`** — read from the FSD's own role model where it has one (an FSD
  describing an approval workflow usually names its roles already); ask if it doesn't.
- **`learning_objectives[]`** (`LO1..LOn`) — observable-verb objectives ("route a PO over
  $10k for approval," never "understand approvals"), each with a Bloom level, the
  audience(s) it's for, and source anchors into `source_map.json`.

Plus `out_of_scope[]` — source sections deliberately not taught, each with a reason. This
is what makes Stage 5's source-coverage check meaningful rather than something to game:
every `procedure` section not reachable from a module must appear here.

Report the brief back before continuing: objective count, audiences found, sections
marked out of scope, anything the FSD leaves genuinely ambiguous.

## Stage 2 — Plan

Select and order modules from `reference/module-library.md` into `deck_plan.json`
(`schemas/deck_plan.schema.json`) — module outline and objective map first, slide content
left empty for Stage 3. The canonical arc, entry-criteria-based rather than fixed order:
welcome → what's changing and why → learning objectives → end-to-end process overview
(diagram) → key terms → roles and responsibilities (diagram or table) → task-walkthrough
modules (screenshots) → knowledge check per module → exceptions and common errors →
where to get help → summary and next steps → facilitator answer key.

Rules that outrank the library — see `reference/module-library.md` for the full list:

1. **Use the client's own terminology** — field, screen, role, and status names come from
   the FSD verbatim. A learner searching for the button you renamed fails the task.
2. **Size modules by procedural weight, not symmetry.** A process the FSD spends eleven
   sub-clauses and six screenshots on earns a module; one mentioned once earns a bullet.
3. **Every `procedure` section gets a home** — a module, or `out_of_scope` with a reason.
4. **Every LO maps to at least one slide.** An unmapped LO means the outline is wrong.
5. **Tag every slide with its `audiences`** as you plan it — this is the field v0.4 will
   filter on; get it right now while the FSD is in context.
6. **Vary layouts** — never more than two consecutive slides on the same one.

**Invoke the `visual-simplifier` skill here.** It does exactly this stage's hardest
judgement call: split each point into what belongs on the slide versus what the
facilitator says aloud, and decide whether a visual genuinely helps — including
recognizing when one doesn't. Its output is what decides which slots become `diagram`
blocks, which become `image` blocks, and what lands in `speaker_notes`.

**Do not use the `presentation-outline-builder` skill** — it builds a persuasive
Situation-Complication-Resolution narrative. A training deck is task-sequenced, not
persuasive; forcing that arc produces a deck that argues instead of teaching.

## Stage 3 — Fill

Shortlist candidate passages per slide, then write from them — never from general
knowledge about the system:

```bash
python scripts/retrieve_chunks.py training/<run>/chunk_index.json \
    --query "approval threshold" --section fsd#4.2 --top 6
```

BM25 over `index_chunks.py`'s inverted index — literal and explainable, same reasoning
`cm-proposal-generator`'s `retrieve.py` gives for tag matching over embeddings: a ranking
you can't reason about can't be debugged when it pulls the wrong clause. A shortlist is
not a decision — read the candidates and choose what actually goes on the slide, and set
`sources` to the `source_map.json` section IDs (not chunk IDs) the content actually came
from.

**Invoke the `slide-writer` skill** to turn chosen chunks into a headline, ≤10-word
bullets, and a speaker note — constrained to what's in the retrieved chunks. Anything it
adds that isn't in a cited chunk is a Stage 5 provenance failure.

**Invoke the `hook-maker` skill** for the opening slide only, and prefer its
relatable-question or short-story options — its web-verified-statistic option is wrong
for internal system training, where a public digital-transformation stat reads as filler.

**Screenshots** — see `reference/screenshot-placement.md`. Each `image` block names an
`asset_id` from `asset_index.json` and a caption; place the asset whose `section_id`
matches the step being taught. A `low_res`-flagged asset needs `content.ack_low_res: true`
to be placed at all — `build_training_deck.py` refuses it otherwise.

**Annotating a screenshot** — see `reference/annotation-patterns.md` for the full
vocabulary (`highlight`, `callout`, `arrow`, `redact`, `zoom`) and when to use each. Add an
`annotations` array to the `image` block's `content`, coordinates as 0-1 fractions of the
*image*, not the slide:

```json
"content": {"asset_id": "fsd-img-014", "caption": "Purchase order approval screen — ① Approve button",
  "annotations": [
    {"type": "highlight", "rect": [0.41, 0.22, 0.28, 0.06], "step": 1, "label": "Approve button"},
    {"type": "callout", "point": [0.55, 0.25], "step": 1}
  ]}
```

A `callout`'s `step` binds to the 1-based index of the sibling `bullets` block's
instructions on the same slide — the set of steps must be exactly `{1..N}` against that
block's bullet count, or `build_training_deck.py`/`qa_training.py` hard-fail. **Redacting
client data is mandatory before handover, not optional**, given this project's government
and GLC clients — flatten with `png_ops.py redact` first (see the reference doc); a
`redact` annotation's block must point at the flattened asset, never the original.

**Diagrams** — see `reference/diagram-patterns.md` for which prose shape maps to which of
the five types. Render each with:

```bash
python scripts/render_diagram.py diagram_spec.json --type process \
    --bbox 0.6,1.8,8.5,4.5 -o training/<run>/diagrams/<slide_id>.xml \
    --svg training/<run>/diagrams/<slide_id>.svg
```

`--bbox` should be the target layout's placeholder geometry from `template_profile.json`.
Colours always come out as `<a:schemeClr>` references and fonts always inherit, so the
diagram stays on-template. **If a label won't fit even at the smallest allowed font, the
script fails loudly rather than emitting clipped text** — shorten the label or split the
diagram, don't retry blindly.

**Knowledge checks** — see `reference/knowledge-checks.md`. Write `question_bank.json`
against `schemas/question_bank.schema.json`: every question maps to an LO and cites the
`source_map.json` section its answer is stated in; an FSD-unanswerable question is a
`[GAP]` on the plan, not a guess. Test the task, not trivia; distractors are plausible
wrong answers drawn from adjacent spec content, never throwaways.

## Stage 4 — Build

```bash
python scripts/build_training_deck.py training/<run>/deck_plan.json \
    training/<run>/template_profile.json training/<run>/asset_index.json \
    -o training/<run>/build_manifest.json
```

This validates — every layout/placeholder exists, every block has provenance, every image
asset exists and (if `low_res`) is acknowledged, every diagram spec actually renders
against its target geometry — and sequences a manifest. It does not assemble XML itself,
for the same reason `cm-proposal-generator`'s `build_deck.py` doesn't: a half-working
assembler that silently drops a placeholder is worse than a manifest a human can follow.

Execute the manifest through the **`pptx` skill's template workflow**: unzip the approved
template, `add_slide.py` to duplicate layouts (all structural work before any content
edits, per that skill's own ordering rule), set text placeholders directly in the slide
XML, then for each `image`/`diagram` block:

```bash
python scripts/inject_slide_xml.py picture unpacked/ ppt/slides/slideN.xml \
    --image training/<run>/assets/fsd-img-014.png --bbox 0.6,1.8,8.5,4.5 --alt "Approval screen"

python scripts/inject_slide_xml.py diagram unpacked/ ppt/slides/slideN.xml \
    --fragment training/<run>/diagrams/<slide_id>.xml
```

`picture` writes the media part, the slide relationship, and the `<p:pic>` reference
together — all three or none, so the deck is never left half-wired — and aspect-fits the
image into `--bbox`, centered, never distorted. `diagram` imports a `render_diagram.py`
fragment and renumbers its shape IDs above the slide's current maximum, so multiple
diagrams (or a diagram on a slide `add_slide.py` duplicated) never collide.

**If the image block carries `annotations`, render and inject the overlay right after its
picture — same slide, same `diagram` subcommand, since an annotation fragment is a
`<p:grpSp>` exactly like a rendered diagram:**

```bash
python scripts/render_annotation.py training/<run>/annotations/<slide_id>.json \
    --image training/<run>/assets/fsd-img-014.png --bbox 0.6,1.8,8.5,4.5 \
    -o training/<run>/annotations/<slide_id>.xml

python scripts/inject_slide_xml.py diagram unpacked/ ppt/slides/slideN.xml \
    --fragment training/<run>/annotations/<slide_id>.xml
```

**Order matters: the picture must be injected first, the annotation overlay second**, so
the shapes land on top of the screenshot in document order — inserting them the other way
round buries the callouts under the picture.

Then `clean.py`, zip, and `validate.py --original <template>` — exactly as the `pptx`
skill documents.

**Verify every annotated slide before handover** — coordinate precision on a dense system
screen is the real risk in this feature, not the drawing. Render the built slide back to
an image and check each shape lands on its target; correct and re-inject if not, up to 3
passes, and if still wrong after that, drop the shape rather than ship a wrong callout.
Full procedure in `reference/annotation-patterns.md`'s verify loop.

Two non-negotiables, inherited from `cm-proposal-generator` and equally true here:

- **Build from the approved template, never from scratch.** No `pptxgenjs`. A lookalike
  deck is not an approved-template deck.
- **Do not apply the `pptx` skill's "Design Ideas" section, or the `theme-factory` skill.**
  Those are for decks built from nothing; the client's template has already made those
  decisions. Colours, fonts, and layout choices all come from the template.

If the practitioner asks for a `.pptx` and there's no approved template available, stop
and ask for one rather than building an approximation — "on the client's approved
template" is the whole requirement, and a lookalike fails it. Only if the practitioner
explicitly accepts a placeholder for a first pass, generate one with
`scripts/make_placeholder_template.py` — six plain, undecorated layouts (title, section
header, title-and-content, two-content, picture-with-caption, diagram-full) covering
every block kind the pipeline needs, so nothing downstream has to special-case a missing
template. State plainly at handover that it isn't the real one.

## Stage 5 — QA

```bash
python scripts/qa_training.py training/<run>/training_brief.json training/<run>/deck_plan.json \
    training/<run>/source_map.json training/<run>/asset_index.json \
    --questions training/<run>/question_bank.json -o training/<run>/qa_report.md
```

Six mechanical checks (see the script's own docstring for exact pass/fail rules):
objective coverage (slide *and* question), source coverage (`procedure` sections),
provenance, asset hygiene (every screenshot placed or declared unused with a reason in
`deck_plan.json`'s `unused_assets`), question sanity (valid keys, enough distractors,
valid objective/source references), and annotation integrity — callout numbers bind
exactly 1:1 to their slide's instructions, every coordinate is in bounds, and every
`redact` annotation's asset actually carries `redacted_from` (a vector mask alone is a
hard fail here, not a warning — it leaves the original pixels recoverable in the .pptx).
The first three, plus the annotation-binding and redaction checks, are hard failures.

Then two passes this script doesn't attempt:

- **Invoke the `training-qa-agent` skill** for instructional integrity — objective
  alignment, sequencing, terminology drift, assessment quality, and (since this is
  system/process training) its system-training lens for stale legacy terminology and
  screen/navigation mismatch. It writes findings into the deck's speaker notes as a
  delimited `--- QA NOTES ---` block; tell the practitioner to look there, not in a
  separate report.
- **The `pptx` skill's own QA** — `markitdown` plus the placeholder-text grep,
  `validate.py --original`, and visual QA on every rendered slide. Screenshot slides are
  where overflow and aspect distortion show up first; diagram slides are where label
  clipping does (if `render_diagram.py` didn't already catch it before build).

Deliver the deck, the QA report, and a plain statement of what's still open: every
`[GAP]`, any uncovered objective, anything left out of scope, unplaced screenshots — and
the reminder that this is a draft for review.

## Notes

- **The source documents are the product.** A thin FSD produces a deck full of `[GAP]`s,
  and that's correct behaviour — it tells the practitioner what the spec never actually
  answered. Don't paper over a gap with plausible-sounding generated filler.
- Never invent a procedure, field, or role the source documents don't state, and never
  soften a mandatory/optional distinction they do state.
- `slide-writer` and `hook-maker` write fluently from general knowledge — valuable
  elsewhere, a liability here. The provenance check is the backstop; constrain their
  input to retrieved chunks and re-verify their output cites real sources.
- Deadlines and go-live dates in FSDs are real. Surface them early if training needs to
  land before a cut-over.
- **Annotation is now ported to the `webapp/` browser artifact** (`src/render-annotation.js`,
  `src/canvas-ops.js`, wired into `plan.js`'s opt-in "annotate" stage, `build-pptx.js`, and
  `qa.js`). The redaction invariant carries over unchanged: `canvas-ops.js`'s `redactImage()`
  produces a genuinely flattened asset via Canvas 2D (no PNG codec needed — the browser
  already has one), and `build-pptx.js`/`qa.js` both refuse a `redact` annotation whose
  block still points at the un-flattened original, exactly as `build_training_deck.py`/
  `qa_training.py` do here. `test/parity.mjs` still only guards `map_source.py`/
  `extract_assets.py`, and deliberately does not attempt byte-for-byte parity on pixel
  ops — Canvas and this stdlib codec will never produce identical bytes, and shouldn't;
  `webapp/test/annotation-render.mjs` and `canvas-ops.mjs` cover the browser side directly
  instead. The one thing that must never diverge between the two implementations is the
  refusal itself: an un-flattened redact ships on neither side, under any circumstance.
  Where the two annotation authoring flows genuinely differ: the CLI skill's coordinates
  come from Claude reading the screenshot in-session; the artifact's come from a
  `sample.json` call with the screenshot attached, one call per screenshot, opt-in and
  consent-gated — see `webapp/src/plan.js`'s `annotatePrompt()`/`annotateModules()`.

## Layout

```
skills/training-material-generator/
├── SKILL.md
├── reference/            # module library, FSD extraction, screenshot placement,
│                         #   diagram patterns, annotation patterns, knowledge-check
│                         #   quality rules
├── schemas/              # source_map, asset_index, training_brief, deck_plan,
│                         #   question_bank contracts
└── scripts/              # map_source, extract_assets, index_chunks, retrieve_chunks,
                          #   render_diagram, render_annotation, png_ops, inject_slide_xml,
                          #   build_training_deck, qa_training, make_placeholder_template
lib/
├── profile_template.py   # shared with cm-proposal-generator — profiles a .potx/.pptx
│                         #   or an HTML template's layouts, placeholders, theme
└── section_walk.py       # shared heading-stack walker — map_source.py and
                          #   extract_assets.py both import it so a section_id means
                          #   the same thing in source_map.json and asset_index.json
```

Scripts are stdlib-only except `inject_slide_xml.py`, which uses `defusedxml` (falls back
to stdlib `xml.dom.minidom` with a warning if absent) — the one stage that edits a real
deck's XML. `png_ops.py` shells out to `soffice` (LibreOffice) only to transcode a JPEG
screenshot to PNG before redacting or cropping it; the PNG codec itself — decode, redact,
crop, upscale, encode — is `zlib` and `struct` alone, no image library.
