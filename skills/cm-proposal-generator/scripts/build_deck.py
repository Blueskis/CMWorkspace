#!/usr/bin/env python3
"""Turn a proposal plan into an ordered build manifest against the approved template.

    python build_deck.py proposal_plan.json template_profile.json -o build_manifest.json

STATUS (v0.1): this script does the checking and sequencing, not the XML assembly.

It validates that every layout the plan references actually exists in the approved
template, that every block targets a real placeholder on its layout, and then emits a
step-by-step manifest — which layout to duplicate, which placeholder to fill with what,
in what order. Stage 4 executes that manifest through the `pptx` skill's template
workflow (unzip -> edit ppt/slides/slideN.xml -> rezip).

Automating the XML edit itself is the main v0.2 candidate. It is deliberately not done
here: getting OOXML placeholder-filling right without corrupting the firm's template
needs the pptx skill's own tooling (add_slide.py, clean.py, validate.py) driving it, and
a half-working assembler that silently drops a placeholder is worse than a manifest a
human can follow. Where the manifest can't express a slide, build that slide by hand
through the pptx skill — never degrade the plan to fit the tooling.
"""

import argparse
import json
import sys
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


def build(plan, profile):
    layouts = layout_lookup(profile)
    steps, errors = [], []
    slide_no = 0

    for section in sorted(plan.get("sections", []), key=lambda s: s.get("order", 0)):
        for slide in section.get("slides", []):
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
                fills.append(
                    {
                        "placeholder": target,
                        "kind": block["kind"],
                        "content": "[GAP] " + block.get("gap_note", "") if block.get("gap")
                        else block["content"],
                        "gap": bool(block.get("gap")),
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
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("plan", type=Path)
    ap.add_argument("profile", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("build_manifest.json"))
    args = ap.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    profile = json.loads(args.profile.read_text(encoding="utf-8"))

    steps, errors = build(plan, profile)

    manifest = {
        "run_id": plan.get("run_id"),
        "template": profile.get("template"),
        "slide_count": len(steps),
        "note": "Execute through the pptx skill's template workflow. Do all structural "
                "work (duplicate/delete/reorder) before editing any slide content.",
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
