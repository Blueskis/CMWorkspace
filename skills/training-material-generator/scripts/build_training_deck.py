#!/usr/bin/env python3
"""Turn a deck plan into an ordered build manifest against the approved template (Stage 4).

    python build_training_deck.py deck_plan.json template_profile.json asset_index.json \\
        -o build_manifest.json --diagrams-dir training/<run>/diagrams

STATUS: this script does the checking and sequencing, not the XML assembly — same
division of labour as cm-proposal-generator's build_deck.py, and for the same reason: a
half-working assembler that silently drops a placeholder is worse than a manifest a human
(or inject_slide_xml.py, block by block) can follow. It validates that:

  * every layout the plan references exists in the approved template, and every block's
    placeholder exists on that layout;
  * every block has provenance — a non-empty `sources` array, or `gap: true` with a
    `gap_note`;
  * every `image` block's `asset_id` is in asset_index.json, and if the asset carries a
    `low_res` quality flag the block has explicitly set `ack_low_res: true` — an
    unacknowledged low-res placement is a hard error here, not just a Stage 5 warning;
  * every `diagram` block's `diagram_spec` actually renders — this script calls
    render_diagram.py's `render()` in-process against the target placeholder's geometry
    and reports a spec error or label-overflow by slide, rather than discovering it
    later at pptx-build time.

Placeholder geometry drives both the image aspect-fit and the diagram bounding box. Where
a layout's placeholder has no recorded geometry (an HTML template, or a .potx placeholder
python couldn't read an <a:xfrm> for), a default content-area box is used and the manifest
carries a warning — never a hard error, since the pptx skill's own template inspection can
usually resolve it by eye where this script can't.

Execute the resulting manifest through the **pptx skill's template workflow**: duplicate
layouts (`add_slide.py`), do all structural work first, then run `inject_slide_xml.py`
per image/diagram block and set text placeholders directly in the slide XML, then
`clean.py` and `validate.py --original <template>`.

Stdlib only, except that it imports render_diagram.py (also stdlib-only) from this same
directory to validate diagrams eagerly.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_diagram import DiagramOverflowError, DiagramSpecError, render  # noqa: E402

DEFAULT_BBOX = (1.0, 1.5, 8.0, 5.0)  # fallback content area, inches, for a placeholder with no geometry
ASPECT_TOLERANCE = 0.35  # relative aspect mismatch beyond this gets a manifest warning (heavy letterboxing)


def layout_lookup(profile):
    table = {}
    for layout in profile.get("layouts", []):
        table[Path(layout["part"]).stem] = layout
        if layout.get("name"):
            table[layout["name"]] = layout
    return table


def placeholder_lookup(layout):
    """Map every placeholder key (name/idx/type) a block might target to its record."""
    table = {}
    for ph in layout.get("placeholders", []):
        for value in (ph.get("name"), ph.get("idx"), ph.get("type")):
            if value is not None:
                table[str(value)] = ph
    return table


def geometry_bbox(placeholder):
    geo = (placeholder or {}).get("geometry")
    if not geo:
        return None
    return (geo["x_in"], geo["y_in"], geo["w_in"], geo["h_in"])


def build(plan, profile, asset_index):
    layouts = layout_lookup(profile)
    assets = {a["asset_id"]: a for a in asset_index.get("assets", [])}

    steps, errors, warnings = [], [], []
    slide_no = 0

    for module in sorted(plan.get("modules", []), key=lambda m: m.get("order", 0)):
        for slide in module.get("slides", []):
            slide_no += 1
            slide_id = slide["slide_id"]
            layout_ref = str(slide["layout"])
            layout = layouts.get(layout_ref)

            if layout is None:
                errors.append(
                    f"{slide_id}: layout '{layout_ref}' is not in the approved template. "
                    f"Available: {', '.join(sorted(layouts))}"
                )
                continue

            ph_table = placeholder_lookup(layout)
            fills = []

            for i, block in enumerate(slide.get("blocks", [])):
                where = f"{slide_id} block {i} ({block.get('kind')})"
                target = str(block["placeholder"])
                placeholder = ph_table.get(target)
                if placeholder is None:
                    errors.append(
                        f"{where}: placeholder '{target}' not on layout '{layout_ref}'. "
                        f"Available: {', '.join(sorted(ph_table))}"
                    )
                    continue

                is_gap = bool(block.get("gap"))
                if is_gap and not block.get("gap_note"):
                    errors.append(f"{where}: gap is true but gap_note is missing")
                if not is_gap and not block.get("sources"):
                    errors.append(f"{where}: no sources and gap is not true — no third state allowed")

                bbox = geometry_bbox(placeholder) or DEFAULT_BBOX
                if geometry_bbox(placeholder) is None:
                    warnings.append(f"{where}: placeholder '{target}' has no recorded geometry — "
                                     f"using a default content box; verify by eye at QA")

                fill = {
                    "placeholder": target,
                    "kind": block["kind"],
                    "gap": is_gap,
                    "gap_note": block.get("gap_note") if is_gap else None,
                    "sources": block.get("sources", []),
                }

                if block["kind"] == "image" and not is_gap:
                    content = block.get("content", {})
                    asset_id = content.get("asset_id")
                    asset = assets.get(asset_id)
                    if asset is None:
                        errors.append(f"{where}: asset_id '{asset_id}' not in asset_index.json")
                    else:
                        if "low_res" in asset.get("quality", []) and not content.get("ack_low_res"):
                            errors.append(
                                f"{where}: asset '{asset_id}' is low_res and content.ack_low_res "
                                f"is not true — acknowledge it explicitly or choose another asset"
                            )
                        asset_aspect = asset.get("aspect")
                        if asset_aspect:
                            box_aspect = bbox[2] / bbox[3]
                            rel_diff = abs(asset_aspect - box_aspect) / box_aspect
                            if rel_diff > ASPECT_TOLERANCE:
                                warnings.append(
                                    f"{where}: asset '{asset_id}' aspect {asset_aspect:.2f} vs "
                                    f"placeholder aspect {box_aspect:.2f} — expect visible letterboxing"
                                )
                    fill["content"] = content
                    fill["bbox"] = bbox

                elif block["kind"] == "diagram" and not is_gap:
                    content = block.get("content", {})
                    diagram_type = content.get("diagram_type")
                    spec = content.get("spec")
                    try:
                        render(diagram_type, spec, bbox)
                    except (DiagramSpecError, DiagramOverflowError) as exc:
                        errors.append(f"{where}: diagram render failed — {exc}")
                    fill["content"] = content
                    fill["bbox"] = bbox

                else:
                    fill["content"] = (
                        "[GAP] " + block.get("gap_note", "") if is_gap else block.get("content")
                    )

                fills.append(fill)

            steps.append({
                "position": slide_no,
                "slide_id": slide_id,
                "module_id": module["module_id"],
                "layout_part": layout["part"],
                "layout_name": layout.get("name"),
                "title": slide["title"],
                "audiences": slide.get("audiences", []),
                "fills": fills,
                "speaker_notes": slide.get("speaker_notes"),
            })

    return steps, errors, warnings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", type=Path)
    ap.add_argument("profile", type=Path)
    ap.add_argument("assets", type=Path, help="asset_index.json")
    ap.add_argument("-o", "--out", type=Path, default=Path("build_manifest.json"))
    args = ap.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    asset_index = json.loads(args.assets.read_text(encoding="utf-8"))

    steps, errors, warnings = build(plan, profile, asset_index)

    manifest = {
        "run_id": plan.get("run_id"),
        "template": profile.get("template"),
        "slide_count": len(steps),
        "note": "Execute through the pptx skill's template workflow: add_slide.py for "
                "structural duplication first, then inject_slide_xml.py per image/diagram "
                "block, then clean.py and validate.py --original <template>.",
        "steps": steps,
        "errors": errors,
        "warnings": warnings,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"{len(steps)} slide(s) sequenced -> {args.out}")
    for w in warnings:
        print(f"  WARNING {w}", file=sys.stderr)
    for err in errors:
        print(f"  ERROR {err}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
