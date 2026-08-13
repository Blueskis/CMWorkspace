# Generic Business HTML Template (PoC)

A neutral, business-suitable slide template so the proposal pipeline can be exercised
end to end before the firm's approved PowerPoint template is available.

**This is a stand-in.** It is not anyone's brand. Decks built on it must never be
presented as being on the firm's approved template — see the note in the skill's Stage 5.

## What's here

| File | Purpose |
|---|---|
| `layouts.html` | The 9 layouts, as `<template data-layout>` blocks with `{{placeholder}}` tokens |
| `theme.css` | All styling — palette, type, layout rules |
| `template_profile.json` | Generated from `layouts.html`; what a plan is validated against |
| `vendor/` | reveal.js 5.1.0 (MIT), vendored — `reveal.css`, `reset.css`, `reveal.js` |

reveal.js supplies slide navigation and print-to-PDF. Its CSS references only data-URIs,
so a rendered deck is fully self-contained: no CDN, no webfonts, no network. The theme
uses system fonts for the same reason — the deck looks the same offline.

## Layouts

| Layout | Required placeholders | Optional |
|---|---|---|
| `title-slide` | `client`, `title`, `meta` | `subtitle` |
| `section-header` | `title` | `kicker`, `body` |
| `title-and-content` | `title`, `body` | `kicker` |
| `two-content` | `title`, `left`, `right` | `kicker`, `left_heading`, `right_heading` |
| `case-study` | `title`, `situation`, `action`, `outcome` | `kicker`, `metrics` |
| `metric-row` | `title`, `metrics` | `kicker`, `body` |
| `table` | `title`, `table` | `kicker`, `body` |
| `timeline` | `title`, `phases` | `kicker`, `body` |
| `team-grid` | `title`, `members` | `kicker`, `footer` |

`footer` is filled by the renderer (sources and slide number) — plans should not target it.

## Block kinds

`text` (bare, for slots the layout already wraps), `heading`, `paragraph`, `bullets`,
`table` (`{headers, rows}`), `metric` (`[{value, label}]`), `phases`
(`[{label, name, detail}]`), `members` (`[{name, role, bio}]`), `image`.

**Use `text`, not `heading`, for `title` / `client` / `kicker` / column headings.** The
layout already wraps those in an element; `heading` nests an `<h3>` inside and loses the
layout's styling.

## Rendering

```bash
python skills/cm-proposal-generator/scripts/render_html.py \
    proposals/<run>/proposal_plan.json \
    proposal-assets/templates/html-generic \
    -o proposals/<run>/proposal.html
```

Open the `.html` in any browser. Arrow keys or space to advance. For PDF, append
`?print-pdf` to the URL and print to PDF — most RFPs require PDF, not HTML.

## Editing

Change `layouts.html` or `theme.css` freely — no Python changes needed. **Re-run
`profile_template.py` after editing layouts**, or the profile a plan is validated against
will have drifted from the layouts that actually render:

```bash
python skills/cm-proposal-generator/scripts/profile_template.py \
    proposal-assets/templates/html-generic/ \
    -o proposal-assets/templates/html-generic/template_profile.json
```

A placeholder is inferred as optional when it sits inside a `{{#name}}...{{/name}}`
region, which the renderer drops entirely when there's no content for it — so a layout
degrades cleanly instead of leaving an empty panel behind.

## Known constraints

- `.slide-body` clips overflow rather than spilling, so an over-full slide loses content
  silently. Always step through a rendered deck; check text-heavy slides first.
- Case-study slides run a step smaller than body text because they carry the most content.
  Very long case studies still need splitting across two slides.
