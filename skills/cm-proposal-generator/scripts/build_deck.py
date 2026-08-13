#!/usr/bin/env python3
"""Resolve a proposal plan against a template: validate, retarget, and sequence it.

    python build_deck.py proposal_plan.json template_profile.json -o build_manifest.json
    python build_deck.py plan.json profile.json --map proposal-assets/templates/template_map.json

This is the shared front half of Stage 5. Both renderers (`render_pptx.py`,
`render_html.py`) call `build()` here, so a plan is checked identically whichever target
it is aimed at: every layout it names exists in the template, every block targets a real
placeholder on that layout, and slides come out in a definite order.

Running it standalone emits the manifest — the same sequence as a JSON file, for
inspecting a plan or for driving a slide by hand through the `pptx` skill when the
renderer cannot express it.

## Retargeting a plan onto a different template

A plan names layouts and placeholders in the canonical vocabulary shared by
`templates/html-generic` and `templates/pptx-generic` (`title-slide`, `kicker`, `left`,
`situation`, …). The firm's approved template will use its own names, and a plan should
not have to be rewritten to move onto it. Two mechanisms bridge the gap:

1. **Normalised matching**, always on. `title-slide` matches a layout named
   `Title Slide`, `Two Content` matches `two-content`. Case and separators are ignored.
2. **Explicit aliases** in `template_map.json`, for names that genuinely differ — when
   the firm calls the section divider "Divider" and its body placeholder "Content
   Placeholder 2". See `proposal-assets/templates/template_map.example.json`.

Aliases win over normalised matching, which wins over nothing. What does *not* happen is
a silent near-miss: an unresolvable layout or placeholder is an error naming what the
template actually offers, because a slide quietly built into the wrong placeholder is
worse than a build that stops.
"""

import argparse
import json
import re
import sys
from pathlib import Path

NON_ALNUM = re.compile(r"[^a-z0-9]+")


def norm(value):
    """Fold a layout or placeholder name to its comparison key."""
    return NON_ALNUM.sub("-", str(value).lower()).strip("-")


def load_map(path):
    """Load template_map.json, tolerating its advisory keys (sections, rules, _comment)."""
    if path is None:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        "layout_aliases": {norm(k): v for k, v in (data.get("layout_aliases") or {}).items()},
        "placeholder_aliases": {
            norm(scope): {norm(k): v for k, v in table.items()}
            for scope, table in (data.get("placeholder_aliases") or {}).items()
        },
    }


def layout_lookup(profile):
    """Map every name a layout answers to — part stem, cSld name, and both normalised."""
    table = {}
    for layout in profile.get("layouts", []):
        stem = Path(layout["part"]).stem
        for key in (stem, norm(stem), layout.get("name"), norm(layout.get("name") or "")):
            if key:
                table.setdefault(key, layout)
    return table


def resolve_layout(layouts, ref, mapping):
    alias = mapping.get("layout_aliases", {}).get(norm(ref))
    for candidate in ([alias] if alias else []) + [ref, norm(ref)]:
        if candidate and candidate in layouts:
            return layouts[candidate]
    return None


def placeholder_table(layout):
    """Every key a placeholder answers to -> the placeholder record itself.

    Name first and unshadowed: a layout has one placeholder called `left` but several of
    type `body`, so name matches must never lose to a type match.
    """
    by_type, table = {}, {}
    for ph in layout.get("placeholders", []):
        for key in (ph.get("name"), norm(ph.get("name") or "")):
            if key:
                table.setdefault(key, ph)
        if ph.get("idx") is not None:
            table.setdefault(str(ph["idx"]), ph)
        if ph.get("type"):
            by_type.setdefault(str(ph["type"]), ph)
    for key, ph in by_type.items():
        table.setdefault(key, ph)
    return table


def resolve_placeholder(layout, table, ref, mapping):
    aliases = mapping.get("placeholder_aliases", {})
    scoped = aliases.get(norm(layout.get("name") or ""), {})
    generic = aliases.get("*", {})
    alias = scoped.get(norm(ref)) or generic.get(norm(ref))
    for candidate in ([alias] if alias else []) + [ref, norm(ref)]:
        if candidate and str(candidate) in table:
            return table[str(candidate)]
    return None


def build(plan, profile, mapping=None):
    """Plan + template profile -> (ordered steps, errors). The heart of Stage 5."""
    mapping = mapping or {}
    layouts = layout_lookup(profile)
    steps, errors = [], []
    slide_no = 0

    for section in sorted(plan.get("sections", []), key=lambda s: s.get("order", 0)):
        for slide in section.get("slides", []):
            slide_no += 1
            layout_ref = str(slide["layout"])
            layout = resolve_layout(layouts, layout_ref, mapping)

            if layout is None:
                available = sorted({lay.get("name") or Path(lay["part"]).stem
                                    for lay in profile.get("layouts", [])})
                errors.append(
                    f"{slide['slide_id']}: layout '{layout_ref}' is not in the template. "
                    f"Available: {', '.join(available)}"
                )
                continue

            table = placeholder_table(layout)
            fills = []
            for block in slide.get("blocks", []):
                ref = str(block["placeholder"])
                target = resolve_placeholder(layout, table, ref, mapping)
                if target is None:
                    available = sorted({ph.get("name") or ph.get("type")
                                        for ph in layout.get("placeholders", [])})
                    errors.append(
                        f"{slide['slide_id']}: placeholder '{ref}' not on layout "
                        f"'{layout.get('name') or layout_ref}'. "
                        f"Available: {', '.join(a for a in available if a)}"
                    )
                    continue
                is_gap = bool(block.get("gap"))
                fills.append(
                    {
                        "placeholder": ref,
                        "resolved": target,
                        "kind": block["kind"],
                        # For a gap, content carries the marker so the manifest can be
                        # followed by hand; gap_note is passed through separately for
                        # renderers that present it themselves.
                        "content": "[GAP] " + block.get("gap_note", "") if is_gap
                        else block["content"],
                        "gap": is_gap,
                        "gap_note": block.get("gap_note") if is_gap else None,
                        "sources": block.get("sources", []),
                    }
                )

            steps.append(
                {
                    "position": slide_no,
                    "slide_id": slide["slide_id"],
                    "section_id": section["section_id"],
                    "layout_part": layout["part"],
                    "layout_name": layout.get("name"),
                    "title": slide["title"],
                    "fills": fills,
                    "speaker_notes": slide.get("speaker_notes"),
                }
            )

    return steps, errors


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", type=Path)
    ap.add_argument("profile", type=Path)
    ap.add_argument("--map", type=Path, dest="template_map",
                    help="template_map.json with layout_aliases / placeholder_aliases")
    ap.add_argument("-o", "--out", type=Path, default=Path("build_manifest.json"))
    args = ap.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    mapping = load_map(args.template_map)

    steps, errors = build(plan, profile, mapping)

    manifest = {
        "run_id": plan.get("run_id"),
        "template": profile.get("template"),
        "template_kind": profile.get("kind"),
        "slide_count": len(steps),
        "note": "render_pptx.py and render_html.py consume this sequence directly. "
                "Follow it by hand through the pptx skill only for a slide the "
                "renderer cannot express — never degrade the plan to fit the tooling.",
        "steps": steps,
        "errors": errors,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"{len(steps)} slide(s) sequenced -> {args.out}")
    limit = plan.get("slide_budget", {}).get("limit")
    if limit and len(steps) > limit:
        print(f"WARNING: {len(steps)} slides exceeds the RFP limit of {limit}", file=sys.stderr)
    for err in errors:
        print(f"  ERROR {err}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
