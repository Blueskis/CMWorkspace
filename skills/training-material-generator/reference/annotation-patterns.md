# Annotation Patterns

Which teaching intent maps to which of `render_annotation.py`'s five annotation `type`
values, the coordinate convention every one of them shares, the redaction rule that
overrides everything else, and the verify loop that catches a wrong coordinate before it
ships. Get the type right before authoring the coordinates — a `highlight` that should have
been a `zoom` still renders, but doesn't teach what it was supposed to.

A `deck_plan.json` `image` block's `content.annotations` is a list of these objects —
exactly what `render_annotation.py` and `build_training_deck.py` both expect. Every
coordinate is a **0-1 fraction of the screenshot image itself**, origin top-left — never a
fraction of the slide or the placeholder. `render_annotation.py` maps this onto the
image's *aspect-fitted* rect inside the placeholder (the same rect `inject_slide_xml.py`
computes when it places the picture), so an annotation authored against the image lands
correctly however the image ends up letterboxed on the slide.

## `highlight` — outline a region

**Use when:** the instruction is "look at this field/button/panel" and the target has a
clear rectangular extent — a form field, a button, a status chip, a section of a table row.

```json
{"type": "highlight", "rect": [0.41, 0.22, 0.28, 0.06], "step": 1,
 "label": "Approve button", "sources": ["s-4-2"]}
```

`rect` is `[u, v, du, dv]`. Renders as a no-fill rounded rectangle with a thick accent1
outline — the screenshot underneath stays fully visible and legible.

**Not this when:** the target is a small icon in a crowded toolbar — a box around a
12px icon is barely visible at slide scale. Use `zoom` instead.

## `callout` — number a point

**Use when:** the slide has a numbered instruction list and each number needs to land on
the exact spot it refers to — the standard task-walkthrough pattern.

```json
{"type": "callout", "point": [0.55, 0.25], "step": 1}
```

`point` is `[u, v]` — the centre of the circle. Renders as a filled accent1 circle with a
real, editable white number in it (a genuine `<a:t>` text run, not a rasterized digit) —
selectable and movable in PowerPoint exactly like any other shape.

**The binding is mechanical, not advisory.** `step` is a 1-based index into the `bullets`
block on the *same slide*. Every image block with `callout` annotations must have its
`step` values form exactly `{1, 2, ..., N}` against that block's bullet count — no
duplicates, no gaps, nothing above N. `qa_training.py` check 6a hard-fails a mismatch,
because a circle with no matching instruction (or an instruction with no circle) is a
teaching defect a first read won't catch. A slide needs exactly one `bullets` block for
this to bind; if the instructions live as prose instead, number them as a bullets block
first rather than trying to bind against paragraph text.

**Not this when:** the slide's explanation is a single sentence, not a numbered list — a
lone highlight with a caption teaches the same thing with less clutter.

## `arrow` — point at something crowded

**Use when:** the target is real but too small, too close to another control, or outside
where a highlight box would read cleanly — a toolbar icon, a small link inline in a
paragraph of the screenshot, a status dot.

```json
{"type": "arrow", "from": [0.70, 0.40], "to": [0.56, 0.26], "step": 2}
```

`from`/`to` are both `[u, v]`; the arrowhead lands on `to`. Renders as a straight connector
with a solid triangular head.

**Not this when:** the target has real width and height worth showing — an arrow into the
middle of a wide field draws attention to a point, not the field's extent; use `highlight`.

## `redact` — mask client data

**Use when:** the screenshot shows real client data that shouldn't leave the training
deck — a vendor name, an employee ID, an org unit code, a dollar amount, an email address.
Given this project's clients (Singapore government and GLC programmes), treat this as a
mandatory pass over every screenshot pulled from a live system or a real FSD example, not
an optional nicety.

```json
{"type": "redact", "rect": [0.05, 0.05, 0.22, 0.04], "reason": "client vendor name"}
```

No `step` — a redaction is not an instruction. `reason` is required and goes in the QA
report, so a reviewer can see what was masked without having to find the original pixels.

**This is the one place burning pixels is not just allowed but required.** The shape
`render_annotation.py` draws is a solid block over the region — visually convincing, but
cosmetic: the original screenshot's pixels are still sitting in `ppt/media/`, one
"unzip the .pptx" away from recovery. Before placing a `redact` annotation, run:

```bash
python png_ops.py redact fsd-img-014.png -o fsd-img-014-r1.png --rect 0.05,0.05,0.22,0.04
```

register `fsd-img-014-r1` as a **new** `asset_index.json` entry with `"redacted_from":
"fsd-img-014"` set, and point the block's `asset_id` at the new, flattened asset — never
the original. `build_training_deck.py` and `qa_training.py` check 6c both hard-fail a
`redact` annotation whose block's asset has no `redacted_from`: the vector shape alone is
never accepted as sufficient, on the reasoning that a masked-looking screenshot that still
leaks the underlying data is worse than an obviously unredacted one — nobody double-checks
the thing that already looks handled.

## `zoom` — magnify a small element

**Use when:** the target is genuinely too small to read at the screenshot's placed size —
a Fiori tile in a dense launchpad, a toolbar icon, small print in a status column — and a
`highlight` or `arrow` alone wouldn't let a learner actually see it.

```json
{"type": "zoom", "rect": [0.40, 0.20, 0.10, 0.08], "scale": 3, "place": "right", "step": 3}
```

`render_annotation.py` draws the frame around the source region on the original screenshot
plus a dashed leader line toward `place` (`left`/`right`/`below`). The magnified inset
itself is a **separate** asset and a separate `image` block:

```bash
python png_ops.py crop fsd-img-014.png -o fsd-img-014-zoom1.png --rect 0.40,0.20,0.10,0.08 --scale 3
```

Nearest-neighbour upscaling is deliberate, not a limitation — it keeps the enlarged field
border and text crisp, where smoothing would blur exactly the detail the zoom exists to
show. Place the resulting `fsd-img-014-zoom1.png` as its own picture block beside the main
screenshot (`media_position: "right"` matching `place`), captioned with what it shows.

**Not this when:** the target is already legible at the screenshot's placed size — a zoom
inset is the most visually heavy annotation type and earns its slide real estate only when
nothing smaller would work.

## Coordinate and density discipline

- **One highlight/callout/arrow per distinguishable target.** Don't stack two callouts on
  the same point to cover two instructions — split the instruction or use one circle with
  a label naming both.
- **More than 6 annotations on one screenshot is a signal, not a rule** —
  `qa_training.py` reports it (not a hard fail) because it's almost always a sign the step
  belongs on two slides, not one. A screenshot dense enough to need seven callouts is
  usually a screen doing two procedures' worth of work.
- **A `label`, if used, should be short and literal** — the field or control's own name as
  it appears on screen, not an instruction ("Amount field", not "enter the amount here").
  The instruction itself lives in the bullet the callout is bound to.
- **Coordinates come from looking at the actual screenshot**, not from guessing typical
  Fiori layout proportions. A dense SAP screen genuinely needs the verify loop below —
  don't skip it because the target "should" be roughly where a similar screen usually has
  it.

## The verify loop

Coordinate precision on a dense screen (a Fiori worklist, a multi-tab config screen) is
the real risk in this whole feature — not the shape drawing, which is exact once the
coordinates are right. After building the slide:

1. `soffice --headless --convert-to pdf` the built deck, then `soffice --convert-to png`
   the relevant page(s) — LibreOffice emits PNG directly, since this container has no
   `pdftoppm`.
2. Look at the rendered slide. For each annotation, check: does the highlight actually
   enclose the named control and nothing else? Does the callout circle sit on empty space
   near its target, not covering it? Does the arrowhead land on the target? Is the redacted
   region fully covered with margin on every side?
3. Correct any wrong coordinate in `deck_plan.json`, re-render just that slide's
   `annotations.xml` fragment, re-inject.
4. Repeat.

**Exit conditions:**

- **Success** — every annotation checks out on a pass with no corrections needed.
- **Cap — 3 correction passes.** If an annotation is still wrong after three passes,
  it does not ship silently: drop the shape, fold what it was pointing at into the
  caption text instead ("the Amount field, top-right of the header block"), and list the
  slide in `qa_report.md` under callouts needing manual placement, with the rendered PNG
  path for a human to finish by eye. A wrong circle actively misleads a learner; no circle
  just under-serves them — the two are not equally bad.

`render_annotation.py --svg` gives a faster inner loop during authoring, before the first
LibreOffice round-trip — it needs no template or slide, just the annotations and the
image, and is close enough to the real render to catch a badly wrong coordinate early.
