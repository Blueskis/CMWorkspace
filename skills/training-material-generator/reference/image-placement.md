# Placing screenshots

A specification's screenshots are the most valuable thing in it for training, and the easiest
to get subtly wrong.

## Which capture goes on which slide

Two signals, and they agree most of the time:

1. **The heading it sat under.** A capture under `4.1 Create Purchase Order screen` belongs
   on the Create PO walkthrough. The ingester records `heading_path` and `anchor` for exactly
   this.
2. **Its position in the document.** `ordinal` preserves document order, so where a section
   has three captures they are the three steps of the task, in order.

Where they disagree — a capture that sits under one heading but clearly shows another
screen — trust the caption and the image itself, and say in the plan why you moved it.

## The rules

**Place the original bytes. Never re-encode.** The image on the slide should be byte-identical
to the one in the specification. A recompressed screenshot loses exactly the thing that makes
it useful: the legibility of the field labels.

**No cropping, no burned-on annotations, in v0.1.** Callouts are numbered steps rendered
*beside* the image by the layout. This is a deliberate constraint, not a missing feature:

- the capture stays an unmodified artifact of the spec, so a reviewer can compare it to the
  source without wondering what we changed;
- the steps stay editable, translatable, and readable by a screen reader;
- and a numbered circle burned onto a screenshot is wrong the moment the screen moves, while
  a numbered step beside it is still true.

**A capture too small for its placeholder is unusable, not resizable.** Upscaling a 400px
screenshot to fill a slide produces something that looks like a screenshot and cannot be read.
Record it in `excluded_assets` with the reason and ask for a recapture. Stage 5 flags placed
images under 600px wide for exactly this.

**A capture the specification itself says is out of date is stale, not usable.** Specs
sometimes carry a "screen shown is indicative" note or describe a field the capture does not
show. Flag it rather than teaching from it.

**Every screenshot is placed or explicitly dismissed.** There is no third state, and Stage 5
fails on one that is neither. `excluded_assets` takes a reason — a duplicate, a screen out of
scope, a resolution too low, or an image redrawn as a diagram. The reason is the point: it
records that someone looked.

## What to write beside the image

Numbered steps, one action each, in the order the learner performs them. Two habits worth
keeping:

- **Name the control exactly as the screen labels it.** "Select the Supplier" — not "choose a
  vendor", not "pick the supplier from the dropdown" if the label says Supplier.
- **Put the rule with the step it constrains**, not in a separate rules block, where the step
  is where the learner will hit it: "Set the Delivery Date. It must be today or later."

The caption is different from the steps: it says what the reader is looking at and calls out
anything the steps do not cover. "Create Purchase Order — header above, lines grid below.
Order Total is calculated and cannot be typed."

## When there is no capture

A walkthrough with no screenshot is a walkthrough of an imaginary screen. If the
specification has no capture for a screen the audience must operate, that is a `[GAP]` with a
named action — someone has to capture it from the build — not something to work around with a
wordier bullet list.

## Logos, icons and page furniture

Handled by classification rather than by judgement: an image classified `logo` or `icon` is
not a placement candidate and is not subject to the triage check. The one thing to watch is
the reverse error — a real screenshot classified as an icon disappears silently, so look over
the ingest summary and reclassify anything that came out `unknown`.
