# Templates

Two live here, and only one of them is a real answer.

| | What it is |
|---|---|
| `pptx-generic/pptx-generic.potx` | A plain, generated stand-in so the pipeline can produce a real `.pptx` before the firm's template exists. **Not the firm's template. Never present it as one.** |
| `html-generic/` | The same nine layouts as an HTML deck — useful for a fast look in a browser, and for a PDF via print |
| *(the firm's approved `.potx`)* | Not in this repository. Firm-specific and usually confidential. Drop it in. |

All three answer to the **same placeholder names** (`title`, `kicker`, `body`, `left`,
`situation`, `metrics`, …), so one `proposal_plan.json` renders to any of them without a
single edit. That is the property that makes switching templates cheap.

## Adding the firm's approved template

1. Copy it in, e.g. `proposal-assets/templates/firm-proposal-template.potx`.
2. Profile it, so a plan can be validated against what the template actually has:

   ```bash
   python skills/cm-proposal-generator/scripts/profile_template.py \
       proposal-assets/templates/firm-proposal-template.potx \
       -o proposal-assets/templates/template_profile.json
   ```

3. Look at it. `profile_template.py` says what each layout *contains*; thumbnails say what
   it *looks like* (the `pptx` skill's `scripts/thumbnail.py` — copy the `.potx` to a
   `.pptx` name first, as it only accepts `.pptx`). If the template ships with example
   slides, those are the best guide to intended usage.
4. Write a `template_map.json` next to it. See `template_map.example.json`.
5. Build:

   ```bash
   python skills/cm-proposal-generator/scripts/render_pptx.py proposals/<run>/proposal_plan.json \
       proposal-assets/templates/firm-proposal-template.potx \
       --map proposal-assets/templates/template_map.json \
       -o proposals/<run>/proposal.pptx
   ```

## What the map is for

Two jobs.

**Retargeting**, which the renderer reads. A plan names layouts and placeholders in the
canonical vocabulary; the firm's template calls the section divider "Divider" and its body
"Content Placeholder 2". `layout_aliases` and `placeholder_aliases` bridge that, so moving
a plan onto the firm's template is a config change rather than a rewrite. Normalised
matching handles the easy half already — `title-slide` finds a layout named `Title Slide`
without any configuration — so only genuine differences need listing.

**House style**, which is advisory. The `sections` block records which layout each kind of
section should normally use. Without that judgement written down somewhere, every section
lands on whichever layout looks safest — usually title-and-bullets — and the deck reads as
twenty identical slides.

## Regenerating the generic template

`pptx-generic.potx` is generated, not hand-built, so every colour, font size and
placeholder position is a line of Python rather than an opaque binary:

```bash
python skills/cm-proposal-generator/scripts/make_pptx_template.py \
    -o proposal-assets/templates/pptx-generic/pptx-generic.potx
python skills/cm-proposal-generator/scripts/profile_template.py \
    proposal-assets/templates/pptx-generic/pptx-generic.potx \
    -o proposal-assets/templates/pptx-generic/template_profile.json
```

Always re-profile after regenerating — the profile is what plans are validated against,
and a stale one validates against a template that no longer exists.
