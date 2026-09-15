# Screenshot Placement Guide

Rules for turning `asset_index.json` entries into `image` blocks in `deck_plan.json`
during Stage 3. Read `extract_assets.py`'s docstring first for how assets get extracted
and classified; this covers what to do with them once you have them.

## Placing an asset

1. **Match by `section_id`.** Every task-walkthrough slide teaches a specific
   `source_map.json` section. Place the screenshot(s) whose `asset_index.json` entry
   carries that same `section_id` — that's the image the FSD itself paired with that step.
   An asset with no matching slide is either genuinely decorative (leave it out) or a sign
   the module plan missed a step (check Stage 2 again).

2. **One screenshot per step, not a contact sheet.** If a procedure has four screenshots
   for four steps, that's four slides (or four positions within a multi-image layout),
   never one slide with four thumbnails crammed in. A shrunk screenshot is unreadable and
   defeats the entire purpose of including it.

2a. **Prefer side by side when the step's explanation is short.** A screenshot with 3-5
   short explanatory bullets reads better next to the bullets than as two separate slides —
   use a "content"-role slide with a body block and a picture block together, not a
   dedicated "picture" slide, when the step doesn't need the screenshot at full size. Fall
   back to a full-slide "picture" role only when the screenshot itself needs the room (a
   dense form, a full worklist, small print that would shrink further in a half-width
   column).

3. **Aspect-fit, never distort.** `inject_slide_xml.py`'s `picture` command aspect-fits
   automatically, centered in the target bbox — don't fight this by hand-stretching an
   image to fill a placeholder exactly. A letterboxed screenshot is more readable than a
   warped one.

4. **Caption from the FSD, not invented.** Use `caption_candidate` if present (usually a
   "Figure N: ..." line the FSD itself wrote); otherwise write a short, literal caption
   describing what's on screen — never a caption that asserts something the screenshot
   doesn't actually show. Callout numbering (circling field 3, say) goes in the caption
   text ("① Amount field"), never burned into the image — this repo has no image-editing
   step, and burning text into a raster image also breaks localization/updates later.

5. **`alt_text`, when the source document set it, is a bonus, not a substitute for a
   caption.** Use it to sanity-check the caption, not as the caption itself — `alt_text`
   is often terse ("Picture 1") and unhelpful.

## When *not* to place an asset

- **`role: "icon"`, `"logo"`, or `"decorative"`** — never placed as a content screenshot.
  These exist in `asset_index.json` for completeness, not because they belong in the deck.
- **`role: "diagram-image"`** (an EMF/WMF/SVG the FSD itself used for a diagram) — prefer
  rebuilding it as a native diagram via `render_diagram.py` if the underlying logic is
  simple enough to describe in a `diagram_spec` (see `reference/diagram-patterns.md`).
  Fall back to placing it as an image only if the original is genuinely too complex to
  re-derive, and say so in the block's content.
- **`quality: ["low_res"]`** — can still be placed, but only with `content.ack_low_res:
  true` set explicitly. `build_training_deck.py` refuses an unacknowledged low-res
  placement outright. Acknowledging it is a deliberate call ("this is the only screenshot
  the FSD has for this step, blurry as it is") — don't set the flag reflexively just to
  get past validation; if a sharper source exists, use that instead.
- **`quality: ["tiny"]`** — almost never worth placing as a standalone content image;
  usually indicates the asset is actually an icon that `guess_role` mis-classified.
  Sanity-check the role before placing.

## Unplaced assets

Every `role: "screenshot"` asset must end up either placed on a slide or listed in
`deck_plan.json`'s `unused_assets` with a reason (a genuine duplicate, an out-of-scope
section's screenshot, an image that turned out decorative on closer look).
`qa_training.py`'s asset-hygiene check reports — not hard-fails — any screenshot that's
neither, because leaving a decision unmade is different from a defect, but it still needs
a human decision before handover, not silence.
