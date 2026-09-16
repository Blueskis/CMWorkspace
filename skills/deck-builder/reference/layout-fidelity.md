# Layout fidelity — why never build a lookalike

The three defects that make a deck read as AI-generated, and how this skill checks each
one mechanically before a slide is assembled:

**Repeated layout.** `plan_deck.py` shells out to `lib/deck/cli/check-fit.mjs`'s variety
gate: no more than two consecutive slides on one layout — a hard failure, not a style
note. A picture-capable layout the plan never uses at all is a warning.

**Text overflow.** The same call runs `lib/deck/fit-check.js`'s fit gate against the
exact placeholder geometry the assembler will use, with the same line-wrap arithmetic
`composeSlide` uses at build time — a "fits" verdict at plan time means what it means at
build time. Text that only fits below the floor size is a hard failure: cut the copy or
split the slide, never ship it smaller than legible.

**Ignoring the template's own slots.** `lib/deck/map-layouts.js`'s `resolveLayoutRoles()`
maps every slide role to a real layout by **placeholder signature, not name** — client
templates name layouts unpredictably ("Content 1/2/3", localised names). When a role has
no dedicated layout, it degrades onto the closest available one (marked `auto: false`,
with a stated reason) rather than failing outright — a template with no picture layout
still produces a deck, with screenshots aspect-fit into the content area as free-floating
pictures. The mapping is always a **proposal**: Stage 1 shows it and lets a human override
any role before Stage 4 builds anything.

**Never build from scratch when an approved template exists.** If `--template` is not
supplied, `intake.py`'s `--template` is a required argument — the run stops rather than
approximating a lookalike deck. This mirrors the repo-wide rule already stated in
`cm-comms-generator`'s `build_pptx.py` and the `pptx` skill's own template workflow.

**Known gap:** the template profiler (`lib/deck/profile-template.js`) does not currently
record which slide master each layout belongs to. On a template with multiple masters,
`resolveLayoutRoles()` can in principle assign different roles from different masters in
one deck. This has not caused a visible defect in testing against
`webapp/test/fixtures/templates/two-masters.pptx`, but it is not enforced — treat a
multi-master template's mapping as one to check by eye in the Stage 1 review before
building.
