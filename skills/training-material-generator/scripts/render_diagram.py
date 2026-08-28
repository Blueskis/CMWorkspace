#!/usr/bin/env python3
"""Rasterise a plan's Mermaid diagrams — needed only for the .pptx render target.

    python render_diagram.py training_plan.json -o diagrams/            # render all
    python render_diagram.py training_plan.json --check                 # validate only
    python render_diagram.py training_plan.json -o diagrams/ --write-back

The HTML target does not need this: it ships mermaid.js in the template's vendor/ and
renders diagrams in the browser. PowerPoint has no such option, so a diagram going into a
.pptx has to become an image first, via `npx @mermaid-js/mermaid-cli`.

Two things this deliberately will not do:

  * **It will not silently skip a diagram it cannot render.** A deck with a figure missing
    is worse than a build that stopped and said which one and why, so an unrenderable
    diagram is an error with the Mermaid source written out beside it for a person to
    render by hand.
  * **It will not invent a fallback picture.** There is no ASCII-art or empty-box
    substitute — the diagram is either the one the plan describes or it is absent and
    reported.

`--check` runs the structural validation alone and needs no network, which is what CI and
a quick pre-flight want.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MERMAID_HEADS = (
    "graph", "flowchart", "sequenceDiagram", "stateDiagram", "stateDiagram-v2",
    "classDiagram", "erDiagram", "journey", "gantt", "pie", "mindmap", "timeline",
    "quadrantChart", "block-beta",
)
# The patterns the skill's reference/diagram-patterns.md defines, and the Mermaid
# diagram types each is allowed to use. Keeping this narrow is the point: a training
# deck wants five legible shapes, not every chart Mermaid can draw.
PATTERN_HEADS = {
    "process-flow": ("graph", "flowchart"),
    "decision-tree": ("graph", "flowchart"),
    "swimlane": ("graph", "flowchart", "sequenceDiagram"),
    "landscape": ("graph", "flowchart"),
    "state-transition": ("stateDiagram", "stateDiagram-v2"),
}


def iter_diagrams(plan):
    """(module_id, slide_id, block_index, block) for every diagram block in the plan."""
    for module in plan.get("modules", []):
        for slide in module.get("slides", []):
            for i, block in enumerate(slide.get("blocks", [])):
                if block.get("kind") == "diagram":
                    yield module["module_id"], slide["slide_id"], i, block


def validate(block, where):
    """Structural checks that do not need Mermaid installed."""
    problems = []
    spec = block.get("diagram") or {}
    source = (spec.get("mermaid") or "").strip()
    pattern = spec.get("pattern")

    if not source:
        problems.append(f"{where}: diagram block has no mermaid source")
        return problems

    head = source.split("\n", 1)[0].strip().split()[0].rstrip(";")
    if not any(head.startswith(h) for h in MERMAID_HEADS):
        problems.append(
            f"{where}: '{head}' is not a Mermaid diagram type "
            f"(expected one of {', '.join(MERMAID_HEADS[:6])}, …)"
        )
    elif pattern in PATTERN_HEADS and not any(
        head.startswith(h) for h in PATTERN_HEADS[pattern]
    ):
        problems.append(
            f"{where}: pattern '{pattern}' expects {' or '.join(PATTERN_HEADS[pattern])}, "
            f"but the source starts with '{head}'"
        )

    if not block.get("sources") and not block.get("gap"):
        problems.append(
            f"{where}: diagram has no sources. A diagram is an interpretation of the "
            f"document; an interpretation without a citation cannot be checked."
        )
    if len(source.splitlines()) > 40:
        problems.append(
            f"{where}: {len(source.splitlines())} lines — too dense to read at slide size; "
            f"split it across two slides"
        )
    return problems


# mermaid-cli drives a headless browser through puppeteer, which by default wants its own
# downloaded Chromium. Plenty of environments already have one and cannot fetch another, so
# look for it rather than failing on a browser that is sitting right there.
MERMAID_THEME = {
    "theme": "base",
    "themeVariables": {
        "fontFamily": '"Segoe UI", Roboto, Arial, sans-serif',
        "fontSize": "15px",
        "primaryColor": "#e3f3f0",
        "primaryBorderColor": "#0f7b6c",
        "primaryTextColor": "#14213d",
        "lineColor": "#43506b",
        "secondaryColor": "#f5f7fa",
        "tertiaryColor": "#ffffff",
    },
}

CHROMIUM_CANDIDATES = (
    "/opt/pw-browsers/chromium",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)


def find_chromium():
    """An existing Chromium/Chrome for puppeteer, or None to let it use its own."""
    if os.environ.get("PUPPETEER_EXECUTABLE_PATH"):
        return os.environ["PUPPETEER_EXECUTABLE_PATH"]
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        found = shutil.which(name)
        if found:
            return found
    for path in CHROMIUM_CANDIDATES:
        if Path(path).exists():
            return path
    return None


def render_one(source, out_path, background="white", scale=2):
    """Render via mermaid-cli. Returns None on success, or the failure text."""
    if shutil.which("npx") is None:
        return "npx is not on PATH, so mermaid-cli cannot be invoked"

    env = dict(os.environ)
    browser = find_chromium()
    if browser:
        env["PUPPETEER_EXECUTABLE_PATH"] = browser

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "diagram.mmd"
        src.write_text(source, encoding="utf-8")
        # --no-sandbox is required wherever this runs as root, which containers usually do.
        puppeteer_config = Path(tmp) / "puppeteer.json"
        puppeteer_config.write_text('{"args": ["--no-sandbox", "--disable-setuid-sandbox"]}',
                                    encoding="utf-8")
        # The same mermaid theme the HTML renderer uses, so a diagram looks the same
        # whichever target it is built for. Kept in one place here and mirrored in
        # render_html.py's MERMAID_BOOT.
        mermaid_config = Path(tmp) / "mermaid.json"
        mermaid_config.write_text(json.dumps(MERMAID_THEME), encoding="utf-8")
        cmd = [
            "npx", "-y", "@mermaid-js/mermaid-cli", "-i", str(src),
            "-o", str(out_path), "-b", background, "-s", str(scale),
            "-p", str(puppeteer_config), "-c", str(mermaid_config),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
        except subprocess.TimeoutExpired:
            return "mermaid-cli timed out after 300s (the first run downloads the package)"
        except OSError as exc:
            return f"could not run mermaid-cli: {exc}"

    if proc.returncode != 0 or not out_path.exists():
        detail = (proc.stderr or proc.stdout or "mermaid-cli failed").strip()[:500]
        if "Could not find Chrome" in detail or "Browser was not found" in detail:
            detail += ("\n    No usable browser. Set PUPPETEER_EXECUTABLE_PATH to a Chrome "
                       "or Chromium binary, or render this diagram by hand.")
        return detail
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", type=Path)
    ap.add_argument("-o", "--out", type=Path, help="Directory for the rendered images")
    ap.add_argument("--format", choices=["png", "svg"], default="png",
                    help="PowerPoint 2016+ takes SVG, but PNG is the safe default")
    ap.add_argument("--scale", type=int, default=2, help="Raster scale factor (png only)")
    ap.add_argument("--check", action="store_true",
                    help="Validate the diagram blocks and stop — no rendering, no network")
    ap.add_argument("--write-back", action="store_true",
                    help="Record each rendered_path back into the plan file")
    args = ap.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    diagrams = list(iter_diagrams(plan))
    if not diagrams:
        print("No diagram blocks in this plan.")
        return 0

    problems = []
    for module_id, slide_id, i, block in diagrams:
        problems.extend(validate(block, f"{module_id}/{slide_id} block {i}"))

    if problems:
        for problem in problems:
            print(f"  ERROR {problem}", file=sys.stderr)
        print(f"{len(problems)} diagram problem(s) — fix the plan", file=sys.stderr)
        return 1

    print(f"{len(diagrams)} diagram block(s) validated.")
    if args.check:
        return 0
    if not args.out:
        sys.exit("give -o/--out to render, or --check to validate only")

    args.out.mkdir(parents=True, exist_ok=True)
    failures = []
    for module_id, slide_id, i, block in diagrams:
        source = block["diagram"]["mermaid"]
        out_path = args.out / f"{slide_id}-{i}.{args.format}"
        error = render_one(source, out_path, scale=args.scale)
        if error:
            fallback = out_path.with_suffix(".mmd")
            fallback.write_text(source, encoding="utf-8")
            failures.append((f"{module_id}/{slide_id}", error, fallback))
            continue
        block["diagram"]["rendered_path"] = str(out_path)
        print(f"  {slide_id} -> {out_path}")

    if failures:
        print(f"\n{len(failures)} diagram(s) did not render:", file=sys.stderr)
        for where, error, fallback in failures:
            print(f"  {where}: {error}", file=sys.stderr)
            print(f"    source written to {fallback} — render it by hand and set "
                  f"diagram.rendered_path, or build that slide's figure through the "
                  f"pptx skill", file=sys.stderr)
        print("Not building a deck with a figure missing.", file=sys.stderr)
        return 1

    if args.write_back:
        args.plan.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        print(f"rendered_path recorded in {args.plan}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
