# Brand Profile Guide

How to produce a `brand_profile.json` for a client, and what the automated route can and
cannot recover.

Schema: `../schemas/brand_profile.schema.json`. Store finished profiles in
`proposal-assets/brand-profiles/<client>.brand_profile.json` and copy one into a run workspace
at Stage 1.

## The rule this file exists to enforce

**Never build a brand lookalike.** If there is no approved template and no brand guide, stop and
ask for one. Do not approximate a palette from the client's website, their logo, or a PDF
somebody screenshotted. This matters more here than it does for a proposal deck: comms go out
to a whole employee base *under the client's name*, and an off-brand all-staff email is a
visible failure in a way an off-brand bid slide is not.

The schema encodes this mechanically. `approval` is required, there is deliberately **no
`inferred` value** for `source`, and both `apply_brand.py` and `qa_comms.py` exit non-zero when
`approval.approved_by` is empty. A profile with no approval is treated as no profile at all.

## Primary path — hand-authored

The default, and the only route that produces a complete profile. The practitioner fills the
profile once per client, reading from the client's brand guidelines.

Everything in the schema is fillable this way. Three blocks are worth extra care:

- **`palette`** — the keys map 1:1 onto the CSS custom properties in the HTML template's
  `theme.css`, which is how `apply_brand.py` recolours a deck without touching a single layout.
  `ink` is headings, `ink_soft` is body text, `canvas` is the slide background. Getting
  `ink`/`canvas` wrong is what produces an unreadable deck, so `apply_brand.py` computes the
  WCAG contrast of every pair it writes and refuses anything below
  `accessibility.min_contrast_ratio`.
- **`tone`** — voice, person, formality, `banned_words`, `preferred_terms`. **No extraction of
  any kind produces this.** It is always hand-written. `banned_words` and `preferred_terms` are
  checked mechanically against every block of draft text, so they are worth filling properly:
  they are the cheapest quality gate in the pipeline.
- **`channel_specs`** — every stated limit becomes a hard failure in Stage 4. Where the client
  has no stated limit, leave it out and the channel library's default applies as a warning
  instead. Do not invent a limit to make the check pass.

## Backup path — extraction from a supplied template

Use only when the client supplied a file and nothing else. **Be honest about what this
recovers**, because it is less than people assume:

```bash
python skills/cm-proposal-generator/scripts/profile_template.py <client>.potx \
    -o comms/<client>/template_profile.json
```

| Recovers | Does not recover |
|---|---|
| Layout names and their placeholder inventories | **Theme colours** — `profile_template.py` parses `a:fontScheme` only; `a:clrScheme` is never read |
| Placeholder geometry, in inches | Tone of voice, in any form |
| Theme fonts — the major/minor latin typefaces | Logo usage rules, clear space, prohibitions |
| | Channel specs and accessibility targets |

So the backup path fills `typography.heading.family` and `typography.body.family`, and confirms
which layouts exist. **Colours have to be read out by hand:**

```bash
unzip -p <client>.potx ppt/theme/theme1.xml | tr '>' '>\n' | grep -A1 'a:srgbClr'
```

Take the `a:clrScheme` values — `dk1`/`dk2` map to `ink`/`ink_soft`, `lt1`/`lt2` to
`canvas`/`panel`, `accent1` to `accent` — and write them into the profile with real names.

**Word templates are not supported by this route at all.** `profile_template.py` accepts
`.potx`, `.pptx`, or an HTML template directory, and rejects `.docx`/`.dotx` outright. For a
Word-only client, read the styles with the `docx` skill and author the profile by hand.

Either way, set `source: "extracted-from-template"`, list the file under `source_files`, and
have a human fill `approval`.

## Applying the profile to the deck channel

```bash
python skills/cm-comms-generator/scripts/apply_brand.py \
    comms/<client>/brand_profile.json \
    proposal-assets/templates/html-generic \
    -o comms/<client>/runs/<run>/template
```

This copies the template directory into the run and appends a generated `:root { … }` override
to the copied `theme.css`. The run keeps its own snapshot of the exact template it was built
on, which is better provenance than a flag on the renderer.

Two things it deliberately does not do: it does not alter layouts, and **it does not place the
client's logo** — that needs an asset the repo does not have and a placement judgement a script
should not make. Both stay practitioner steps, and both are listed in the QA report's human
checklist.

**A palette-swapped generic template is still the generic template.** It is a proof-of-concept
render carrying the client's colours, not the client's approved deck. Say exactly that at
handover, every time.

## Fonts in the HTML render

The template fetches no webfonts by design, so the deck opens identically offline. A brand
typeface that is not installed on the viewer's machine will silently fall back. Fill
`typography.web_safe_fallback` with what you are willing to see instead, and treat the HTML
render's typography as indicative rather than final.
