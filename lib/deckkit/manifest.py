"""Validate a slide plan against a template profile and sequence it into a build manifest.

This is the join between a plan and a template. It checks that every layout the plan
references actually exists in the template, that every block targets a real placeholder on
its layout, and then emits a step-by-step manifest — which layout to duplicate, which
placeholder to fill with what, in what order.

Both render targets consume the manifest: the HTML renderer walks it directly, and the
.pptx path executes it through the pptx skill's template workflow (unzip -> edit
ppt/slides/slideN.xml -> rezip). That is why the check lives here rather than in either
renderer — a plan is validated identically whichever way it is going to be built.

Errors are collected, not raised. A plan with three bad placeholders should report all
three, not stop at the first.
"""

from pathlib import Path


def layout_lookup(profile):
    """Map both layout part-stem (slideLayout3) and human name to the layout record."""
    table = {}
    for layout in profile.get("layouts", []):
        table[Path(layout["part"]).stem] = layout
        if layout.get("name"):
            table[layout["name"]] = layout
    return table


def placeholder_keys(layout):
    keys = set()
    for ph in layout.get("placeholders", []):
        for value in (ph.get("name"), ph.get("idx"), ph.get("type")):
            if value is not None:
                keys.add(str(value))
    return keys


def build(plan, profile, group_key="sections", group_id_key="section_id"):
    """Sequence a plan's slides into manifest steps. Returns (steps, errors).

    `group_key`/`group_id_key` name the plan's grouping level — "sections" for a proposal,
    "modules" for a training deck. The slide and block contract is identical either way,
    which is the point: one sequencer, two document types.
    """
    layouts = layout_lookup(profile)
    steps, errors = [], []
    slide_no = 0

    for group in sorted(plan.get(group_key, []), key=lambda s: s.get("order", 0)):
        for slide in group.get("slides", []):
            slide_no += 1
            layout_ref = str(slide["layout"])
            layout = layouts.get(layout_ref)

            if layout is None:
                errors.append(
                    f"{slide['slide_id']}: layout '{layout_ref}' is not in the approved "
                    f"template. Available: {', '.join(sorted(layouts))}"
                )
                continue

            keys = placeholder_keys(layout)
            fills = []
            for block in slide.get("blocks", []):
                target = str(block["placeholder"])
                if target not in keys:
                    errors.append(
                        f"{slide['slide_id']}: placeholder '{target}' not on layout "
                        f"'{layout_ref}'. Available: {', '.join(sorted(keys))}"
                    )
                    continue
                is_gap = bool(block.get("gap"))
                fill = {
                    "placeholder": target,
                    "kind": block["kind"],
                    # For a gap, content carries the marker so the pptx path can be
                    # followed by hand from the manifest alone; gap_note is passed
                    # through separately for renderers that present it themselves.
                    "content": "[GAP] " + block.get("gap_note", "") if is_gap
                    else block["content"],
                    "gap": is_gap,
                    "gap_note": block.get("gap_note") if is_gap else None,
                    "sources": block.get("sources", []),
                }
                # Carried through untouched for the renderers that need them; absent on a
                # proposal plan, so the manifest shape is unchanged for that skill.
                for extra in ("asset_id", "asset_path", "alt", "diagram", "questions"):
                    if extra in block:
                        fill[extra] = block[extra]
                fills.append(fill)

            step = {
                "position": slide_no,
                "slide_id": slide["slide_id"],
                group_id_key: group[group_id_key],
                "layout_part": layout["part"],
                "layout_name": layout.get("name"),
                "title": slide["title"],
                "fills": fills,
                "speaker_notes": slide.get("speaker_notes"),
            }
            if "objective_ids" in slide:
                step["objective_ids"] = slide["objective_ids"]
            if "audiences" in slide:
                step["audiences"] = slide["audiences"]
            steps.append(step)

    return steps, errors
