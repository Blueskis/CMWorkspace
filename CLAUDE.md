# CM Workspace

Change-management working tools, packaged as a Claude Code plugin. See `README.md` for the
skills themselves.

## Artifact house style

Every HTML artifact published from this project uses the same visual system — colour tokens,
fonts, and a light/dark toggle — first established in the **CM Effort & Pricing Estimator**
artifact and carried forward into **Change Impact Intake**. Apply it by default; only deviate
when the user explicitly asks for a different visual direction for that one artifact.

### Tokens

```css
:root {
  color-scheme: light dark;
  --paper: #F3F5F9;
  --surface: #FFFFFF;
  --surface-2: #EAEEF5;
  --ink: #12161F;
  --ink-2: #4C5666;
  --ink-3: #7A8494;
  --line: #DCE1EA;
  --line-strong: #BFC7D4;
  --accent: #2E3D77;
  --accent-ink: #FFFFFF;
  --accent-soft: #E4E8F6;
  --jade: #0B6B54;       /* semantic: success / low / good */
  --jade-soft: #E0F0EA;
  --amber: #8C5E0C;      /* semantic: warning / medium */
  --amber-soft: #F7EBD5;
  --clay: #A33D2E;       /* semantic: critical / high / error */
  --clay-soft: #F7E4E0;
  --shadow: 0 1px 2px rgba(18, 22, 31, .06), 0 8px 24px -16px rgba(18, 22, 31, .35);

  --font-display: ui-serif, "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  --font-body: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --paper: #0E1117; --surface: #171B23; --surface-2: #1F242E;
    --ink: #E8EBF2; --ink-2: #A5AEBD; --ink-3: #7B8494;
    --line: #2A303B; --line-strong: #3B4351;
    --accent: #97A5EA; --accent-ink: #10131B; --accent-soft: #1C2340;
    --jade: #4FC7A0; --jade-soft: #12302A;
    --amber: #D9A54E; --amber-soft: #2E2617;
    --clay: #E38375; --clay-soft: #33201D;
    --shadow: 0 1px 2px rgba(0, 0, 0, .5), 0 8px 24px -16px rgba(0, 0, 0, .8);
  }
}
:root[data-theme="dark"] { /* same values as the dark media block above, so the toggle wins */ }
```

Deliberately **system fonts only — no Google Fonts link**. A serif display face for headings
(`--font-display`), system-ui for body and controls (`--font-body`), and a monospace face for
codes, IDs, and tabular data (`--font-mono`). This keeps every artifact self-contained with
zero network dependency for type, and gives the suite a consistent "considered enterprise
tool" register rather than a decorative one.

Semantic colours (`--jade`/`--amber`/`--clay`) are independent of `--accent` — never repurpose
the accent hue for status. `--accent` is interaction (buttons, active tab, links); the three
semantic pairs are state (good/warning/critical), each with a `-soft` background for pill/chip
fills.

### Toggle button

Every artifact gets a light/dark toggle in its header toolbar — a plain-labelled button, not
an icon, matching the existing suite:

```html
<button type="button" class="btn ghost small" data-action="toggle-theme" title="Toggle light/dark">Theme</button>
```

```js
// inside whatever click-delegation the page already uses:
} else if (action === "toggle-theme") {
  var docEl = document.documentElement;
  var cur = docEl.getAttribute("data-theme");
  var isDark = cur ? cur === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  docEl.setAttribute("data-theme", isDark ? "light" : "dark");
}
```

This does not persist across reloads (matches `CM Effort & Pricing Estimator`'s own
behaviour) — each load starts from the viewer's system preference, same as any artifact
without a toggle. Don't add `localStorage` persistence to "improve" this; consistency across
the suite matters more than any one page's convenience, and every artifact in this project
should behave identically here.

### Component vocabulary

Reuse these class names and roles rather than inventing new ones per artifact:

- `.appbar` / `.brand` — sticky header, page title (`--font-display`) + one-line subtitle
  (`--ink-3`), toolbar row (`.row`) with the theme toggle and any other page-level controls
- `.btn` (+ `.primary` / `.ghost` / `.small` / `.danger`) — the one button system
- `.card` — `var(--surface)` background, `var(--line)` border, `10px` radius, `var(--shadow)`
- `.eyebrow` — `--font-mono`, uppercase, letter-spaced, `--ink-3` — small tracked labels
- `.num` / `font-variant-numeric: tabular-nums` — anywhere digits line up in a column
- Inputs: `var(--surface)` background, `var(--line-strong)` border, `6px` radius

### Where this came from

Extracted directly from the published `CM Effort & Pricing Estimator` artifact
(`https://claude.ai/code/artifact/d3aa3018-94a9-4b46-a023-554815335eee`) at the user's
request, then applied to `Change Impact Intake`
(`https://claude.ai/code/artifact/4f937bb9-ee6d-41bf-ab6e-dabeed14bd55`). If either drifts
from this file, treat this file as the source of truth and re-sync the artifact, not the
other way round.
