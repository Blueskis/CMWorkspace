#!/usr/bin/env python3
"""Turn a training plan into an ordered build manifest against the slide template.

    python build_deck.py training_plan.json template_profile.json -o build_manifest.json

STATUS (v0.1): this script does the checking and sequencing, not the XML assembly — the
same division as the proposal generator's build_deck.py, for the same reason. It validates
that every layout the plan references exists in the template and that every block targets a
real placeholder on its layout, then emits a step-by-step manifest: which layout to
duplicate, which placeholder to fill with what, in what order.

For the **.pptx** target, Stage 4 executes that manifest through the `pptx` skill's
template workflow (unzip -> edit ppt/slides/slideN.xml -> rezip). Beyond the proposal
manifest, this one also names, per slide:

  * the **image file** to insert for each `image` block, so a screenshot is placed from the
    original bytes ingest extracted rather than re-encoded on the way;
  * the **rendered diagram** path for each `diagram` block (run render_diagram.py first);
  * the **answer key** for each knowledge check, formatted as speaker-notes text, so the
    questions land on the slide and the answers land in the notes.

Where the manifest cannot express a slide, build that slide by hand through the pptx
skill — never degrade the plan to fit the tooling.

The validation and sequencing live in lib/deckkit/manifest.py, shared with the proposal
generator; this file is the training-side CLI over it.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from deckkit.manifest import build  # noqa: E402


def answer_key(questions):
    """Format a check's answers as the speaker-notes text a trainer reads from."""
    lines = ["ANSWER KEY — do not show on screen", ""]
    for n, q in enumerate(questions, 1):
        if q.get("type") == "true_false":
            answer = "TRUE" if q.get("answer") else "FALSE"
        else:
            options = q.get("options") or []
            idx = q.get("answer_index")
            letter = chr(65 + idx) if isinstance(idx, int) and idx < len(options) else "?"
            answer = f"{letter}. {options[idx]}" if letter != "?" else "(no answer recorded)"
        lines.append(f"{n}. {answer}")
        if q.get("rationale"):
            lines.append(f"   Why: {q['rationale']}")
        if q.get("sources"):
            lines.append(f"   Source: {', '.join(q['sources'])}")
    return "\n".join(lines)


def annotate(steps):
    """Add the media and answer-key instructions the .pptx path needs, per step."""
    for step in steps:
        media, keys = [], []
        for fill in step["fills"]:
            if fill["kind"] == "image" and fill.get("asset_path"):
                media.append({
                    "placeholder": fill["placeholder"],
                    "file": fill["asset_path"],
                    "asset_id": fill.get("asset_id"),
                    "alt": fill.get("alt") or "",
                    "note": "insert the original file — do not re-encode or crop",
                })
            elif fill["kind"] == "diagram":
                rendered = (fill.get("diagram") or {}).get("rendered_path")
                media.append({
                    "placeholder": fill["placeholder"],
                    "file": rendered,
                    "asset_id": None,
                    "alt": (fill.get("diagram") or {}).get("caption", ""),
                    "note": "rendered by render_diagram.py" if rendered
                            else "NOT RENDERED — run render_diagram.py before building",
                })
            elif fill["kind"] == "questions":
                keys.append(answer_key(fill.get("questions") or []))

        if media:
            step["media"] = media
        if keys:
            joined = "\n\n".join(keys)
            step["speaker_notes"] = (
                f"{step['speaker_notes']}\n\n{joined}" if step.get("speaker_notes") else joined
            )
    return steps


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", type=Path)
    ap.add_argument("profile", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("build_manifest.json"))
    args = ap.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    profile = json.loads(args.profile.read_text(encoding="utf-8"))

    steps, errors = build(plan, profile, group_key="modules", group_id_key="module_id")
    annotate(steps)

    unrendered = [
        s["slide_id"] for s in steps
        for m in s.get("media", []) if m["file"] is None
    ]

    manifest = {
        "run_id": plan.get("run_id"),
        "course_title": plan.get("course_title"),
        "template": profile.get("template"),
        "slide_count": len(steps),
        "note": "Execute through the pptx skill's template workflow. Do all structural "
                "work (duplicate/delete/reorder) before editing any slide content. "
                "Insert every 'media' file as a picture, unmodified. Answer keys are "
                "already folded into speaker_notes — they must not appear on a slide.",
        "steps": steps,
        "errors": errors,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    images = sum(1 for s in steps for m in s.get("media", []) if m.get("asset_id"))
    diagrams = sum(1 for s in steps for m in s.get("media", []) if not m.get("asset_id"))
    print(f"{len(steps)} slide(s) sequenced -> {args.out}")
    print(f"  {images} image(s), {diagrams} diagram(s) to place")

    limit = plan.get("slide_budget", {}).get("limit")
    if limit and len(steps) > limit:
        print(f"WARNING: {len(steps)} slides exceeds the session limit of {limit}",
              file=sys.stderr)
    if unrendered:
        print(f"WARNING: diagram(s) not yet rendered on {', '.join(sorted(set(unrendered)))} "
              f"— run render_diagram.py before building the .pptx", file=sys.stderr)
    for err in errors:
        print(f"  ERROR {err}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
