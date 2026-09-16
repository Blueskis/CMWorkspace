#!/usr/bin/env python3
"""Final QA on a built deck.pptx (deck-builder Stage 5).

    python qa_deck.py decks/<run>/deck.pptx --template client.potx \
        --plan-validation decks/<run>/plan_validation.json -o decks/<run>/qa_report.md

Three checks, matching the pptx skill's own required QA plus this skill's own gates:

  * **plan_validation.json must show hard_fail: false.** plan_deck.py already ran the
    fit/variety/provenance/deck-type gates before assembly; this script refuses to call a
    deck QA-clean if its own plan never passed (assembling from a failing plan is possible
    — assemble.mjs doesn't re-check — so this is the backstop).
  * **file validation** — shells out to the pptx skill's `office/validate.py`, always with
    `--original <template>` (a template-derived deck without it can read failures the
    template already had as if this build caused them).
  * **content QA** — shells out to `markitdown` and greps for leftover placeholder text
    (`XXXX`, `lorem`, `[insert`, `TODO`) exactly as the pptx skill's own SKILL.md
    prescribes, since a template's own placeholder runs that a plan failed to replace are
    otherwise invisible in the OOXML validator.

Visual QA (render each slide, look for overflow/overlap/margins) is NOT automated here —
it needs a human or a subagent looking at rendered images, per the pptx skill's own
"stare at the images fresh" instruction. Render with:
    soffice --headless --convert-to pdf deck.pptx
    node lib/deck/cli/rasterise.mjs deck.pdf -o slides/

Stdlib only, except shelling out to the pptx skill's scripts and to `markitdown`.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

PLACEHOLDER_RE = re.compile(r"\bx{3,}\b|lorem|\[insert|\bTODO\b", re.IGNORECASE)

# The pptx skill's install location in this environment — see SKILL.md's "Depends on"
# section for how to locate it if this path has moved.
PPTX_SKILL_CANDIDATES = [
    Path("/root/.claude/skills/pptx"),
]


def find_pptx_skill():
    for c in PPTX_SKILL_CANDIDATES:
        if (c / "scripts" / "office" / "validate.py").is_file():
            return c
    import glob
    matches = glob.glob("/root/.claude/skills/**/pptx/scripts/office/validate.py", recursive=True)
    if matches:
        return Path(matches[0]).parents[2]
    return None


def run_validate(deck_path, template_path):
    skill_dir = find_pptx_skill()
    if skill_dir is None:
        return False, "pptx skill not found on disk — cannot run office/validate.py; install it or pass its path manually"
    cmd = ["python3", str(skill_dir / "scripts" / "office" / "validate.py"), str(deck_path)]
    if template_path:
        cmd += ["--original", str(template_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, (result.stdout + result.stderr).strip()


def run_content_check(deck_path):
    try:
        result = subprocess.run(["markitdown", str(deck_path)], capture_output=True, text=True)
    except FileNotFoundError:
        return None, "markitdown not installed — content QA skipped (pip install markitdown[pptx])"
    text = result.stdout
    hits = PLACEHOLDER_RE.findall(text)
    return (len(hits) == 0), (f"leftover placeholder-looking text found: {hits}" if hits else "clean")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck", type=Path)
    ap.add_argument("--template", type=Path, default=None)
    ap.add_argument("--plan-validation", type=Path, default=None)
    ap.add_argument("-o", "--out", type=Path, default=Path("qa_report.md"))
    args = ap.parse_args()

    lines = [f"# QA report — {args.deck.name}", ""]
    hard_fail = False

    if args.plan_validation:
        import json
        pv = json.loads(args.plan_validation.read_text(encoding="utf-8"))
        if pv.get("hard_fail"):
            hard_fail = True
            lines.append(f"## Plan validation: FAILED ({len(pv.get('failures', []))} failure(s))")
            lines.append("This deck was assembled from a plan that never passed plan_deck.py. "
                          "Fix the plan and rebuild — do not hand this over.")
        else:
            lines.append(f"## Plan validation: passed ({len(pv.get('warnings', []))} warning(s))")
    else:
        lines.append("## Plan validation: not checked (no --plan-validation passed)")
    lines.append("")

    file_ok, file_msg = run_validate(args.deck, args.template)
    if not file_ok:
        hard_fail = True
    lines.append(f"## File validation (pptx skill's office/validate.py): {'PASSED' if file_ok else 'FAILED'}")
    lines.append("```")
    lines.append(file_msg)
    lines.append("```")
    lines.append("")

    content_ok, content_msg = run_content_check(args.deck)
    if content_ok is False:
        hard_fail = True
    lines.append(f"## Content QA (markitdown placeholder-text check): "
                  f"{'PASSED' if content_ok else ('SKIPPED' if content_ok is None else 'FAILED')}")
    lines.append(content_msg)
    lines.append("")

    lines.append("## Visual QA")
    lines.append("Not automated — render and look at every slide before handover:")
    lines.append("```")
    lines.append(f"soffice --headless --convert-to pdf {args.deck}")
    lines.append(f"node lib/deck/cli/rasterise.mjs {args.deck.with_suffix('.pdf')} -o {args.deck.parent}/slides/")
    lines.append("```")
    lines.append("")
    lines.append("**This deck is a first draft for practitioner review, never a client-ready file.**")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"{'FAILED' if hard_fail else 'PASSED'} -> {args.out}")
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
