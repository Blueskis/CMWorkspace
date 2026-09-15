# Deloitte-Palette HTML Template

A minimalist proposal template built around the Deloitte Green Dot identity — a black
wordmark, the green dot as its fixed full stop, and color used as a signal rather than a
fill. Same layout set and placeholder contract as `html-generic`, so a `proposal_plan.json`
validates and renders against either template unchanged; only `theme.css` and the static
`.brand-mark` furniture in `layouts.html` differ.

## ⚠️ Not an official download

This was assembled from a supplied color spec (hex/RGB/CMYK/Pantone values for the ten
Deloitte Green Dot colors) and general knowledge of the public identity — **not** the
firm's licensed Brand Space assets, approved master template, or real wordmark typeface
(no web font ships here; the wordmark renders in the system sans-serif stack, not
Deloitte's proprietary face). Treat it as a close approximation for internal drafting and
dry-runs, not a substitute for the real thing.

Before anything client-facing or external:

1. **Verify against the current Brand Space guidelines** — clear-space and minimum-size
   rules for the dot, correct typography, correct color usage by application, are not
   independently confirmed here.
2. **Get brand/legal sign-off** on using the Deloitte name and mark at all — this template
   only makes sense inside an actual Deloitte engagement or internal context; it must
   never be used to imply an affiliation that doesn't exist.
3. **Swap in the real template** per the top-level README's setup step once it's
   available — this stays a stand-in, same as `html-generic`.

## Palette

All ten colors from the supplied Green Dot spec are in `theme.css` as CSS custom
properties. Two (`--green-bright`, `--green-pale`) carry the print caveats from the
source spec verbatim — bright green has no CMYK equivalent (Pantone only, screen-safe
micro-accents here), pale green has no Pantone equivalent (CMYK only).

| Token | Hex | Use in this theme |
|---|---|---|
| `--green` | `#86BC25` | Primary accent — rules, bullets, the dot itself |
| `--green-mid` | `#26890D` | Kickers, eyebrow labels, role text |
| `--green-deep` | `#046A38` | Tagline |
| `--green-dark` | `#1C3D26` | Reserved — not used at this saturation of minimalism |
| `--green-bright` | `#0DF200` | Reserved — none used; too loud for the minimalist brief |
| `--green-pale` | `#F1F6E4` | Section-header decorative circle, source-tag chips |
| `--black` | `#000000` | Wordmark, headings, primary text |
| `--gray-dark` | `#222222` | Body copy |
| `--gray-light` | `#E6E6E6` | Hairlines, dividers, panel borders |
| `--white` | `#FFFFFF` | Canvas — every slide is white, never a color fill |

`--gap-amber` / `--gap-bg` are functional, deliberately off-palette — a `[GAP]` block
must never read as a brand-color callout.

## Design choices

- **Thin lines, not blocks.** Every accent is a 1–3px rule or a panel outline. No filled
  color panels, no gradients, no shadows — matches the "mostly thin lines" brief and the
  Green Dot identity's own restraint (green marks a point, it doesn't fill a page).
- **The dot is the only graphic device.** It appears in the wordmark, the tagline, and —
  once, large and pale — behind the section-header title. Nowhere else.
- **Tagline set once per deck**, on the title slide only ("Together makes progress"),
  under the source lockup at
  <https://mma.prnewswire.com/media/2700126/Deloitte_Together_makes_progress_Logo.jpg> —
  not repeated on every slide, so it reads as a statement rather than wallpaper.
- **`.brand-mark`** (the small wordmark + dot, top-right of every slide) is static markup
  in `layouts.html`, not a placeholder — a plan can't fill or drop it. Copy it into any
  new layout you add.

## Rendering

```bash
python skills/cm-proposal-generator/scripts/render_html.py \
    proposals/<run>/proposal_plan.json \
    proposal-assets/templates/html-deloitte \
    -o proposals/<run>/proposal.html
```

Everything else — layouts, placeholders, editing workflow, known constraints (slide
overflow clips silently, case studies run a step smaller) — is identical to
`html-generic`; see that folder's README for details that aren't palette-specific.
