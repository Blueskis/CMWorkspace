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

The validation and sequencing live in lib/deckkit/manifest.py, shared with the
training-material generator; this file is the proposal-side CLI over it.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from deckkit.manifest import build  # noqa: E402  (re-exported for render_html.py)


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
