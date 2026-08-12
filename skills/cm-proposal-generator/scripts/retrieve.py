#!/usr/bin/env python3
"""Query the knowledge-bank index for entries matching a section and tags.

    python retrieve.py kb_index.json --section methodology --tags workday,financial-services
    python retrieve.py kb_index.json --section case-studies --tags erp --top 3 --json

v0.1 scoring is deliberately simple and explainable — literal tag overlap, weighted by
section match and freshness. It is a shortlist generator, not a decision: the model reads
the shortlisted entries and chooses what actually fits the slide.

Ranking:
    +3  per matching tag
    +2  section matches the requested section
    -2  entry is stale (last_reviewed older than 24 months)
    -3  entry is superseded by a newer one

internal-only entries are excluded unless --include-internal is passed, since they must
not reach client-facing material.
"""

import argparse
import json
import sys
from pathlib import Path


def score(entry, section, tags):
    matched = sorted(set(entry["tags"]) & tags)
    points = 3 * len(matched)
    reasons = [f"tag:{t}" for t in matched]

    if section and entry["section"] == section:
        points += 2
        reasons.append(f"section:{section}")
    if entry.get("stale"):
        points -= 2
        reasons.append("stale")
    if entry.get("superseded"):
        points -= 3
        reasons.append("superseded")

    return points, reasons


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("index", type=Path)
    ap.add_argument("--section", help="Restrict to (and boost) this knowledge-bank section")
    ap.add_argument("--tags", default="", help="Comma-separated tags")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--include-internal", action="store_true",
                    help="Include internal-only entries — NOT for client-facing content")
    ap.add_argument("--strict-section", action="store_true",
                    help="Return only entries in --section rather than boosting them")
    ap.add_argument("--json", action="store_true", help="Machine-readable output")
    args = ap.parse_args()

    index = json.loads(args.index.read_text(encoding="utf-8"))
    tags = {t.strip().lower() for t in args.tags.split(",") if t.strip()}

    candidates = []
    for entry in index["entries"]:
        if entry.get("clearance") == "internal-only" and not args.include_internal:
            continue
        if args.strict_section and args.section and entry["section"] != args.section:
            continue
        points, reasons = score(entry, args.section, tags)
        if points <= 0:
            continue
        candidates.append({**entry, "score": points, "why": reasons})

    candidates.sort(key=lambda e: (-e["score"], e["id"]))
    results = candidates[: args.top]

    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    if not results:
        print(f"No matches for section={args.section!r} tags={sorted(tags)}.")
        print("This is a [GAP] — record it in the plan; do not substitute generated content.")
        return 0

    for entry in results:
        flags = []
        if entry.get("stale"):
            flags.append("STALE")
        if entry.get("clearance") == "anonymised":
            flags.append("ANONYMISED — do not name the client")
        if not entry.get("metrics_verified"):
            flags.append("metrics unverified")
        suffix = f"  [{'; '.join(flags)}]" if flags else ""
        print(f"{entry['score']:>3}  {entry['id']}  ({entry['section']}){suffix}")
        print(f"     {entry['title']}")
        print(f"     {entry['path']}  ·  matched: {', '.join(entry['why'])}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
