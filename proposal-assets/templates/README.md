# Approved Templates

Drop the firm's approved PowerPoint template here as `.potx` (or `.pptx`).

There is no template in this repository — it's firm-specific and often
confidential, so it isn't checked in. The skill will stop and ask for one rather than
building an approximation, which is the correct behaviour: "built on the company-approved
template" is the deliverable's whole requirement, and a lookalike fails it.

## Adding one

1. Copy the template in, e.g. `proposal-assets/templates/firm-proposal-template.potx`.
2. Profile it so the skill knows what layouts it has:

   ```bash
   python skills/cm-proposal-generator/scripts/profile_template.py \
       proposal-assets/templates/firm-proposal-template.potx \
       -o proposal-assets/templates/firm-proposal-template.profile.json
   ```

3. Thumbnail it to see the house style (the `pptx` skill's tooling — copy a `.potx` to a
   `.pptx` name first, since thumbnail.py only accepts `.pptx`):

   ```bash
   cp firm-proposal-template.potx /tmp/firm-template.pptx
   python ~/.claude/skills/pptx/scripts/thumbnail.py /tmp/firm-template.pptx firm-template-thumbs
   ```

4. Write a `template_map.json` next to the template, mapping proposal sections to the
   layouts that suit them. See `template_map.example.json`.

## Why the map matters

Without it, every section lands on whichever layout looks safest — usually
title-and-bullets — and the deck reads as twenty identical slides. The map is where the
practitioner's judgement about the firm's house style gets encoded once and reused across
every bid.

If the template ships with example slides, they're the best guide to intended usage:
thumbnail them and mirror how each layout is actually used in practice.

## Shared with the comms generator

`html-generic/` is used by both skills. `cm-comms-generator`'s slide-deck channel renders
through the same `render_html.py` against the same layouts, so a change here affects both —
re-run `profile_template.py` and re-render both worked examples after editing `layouts.html`.

The comms skill never renders directly from this directory. `apply_brand.py` copies it into
the run and appends a client palette override, so each comms run keeps a snapshot of exactly
what it was built on. A recoloured copy is still the generic template, not the client's
approved one.

Client brand profiles — palette, typography, voice, channel specs — live one level up in
`../brand-profiles/`, not here. This folder is for slide templates.
