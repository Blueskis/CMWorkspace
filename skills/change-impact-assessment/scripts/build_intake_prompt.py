#!/usr/bin/env python3
"""Build the in-page scoring rubric embedded in the Change Impact Intake artifact.

The artifact's in-page `sample` capability has no memory of this repo, so the 0-3 scoring
anchors, band cut-offs and response-derivation rules have to travel inside the prompt text
itself. This script is the single source: it concatenates `reference/rating-methodology.md`
and `reference/response-playbook.md` into the block the artifact embeds, so the page's copy
of the rubric can never quietly diverge from the one the rest of the skill uses.

Usage:
    python3 scripts/build_intake_prompt.py > /tmp/rubric_block.txt
    python3 scripts/build_intake_prompt.py --max-chars 60000   # sample's prompt cap is ~64KiB

Re-run this and paste the output into the artifact's `RUBRIC_BLOCK` constant whenever either
source file changes. Do not hand-edit the rubric text inside the artifact directly.
"""
import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REF = HERE.parent / "reference"
SOURCES = ["rating-methodology.md", "response-playbook.md"]

HEADER = """You are scoring one change-impact row for a live intake tool. Score strictly against
the rubric below — do not invent your own scale. If the input doesn't give you enough to score
a dimension with confidence, say so in `notes` and mark `confidence: "Low"` rather than
guessing. This is a first-pass draft for a human to validate, not a finished assessment.

""".lstrip("\n")


def build(max_chars: int | None) -> str:
    parts = [HEADER]
    for name in SOURCES:
        path = REF / name
        if not path.exists():
            print(f"warning: {path} not found, skipping", file=sys.stderr)
            continue
        parts.append(f"\n--- {name} ---\n\n")
        parts.append(path.read_text(encoding="utf-8"))
    text = "".join(parts)
    if max_chars is not None and len(text) > max_chars:
        print(
            f"warning: rubric block is {len(text)} chars, over the {max_chars} cap — "
            "trim the source docs or raise --max-chars if the platform allows it",
            file=sys.stderr,
        )
    return text


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--max-chars",
        type=int,
        default=60000,
        help="Warn (not truncate) if the built block exceeds this many characters "
        "(sample's documented prompt cap is roughly 64KiB; default leaves headroom).",
    )
    args = ap.parse_args()
    sys.stdout.write(build(args.max_chars))


if __name__ == "__main__":
    main()
