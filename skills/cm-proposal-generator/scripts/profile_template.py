#!/usr/bin/env python3
"""Profile a proposal template: what layouts exist and what each one can hold.

    python profile_template.py proposal-assets/templates/firm.potx        -o profile.json
    python profile_template.py proposal-assets/templates/html-generic/    -o profile.json

Two template kinds, one output schema:

  * **.potx/.pptx** — reads ppt/slideLayouts/*.xml for layouts and placeholders.
  * **a directory** — an HTML template; reads layouts.html for <template data-layout>
    blocks and their {{placeholder}} tokens.

Stage 2 needs to know which layouts are available before planning slides, and Stage 4
needs each layout's placeholder inventory to fill it. Because both kinds emit the same
profile, build_deck.py validates a proposal plan identically against either — only the
renderer downstream differs.

Profiling an HTML template is also what keeps its profile honest: the placeholder list is
derived from layouts.html itself, so editing a layout can't silently drift from the
profile a plan is checked against.

Stdlib only. The profiling itself lives in lib/deckkit/template_profile.py, shared with
the training-material generator so the two skills cannot drift apart; this file is the
proposal-side CLI over it.

Pair with the pptx skill's `scripts/thumbnail.py` for the visual side of a .potx: this
tells you what a layout contains, the thumbnail grid tells you what it looks like.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from deckkit import template_profile  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
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
            print(f"  {layout['part']:<20} required: {', '.join(required) or '—'}")
            if optional:
                print(f"  {'':<20} optional: {', '.join(optional)}")
        return 0

    layouts = profile["layouts"]
    print(f"Profiled {len(layouts)} layouts from {args.template.name} -> {args.out}")
    for layout in layouts:
        kinds = ", ".join(sorted({p["type"] for p in layout["placeholders"]})) or "none"
        print(f"  {Path(layout['part']).stem:<16} {layout['name'] or '(unnamed)':<32} "
              f"{layout['placeholder_count']} ph ({kinds})")
    if profile["example_slide_count"]:
        print(f"\n{profile['example_slide_count']} example slide(s) present — thumbnail them "
              f"(pptx skill: scripts/thumbnail.py) to see the intended house style.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
