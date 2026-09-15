# Brand Profiles

One `brand_profile.json` per client, carrying their approved theme, voice and channel
specifications. Read by `cm-comms-generator`; copied into a run workspace at Stage 1.

Naming: `<client-slug>.brand_profile.json`.

Schema and authoring guidance:
- `skills/cm-comms-generator/schemas/brand_profile.schema.json`
- `skills/cm-comms-generator/reference/brand-profile-guide.md`

## The rule

**Never build a brand lookalike.** No approved template and no brand guide means stop and ask,
not approximate from the client's website. Comms go out to a whole employee base under the
client's name; an off-brand all-staff email is a visible failure in a way an off-brand bid
slide is not.

The schema enforces this as far as a schema can: `approval` is required, `source` has no
`inferred` value, and both `apply_brand.py` and `qa_comms.py` exit non-zero when
`approval.approved_by` is empty.

## Real profiles are not committed here

`northwind.brand_profile.EXAMPLE.json` is an invented example for the worked example in
`examples/northwind-payroll/`. Real client profiles carry a real client's brand rules and
should live wherever the firm keeps client-confidential material — not in this repo.

## The two authoring routes

**Hand-authored from the client's brand guidelines** is the default and the only route that
produces a complete profile.

**Extracted from a supplied `.potx`** is the backup, and recovers less than people expect:
`profile_template.py` reads layouts, placeholders, geometry and theme *fonts* — it does not
parse `a:clrScheme`, so colours are a manual read, and `.docx`/`.dotx` are rejected outright.
The guide has the `unzip` recipe and the full recovery table.

Tone of voice is hand-written on both routes. Nothing extracts it.

## Deloitte (unapproved — internal drafting only)

`deloitte.brand_profile.EXAMPLE.json` carries the Deloitte Green Dot palette (ten colours,
hex/RGB/CMYK/Pantone) pulled from `proposal-assets/templates/html-deloitte/theme.css` — the
same "not an official download" build used for the proposal-generator's Deloitte template.

**`approval` is deliberately left empty.** Every producer script refuses to run against it —
verified: `apply_brand.py`, `qa_comms.py`, `canva_brief.py` and `route_channel.py` all exit
non-zero with "brand profile has no recorded approval." That is correct behaviour, not a bug
to fix: this palette has no real Deloitte brand/legal sign-off behind it, and the schema's
approval gate exists exactly to stop a run in that situation rather than draft on a lookalike.

Before this profile can produce anything: get a real approver from Deloitte's own brand or
legal function, confirm the palette and typography against current Brand Space guidance (no
licensed wordmark typeface ships here — headings and body both fall back to system Segoe UI),
and only then fill in `approval.approved_by`, `.role` and `.approved_date`.
