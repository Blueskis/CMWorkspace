#!/usr/bin/env python3
"""Profile a training template: what layouts exist and what each one can hold.

    python profile_template.py training-assets/templates/html-training/  -o profile.json
    python profile_template.py training-assets/templates/client.potx     -o profile.json

Two template kinds, one output schema:

  * **.potx/.pptx** — reads ppt/slideLayouts/*.xml for layouts and placeholders.
  * **a directory** — an HTML template; reads layouts.html for <template data-layout>
    blocks and their {{placeholder}} tokens.

Stage 2 needs to know which layouts are available before planning modules — you cannot
plan a screenshot walkthrough onto a template with nowhere to put the picture — and Stage 4
needs each layout's placeholder inventory to fill it. Because both kinds emit the same
profile, build_deck.py validates a training plan identically against either; only the
renderer downstream differs.

Profiling an HTML template is also what keeps its profile honest: the placeholder list is
derived from layouts.html itself, so editing a layout can't silently drift from the profile
a plan is checked against. Re-run this after any layout edit.

Stdlib only. The profiling itself lives in lib/deckkit/template_profile.py, shared with the
proposal generator; this file is the training-side CLI over it.

Pair with the pptx skill's `scripts/thumbnail.py` for the visual side of a client .potx:
this tells you what a layout contains, the thumbnail grid tells you what it looks like.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from deckkit import template_profile  # noqa: E402

# Layouts a training deck cannot do without. A client template missing one of these is
# not unusable, but the planner has to know before it plans a slide with nowhere to go.
EXPECTED = {
    "screenshot-walkthrough": "a screen capture beside numbered steps",
    "knowledge-check": "five questions on one slide",
    "diagram": "a process or state diagram",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("template", type=Path,
                    help=".potx/.pptx file, or an HTML template directory containing layouts.html")
    ap.add_argument("-o", "--out", type=Path, default=Path("template_profile.json"))
    args = ap.parse_args()

    def note_parse_error(part, exc):
        print(f"  could not parse {part}: {exc}", file=sys.stderr)

    try:
        profile = template_profile.profile(args.template, on_parse_error=note_parse_error)
    except ValueError as exc:
        sys.exit(str(exc))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(profile, indent=2), encoding="utf-8")

    if profile["kind"] == "html":
        print(f"Profiled {profile['layout_count']} HTML layouts from {args.template} -> {args.out}")
        for layout in profile["layouts"]:
            required = [p["name"] for p in layout["placeholders"] if p["required"]]
            optional = [p["name"] for p in layout["placeholders"] if not p["required"]]
            print(f"  {layout['part']:<24} required: {', '.join(required) or '—'}")
            if optional:
                print(f"  {'':<24} optional: {', '.join(optional)}")
    else:
        layouts = profile["layouts"]
        print(f"Profiled {len(layouts)} layouts from {args.template.name} -> {args.out}")
        for layout in layouts:
            kinds = ", ".join(sorted({p["type"] for p in layout["placeholders"]})) or "none"
            print(f"  {Path(layout['part']).stem:<16} {layout['name'] or '(unnamed)':<32} "
                  f"{layout['placeholder_count']} ph ({kinds})")
        if profile["example_slide_count"]:
            print(f"\n{profile['example_slide_count']} example slide(s) present — thumbnail "
                  f"them (pptx skill: scripts/thumbnail.py) to see the intended house style.")

    names = {str(layout.get("name", "")).lower() for layout in profile["layouts"]}
    names |= {Path(layout["part"]).stem.lower() for layout in profile["layouts"]}
    missing = [
        f"{key} ({why})" for key, why in EXPECTED.items()
        if key not in names and key.replace("-", " ") not in names
    ]
    if missing:
        print("\nNo obvious layout for:", file=sys.stderr)
        for item in missing:
            print(f"  - {item}", file=sys.stderr)
        print("Map these to the nearest layout the template does have, and say so in the "
              "plan — do not plan a slide onto a layout that cannot hold it.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
