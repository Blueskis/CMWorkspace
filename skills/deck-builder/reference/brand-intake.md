# Brand intake

Three routes into `lib/schemas/brand_profile.schema.json`'s canonical shape, all through
`lib/brand_profile.py`:

1. **A file already in canonical shape** — validated and passed through.
2. **`--from-vault <export.json>`** — the Brand Vault artifact's export. Adapted:
   `colors.*` → `palette.*`, `typography.headingFont/bodyFont` → `typography.heading/
   body.family`, `logo.dataUri` kept as-is, `voice.*` → `tone.*`, `messaging` carried
   through unchanged (deck-builder's retrieval query-expansion reads
   `messaging.terminology` directly).
3. **`--from-template <.potx>`** — extracted from the template's own theme via
   `lib/profile_template.py`'s `theme_colors`/`theme_fonts`, mapped onto palette roles
   (accent1→primary, accent2→secondary, accent3→accent, the darker of dk1/dk2→ink, the
   lighter of lt1/lt2→canvas) and the major/minor font scheme.

**None of the three ever invents an `approval` block.** A profile with `approval` empty
is treated as no profile at all — every producer stops and asks rather than proceeding
with an unapproved palette, whatever the profile's origin. This is the mechanical form of
"never build a lookalike," extended from templates to brand.

`--format pptx|docx|html` emits a flat producer theme and checks every ink/canvas pair
named in `accessibility.min_contrast_ratio` (default 4.5, WCAG AA) — a failing pair is
reported by name and ratio, and the run still writes the theme (so it can be inspected)
but exits non-zero.

Two prior schemas had drifted apart before this skill reconciled them — see
`lib/schemas/brand_profile.schema.json`'s own description for the full history. Nothing
downstream should read `cm-comms-generator/schemas/brand_profile.schema.json` or
`artifacts/brand-template-creator/schemas/brand_profile.schema.json` directly again;
`lib/brand_profile.py` is the one adapter.
