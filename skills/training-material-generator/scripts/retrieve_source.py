#!/usr/bin/env python3
"""Query the source index for the chunks a slide should be written from.

    python retrieve_source.py source_index.json --heading "Purchase Order Approval"
    python retrieve_source.py source_index.json --keywords approval,threshold --top 5 --json
    python retrieve_source.py source_index.json --anchor POFSD#5.1 --full

Scoring is literal and explainable, the same philosophy as the proposal generator's
retrieve.py: this produces a **shortlist, not a decision**. The model reads the shortlisted
chunks and writes the slide from them.

Ranking:
    +4  per keyword found in the chunk's heading path
    +2  per keyword found in the chunk's body text
    +3  the requested heading matches somewhere in the chunk's heading path
    +2  chunk carries a table          (field rules and thresholds live in tables)
    +2  chunk carries a placement-class image  (the screenshot for this step)
    -3  chunk's topic is out of scope  (document furniture)

There is no embedding search and no synonym expansion in v0.1. That is a real limit: ask
for "approval" and a chunk that only ever says "authorisation" will not surface. Read the
neighbouring chunks by anchor when a search comes back thin — `--context` does exactly
that — rather than concluding the document is silent and writing a [GAP].
"""

import argparse
import json
import re
import sys
from pathlib import Path

PLACEMENT_KINDS = ("screenshot", "diagram", "chart")


def score(chunk, keywords, heading, out_of_scope, placement_assets):
    points, reasons = 0, []
    path_text = " ".join(chunk["heading_path"]).lower()
    body = chunk["text"].lower()

    for keyword in keywords:
        if keyword in path_text:
            points += 4
            reasons.append(f"heading:{keyword}")
        elif keyword in body:
            points += 2
            reasons.append(f"text:{keyword}")

    if heading and heading.lower() in path_text:
        points += 3
        reasons.append("heading-match")
    if chunk["tables"]:
        points += 2
        reasons.append(f"{len(chunk['tables'])} table(s)")
    if any(a in placement_assets for a in chunk["asset_ids"]):
        points += 2
        reasons.append("has an image")
    if chunk["anchor"] in out_of_scope:
        points -= 3
        reasons.append("out-of-scope topic")

    return points, reasons


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("index", type=Path)
    ap.add_argument("--heading", help="Heading text to match against the heading path")
    ap.add_argument("--keywords", default="", help="Comma-separated terms")
    ap.add_argument("--anchor", help="Fetch one chunk by exact anchor, ignoring scoring")
    ap.add_argument("--context", type=int, default=0, metavar="N",
                    help="With --anchor, also show the N chunks either side in document order")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--full", action="store_true", help="Print whole chunks, not excerpts")
    ap.add_argument("--json", action="store_true", help="Machine-readable output")
    args = ap.parse_args()

    index = json.loads(args.index.read_text(encoding="utf-8"))
    chunks = index["chunks"]
    out_of_scope = {t["anchor"] for t in index["topics"] if not t["in_scope"]}
    placement_assets = {
        a["asset_id"] for a in index["assets"] if a["asset_kind"] in PLACEMENT_KINDS
    }

    if args.anchor:
        positions = [i for i, c in enumerate(chunks) if c["anchor"] == args.anchor]
        if not positions:
            sys.exit(f"no chunk with anchor {args.anchor!r} — "
                     f"anchors look like {chunks[0]['anchor']!r}")
        i = positions[0]
        lo, hi = max(0, i - args.context), min(len(chunks), i + args.context + 1)
        results = [{**c, "score": 0, "why": ["by anchor"]} for c in chunks[lo:hi]]
    else:
        keywords = [k.strip().lower() for k in args.keywords.split(",") if k.strip()]
        if not keywords and not args.heading:
            sys.exit("give --heading, --keywords or --anchor")
        candidates = []
        for chunk in chunks:
            points, reasons = score(chunk, keywords, args.heading, out_of_scope,
                                    placement_assets)
            if points > 0:
                candidates.append({**chunk, "score": points, "why": reasons})
        candidates.sort(key=lambda c: (-c["score"], c["ordinal"]))
        results = candidates[: args.top]

    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    if not results:
        print("No matching chunks.")
        print("Before recording a [GAP]: the index is searched literally, so try the "
              "document's own vocabulary, or read around a nearby anchor with "
              "--anchor <a> --context 2. A [GAP] should mean the spec is silent, not "
              "that the search term was ours rather than theirs.")
        return 0

    for chunk in results:
        assets = [a for a in chunk["asset_ids"] if a in placement_assets]
        print(f"{chunk['score']:>3}  {chunk['anchor']}")
        print(f"     {' > '.join(chunk['heading_path']) or '(preamble)'}")
        text = chunk["text"] if args.full else " ".join(chunk["text"].split())[:400]
        for line in text.splitlines() or [""]:
            print(f"     {line}")
        for table in chunk["tables"]:
            print(f"     [table {table['table_id']}] {' | '.join(table['header'])}"
                  f"  ({len(table['rows'])} rows)")
            if args.full:
                for row in table["rows"]:
                    print(f"       {' | '.join(row)}")
        if assets:
            print(f"     [images] {', '.join(assets)}")
        print(f"     matched: {', '.join(chunk['why'])}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
