#!/usr/bin/env python3
"""Compare two documents and produce the change brief. The default way to use this skill.

    python compare.py last-week.docx this-week.docx \\
        --previous-period "Week 11" --current-period "Week 12" -o run/

Two files in, a change brief out. Whatever the two documents are — two CM plans this week,
two training trackers next week, two RICEFWA decks the week after — nothing carries over
between runs and nothing needs to have been set up beforehand. The consultant uploads two
files and gets a brief to write the update from.

This runs the three mechanical stages (extract, diff, merge) in one go and writes every
intermediate artifact, so a run is still inspectable and resumable stage by stage. It does
not write the update — that is Stage 4, and it is the model's job.

For several documents a week, or to avoid re-uploading last period's files every time, use
intake.py instead; it pairs whole folders and can keep a snapshot archive. Neither is a
prerequisite for this — a standalone two-file comparison always works on its own.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diff_snapshots import diff, load_rules  # noqa: E402
from extract import EXTRACTORS, extract, slug  # noqa: E402
from write_update import merge, render_md  # noqa: E402


def check(path):
    path = Path(path)
    if not path.is_file():
        raise SystemExit(f"{path} is not a file.")
    if path.suffix.lower() not in EXTRACTORS:
        raise SystemExit(
            f"{path.name}: unsupported type '{path.suffix or '(none)'}'. Supported: "
            + ", ".join(sorted(EXTRACTORS))
            + ".\nResave legacy .doc/.xls/.ppt as Open XML first. PDFs can't be compared "
            "structurally — say so rather than passing a text-only comparison off as one."
        )
    return path


def document_name(previous, current, override):
    """One name for the pair, since the client's two filenames rarely match."""
    if override:
        return slug(override)
    a, b = slug(previous.stem), slug(current.stem)
    if a == b:
        return a
    # Longest shared run of words, so 'CM Plan v4' and 'CM Plan v5 FINAL' -> 'cm-plan'.
    wa, wb = a.split("-"), b.split("-")
    best = []
    for i in range(len(wa)):
        for j in range(len(wb)):
            k = 0
            while i + k < len(wa) and j + k < len(wb) and wa[i + k] == wb[j + k]:
                k += 1
            if k > len(best):
                best = wa[i : i + k]
    return "-".join(best) if best else b


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("previous", help="last period's document")
    ap.add_argument("current", help="this period's document")
    ap.add_argument("--previous-period", default="previous", help="e.g. 'Week 11'")
    ap.add_argument("--current-period", default="current", help="e.g. 'Week 12'")
    ap.add_argument("--name", help="what to call this document (default: derived from the filenames)")
    ap.add_argument("--rules", help="materiality rule overrides; see diff_snapshots.py --print-rules")
    ap.add_argument("-o", "--out", default="run", help="run folder to write into (default: run/)")
    args = ap.parse_args()

    previous, current = check(args.previous), check(args.current)
    name = document_name(previous, current, args.name)
    out = Path(args.out)
    (out / "snapshots").mkdir(parents=True, exist_ok=True)
    (out / "changes").mkdir(parents=True, exist_ok=True)

    if previous.suffix.lower() != current.suffix.lower():
        print(
            f"warning: comparing a {previous.suffix} with a {current.suffix} — check these "
            "are two versions of the same report, not two different documents",
            file=sys.stderr,
        )

    snapshots = {}
    for role, path, period in (
        ("previous", previous, args.previous_period),
        ("current", current, args.current_period),
    ):
        snapshot = extract(path, period, name)
        target = out / "snapshots" / f"{name}-{role}.json"
        target.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        snapshots[role] = snapshot
        print(f"  {role}: {path.name} — {len(snapshot['items'])} items", file=sys.stderr)

    if not snapshots["previous"]["items"] or not snapshots["current"]["items"]:
        raise SystemExit(
            "\nnothing extracted from one of the documents. It may be empty, scanned, or "
            "structured in a way the extractor doesn't read. Say so rather than reporting "
            "an empty comparison as 'no changes'."
        )

    result = diff(snapshots["previous"], snapshots["current"], load_rules(args.rules))
    changes_path = out / "changes" / f"{name}.json"
    changes_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    brief = merge([changes_path])
    (out / "change_brief.json").write_text(
        json.dumps(brief, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out / "change_brief.md").write_text(render_md(brief), encoding="utf-8")

    by = brief["totals"]["by_materiality"]
    print(
        f"\n{brief['totals']['changes']} changes — {by['high']} high, {by['medium']} medium, "
        f"{by['low']} low\n"
        f"  {out}/change_brief.md   <- write the update from this\n"
        f"  {out}/change_brief.json <- what QA checks the update against",
        file=sys.stderr,
    )
    if brief["totals"]["changes"] == 0:
        print(
            "\nNo changes at all. Deliver that as a finding, and check the document was "
            "actually updated — an untouched tracker is itself worth raising.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
