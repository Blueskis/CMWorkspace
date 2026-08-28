# Training templates

Where a slide template for the training generator lives. Two kinds, one profile format.

## `html-training/` — the PoC template

A self-contained HTML deck template, so the pipeline can be exercised before a client's
approved training template is available. 14 layouts, a neutral theme, and vendored
`reveal.js` and `mermaid.js` (both MIT — see `vendor/LICENSE-*.txt`), so a rendered deck
opens from disk with no server and no network.

Everything template-specific is in `layouts.html` and `theme.css`. Both are editable
without touching Python — re-run `profile_template.py` afterwards so `template_profile.json`
stays in step with the layouts, since that profile is what a plan is validated against.

**This is a stand-in, and saying so is part of the handover.** Never present a deck built on
it as though it were on the client's template.

## Adding a client's `.potx`

Drop the file in this directory and profile it:

```bash
python skills/training-material-generator/scripts/profile_template.py \
    training-assets/templates/<client>.potx -o training/<run>/template_profile.json
```

The profiler lists the layouts and warns when there is no obvious home for a screenshot
walkthrough, a knowledge check or a diagram. Map those to the nearest layout the template
does have and record the mapping in the plan; never plan a slide onto a layout that cannot
hold it.

Pair it with the `pptx` skill's `scripts/thumbnail.py` — the profile tells you what a layout
contains, the thumbnail grid tells you what it looks like.

If someone asks for a `.pptx` and there is no client template, **stop and ask for one**. A
lookalike built from scratch is not the client's template, and the requirement was the
template.
