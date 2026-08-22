#!/usr/bin/env python3
"""Stage 1 intake: take what the consultant uploaded and get it into snapshots.

Two periods, both uploaded:

    python intake.py --previous inputs/week-11 --previous-period "Week 11" \\
                     --current  inputs/week-12 --current-period  "Week 12" \\
                     --snapshots run/snapshots --archive .snapshot-archive

This period only, diffing against what a previous run stored:

    python intake.py --current inputs/week-13 --current-period "Week 13" \\
                     --snapshots run/snapshots --archive .snapshot-archive

The archive is the point. Uploading two versions of three documents every week is a chore
the consultant will eventually skip; uploading this week's and diffing against a stored
snapshot is not. Snapshots are small JSON, so a whole engagement's history costs very
little — but they do contain the documents' extracted content, so the archive belongs
wherever the source documents would be allowed to live, and nowhere else.

Pairing is by filename with the client's version noise stripped — 'CM Plan v4.docx' and
'CM Plan v5 FINAL 2026-08-21.docx' pair as `cm-plan`. Nothing is paired silently: the
report says what paired, what is new, and what has gone missing since last period.
"""

import argparse
import difflib
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract import EXTRACTORS, extract, slug  # noqa: E402

# Version noise the client's filenames carry. Stripped before pairing, never before
# display — the consultant needs to see the name they actually uploaded.
NOISE = [
    r"\bv\d+(?:[._]\d+)*\b",
    r"\bversion\s*\d+\b",
    r"\bdraft\b", r"\bfinal\b", r"\bclean\b", r"\bcopy\b", r"\blatest\b",
    r"\bupdated?\b", r"\brev(?:ised|ision)?\s*\d*\b",
    r"\b(?:wk|week)\s*\d+\b", r"\bw\d{1,2}\b",
    r"\b\d{4}[-_ ]\d{2}[-_ ]\d{2}\b", r"\b\d{2}[-_ ]\d{2}[-_ ]\d{4}\b", r"\b\d{6,8}\b",
    r"\bq[1-4]\b", r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b",
    r"\bfor\s+review\b", r"\bsigned\s*off\b", r"\bmaster\b",
    r"\([^)]*\)",
]


def canonical(filename):
    """'CM Plan v5 FINAL 2026-08-21.docx' -> 'cm-plan'."""
    stem = Path(filename).stem.lower()
    for pattern in NOISE:
        stem = re.sub(pattern, " ", stem)
    return slug(stem) or slug(Path(filename).stem)


def documents_in(folder):
    """A folder of uploads, or a single file — comparing two files is always allowed."""
    folder = Path(folder)
    if folder.is_file():
        if folder.suffix.lower() not in EXTRACTORS:
            return {}, [folder]
        return {canonical(folder.name): folder}, []
    if not folder.is_dir():
        raise SystemExit(f"{folder} is neither a file nor a folder.")
    found, skipped = {}, []
    for path in sorted(folder.iterdir()):
        if path.name.startswith(("~$", ".")):
            continue  # Office lock files and dotfiles
        if not path.is_file():
            continue
        if path.suffix.lower() not in EXTRACTORS:
            skipped.append(path)
            continue
        key = canonical(path.name)
        while key in found:
            key += "-2"
        found[key] = path
    return found, skipped


def pair(previous, current, threshold=0.72):
    """Exact canonical match first, then best-effort similarity on what's left."""
    pairs = {k: (previous[k], current[k]) for k in previous if k in current}
    prev_left = {k: v for k, v in previous.items() if k not in pairs}
    curr_left = {k: v for k, v in current.items() if k not in pairs}

    candidates = sorted(
        (
            (difflib.SequenceMatcher(None, pk, ck).ratio(), pk, ck)
            for pk in prev_left
            for ck in curr_left
        ),
        reverse=True,
    )
    fuzzy, used_p, used_c = [], set(), set()
    for score, pk, ck in candidates:
        if score < threshold or pk in used_p or ck in used_c:
            continue
        used_p.add(pk)
        used_c.add(ck)
        pairs[ck] = (prev_left[pk], curr_left[ck])
        fuzzy.append((pk, ck, round(score, 2)))

    missing = {k: v for k, v in prev_left.items() if k not in used_p}
    new = {k: v for k, v in curr_left.items() if k not in used_c}
    return pairs, fuzzy, missing, new


def archived(archive, name):
    path = Path(archive) / f"{name}.json"
    return path if path.is_file() else None


def write_snapshot(path, period, name, out):
    snapshot = extract(path, period, name)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return snapshot


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--current", required=True, help="this period's uploads: a folder, or a single file")
    ap.add_argument("--current-period", required=True, help="e.g. 'Week 12'")
    ap.add_argument("--previous", help="last period's uploads: a folder or a single file; omit to use --archive")
    ap.add_argument("--previous-period", help="e.g. 'Week 11'")
    ap.add_argument("--snapshots", required=True, help="folder to write snapshots into")
    ap.add_argument("--archive", help="folder of stored snapshots to read from and update")
    ap.add_argument("--dry-run", action="store_true", help="report the pairing and stop")
    args = ap.parse_args()

    if not args.previous and not args.archive:
        ap.error("give --previous (both periods uploaded) or --archive (a stored previous run)")
    if args.previous and not args.previous_period:
        ap.error("--previous-period is required with --previous")

    current, skipped_c = documents_in(args.current)
    if not current:
        raise SystemExit(f"no supported documents in {args.current}")


    report, plan = [], []
    if args.previous:
        previous, skipped_p = documents_in(args.previous)
        pairs, fuzzy, missing, new = pair(previous, current)
        # Two single files are the two versions, whatever they are called — the consultant
        # settled that by passing them. Don't let filename dissimilarity override it.
        if not pairs and len(previous) == 1 and len(current) == 1:
            name = next(iter(current))
            pairs = {name: (next(iter(previous.values())), next(iter(current.values())))}
            fuzzy, missing, new = [], {}, {}
            report.append("  (pairing the two files given, despite dissimilar names)")
        skipped_c += skipped_p
        for name, (prev_path, curr_path) in sorted(pairs.items()):
            note = next(
                (f"  (paired by similarity {s} with '{pk}')" for pk, ck, s in fuzzy if ck == name),
                "",
            )
            report.append(f"  PAIR    {name}: {prev_path.name} -> {curr_path.name}{note}")
            plan.append((name, prev_path, curr_path))
        for name, path in sorted(new.items()):
            report.append(f"  NEW     {name}: {path.name} — no previous version, cannot be diffed")
        for name, path in sorted(missing.items()):
            report.append(f"  MISSING {name}: was {path.name} last period, not uploaded this period")
    else:
        new = {}
        for name, curr_path in sorted(current.items()):
            stored = archived(args.archive, name)
            if stored:
                report.append(f"  PAIR    {name}: archived snapshot -> {curr_path.name}")
                plan.append((name, stored, curr_path))
            else:
                new[name] = curr_path
                report.append(
                    f"  NEW     {name}: {curr_path.name} — nothing in the archive under this "
                    "name, so either it is genuinely new or the filename drifted too far to pair"
                )
        # A document the archive knows about that nobody uploaded is the likeliest mistake
        # in upload-only mode. Never let it pass as 'nothing changed there'.
        for stored in sorted(Path(args.archive).glob("*.json")) if Path(args.archive).is_dir() else []:
            if stored.stem not in current:
                report.append(
                    f"  MISSING {stored.stem}: in the archive from a previous run, not uploaded "
                    "this period — ask for it before reporting, don't report it as unchanged"
                )

    for path in skipped_c:
        report.append(f"  SKIP    {path.name} — unsupported type '{path.suffix or '(none)'}'")

    print("\n".join(report) or "  (nothing found)", file=sys.stderr)
    if args.dry_run:
        print("\ndry run — nothing written", file=sys.stderr)
        return
    if not plan:
        raise SystemExit(
            "\nnothing to compare. Every document is new, or the previous period is missing.\n"
            "Report this rather than working around it — a first run has nothing to diff "
            "against and should be delivered as a baseline, not as an update."
        )

    snapshots = Path(args.snapshots)
    snapshots.mkdir(parents=True, exist_ok=True)
    print("", file=sys.stderr)
    for name, prev_source, curr_path in plan:
        curr_out = snapshots / f"{name}-current.json"
        prev_out = snapshots / f"{name}-previous.json"

        if prev_source.suffix.lower() == ".json":
            shutil.copyfile(prev_source, prev_out)
            stored = json.loads(prev_out.read_text(encoding="utf-8"))
            prev_label = stored["document"]["period_label"]
            prev_items = len(stored["items"])
        else:
            snapshot = write_snapshot(prev_source, args.previous_period, name, prev_out)
            prev_label, prev_items = args.previous_period, len(snapshot["items"])

        snapshot = write_snapshot(curr_path, args.current_period, name, curr_out)
        print(
            f"  {name}: {prev_label} ({prev_items} items) -> "
            f"{args.current_period} ({len(snapshot['items'])} items)",
            file=sys.stderr,
        )

        if args.archive:
            store = Path(args.archive)
            store.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(curr_out, store / f"{name}.json")

    if args.archive:
        print(
            f"\narchive updated at {args.archive} — next period, upload only that period's "
            "documents and drop --previous.",
            file=sys.stderr,
        )
    print(
        "\nNext: diff each pair, e.g.\n"
        f"  for n in {' '.join(n for n, _, _ in plan)}; do \\\n"
        f"    python diff_snapshots.py {args.snapshots}/$n-previous.json "
        f"{args.snapshots}/$n-current.json -o changes/$n.json; done",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
