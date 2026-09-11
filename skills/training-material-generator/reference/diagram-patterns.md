# Diagram Patterns

Which prose shape in an FSD maps to which of `render_diagram.py`'s five `diagram_type`
values, and the exact `spec` object each one expects. Get the type right before writing
the spec — picking the wrong type for what the FSD actually describes produces a diagram
that's technically valid but doesn't read as the thing it's illustrating.

A `deck_plan.json` `diagram` block's `content` is `{"diagram_type": "...", "spec": {...}}`
— exactly what `render_diagram.py` and `build_training_deck.py` both expect.

## `process` — numbered procedure steps

**Use when:** the FSD describes a single-role, linear sequence — "Step 1... Step 2...
Step 3..." with no branching and no handoff between roles. This is the most common shape
in a task-walkthrough module.

**Not this when:** more than one role acts, or the sequence branches. Use `swimlane` or
`decision` instead — forcing a multi-role or branching procedure into a flat `process`
diagram loses the information a learner most needs.

```json
{"steps": ["Create PO", "Submit for Approval", "Manager Review", "Approved & Posted"]}
```

Renders as a left-to-right box-and-arrow chain, one box per step.

## `swimlane` — role-by-step handoffs

**Use when:** the FSD's procedure crosses roles — a requester submits, an approver
reviews, finance posts. This is the natural choice for module 6 (roles and
responsibilities) and for any walkthrough where responsibility changes hands mid-process.

```json
{
  "roles": ["Requester", "Approver", "Finance"],
  "steps": [
    {"step": "Create PO", "role": "Requester"},
    {"step": "Submit", "role": "Requester"},
    {"step": "Review", "role": "Approver"},
    {"step": "Post", "role": "Finance"}
  ]
}
```

`roles` lists the lanes top-to-bottom; `steps` lists the sequence in order, each tagged
with the lane it belongs to. Every `role` value in `steps` must appear in `roles` —
`render_diagram.py` raises `DiagramSpecError` otherwise, so a typo'd role name fails loud
rather than silently drawing an empty lane.

## `decision` — "if X then Y" rules

**Use when:** the FSD states conditional routing — approval thresholds, escalation
triggers, routing logic ("amounts under $1,000 are auto-approved; over $10,000 require
Director approval"). This is the type most FSDs bury as prose (see
`reference/fsd-extraction.md`, point 6) and most benefit from being pulled out.

```json
{
  "rules": [
    {"condition": "Amount <= $1,000", "outcome": "Auto-approved"},
    {"condition": "$1,000 < Amount <= $10,000", "outcome": "Manager approval"},
    {"condition": "Amount > $10,000", "outcome": "Director approval"}
  ]
}
```

Each rule renders as a condition shape connected to its outcome. List rules in the FSD's
own order (usually ascending threshold) — that order is itself information.

## `hierarchy` — escalation or org structure

**Use when:** the FSD describes an approval escalation chain, a reporting structure, or
any strictly tree-shaped relationship (not a sequence, not role-by-step — a parent/child
structure).

```json
{
  "root": {
    "name": "Director",
    "children": [
      {"name": "Manager A", "children": [{"name": "Team Lead"}]},
      {"name": "Manager B"}
    ]
  }
}
```

Recursive: any node can carry a `children` array. Depth beyond 3-4 levels tends to
overflow a slide — if the FSD's real hierarchy is deeper, consider splitting it (e.g.,
one diagram per branch) rather than shrinking labels past readability.

## `timeline` — milestones and cut-over dates

**Use when:** the FSD (or the training brief) states dated milestones — a rollout
schedule, a phased cut-over, a training-then-go-live sequence. Rare inside procedural
walkthrough modules; more common on an opening or closing slide when training is tied to
a specific rollout.

```json
{
  "milestones": [
    {"label": "Kickoff", "date": "Jan 2026"},
    {"label": "UAT", "date": "Feb 2026"},
    {"label": "Go-live", "date": "Mar 2026"}
  ]
}
```

`date` is optional per milestone but should be included whenever the source states one —
an undated timeline is usually better as a plain `process` list.

## Sizing and the overflow rule

Every label is auto-fit against the `--bbox` you pass (normally the target layout's
placeholder geometry from `template_profile.json`). **If a label won't fit even at the
smallest allowed font (8pt), `render_diagram.py` raises rather than emitting clipped
text.** When that happens:

- Shorten the label — FSD field/status names are sometimes long; use the shortest form
  that's still the FSD's own wording, not a paraphrase.
- Split the diagram — a `process` with too many steps for one row can become two
  sequential diagrams across two slides; a `hierarchy` that's too deep can become one
  diagram per major branch.
- Widen the target — check whether a different, larger layout placeholder is available on
  the template before shrinking content to fit a small one.

Never retry with a larger font ceiling or a smaller minimum than `render_diagram.py`'s
defaults — those bounds (14pt down to 8pt) are chosen to stay legible on a projected
slide; going below them defeats the purpose of catching overflow at all.

## Colour and font discipline

Every diagram references template colours as `<a:schemeClr val="accent1"/>` (never hex)
and never sets an explicit typeface (fonts inherit from the template). This is not
optional or configurable per-diagram — it's what keeps a generated diagram from drifting
off-template the way `template_map.json`'s `respect_theme_fonts` rule already governs
manually-styled slides. Pass `--theme-colors` (from `template_profile.json`'s
`theme_colors`) to `render_diagram.py` only for a faithful SVG *preview* — it has no
effect on the OOXML output, which always uses scheme references.
