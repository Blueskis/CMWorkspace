#!/usr/bin/env python3
"""Shim — chunking/retrieval moved to lib/deck_index.py so deck-builder can share it.

    python retrieve_chunks.py chunk_index.json --query "approval threshold" --top 6
    python retrieve_chunks.py chunk_index.json --section fsd#4.2.1 --top 6

Kept here, with its original CLI unchanged, so the commands documented in this skill's
SKILL.md keep working. See lib/deck_index.py for the actual implementation.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from deck_index import query_index, tokenize  # noqa: E402,F401


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("index", type=Path)
    ap.add_argument("--query", default="")
    ap.add_argument("--section", default=None)
    ap.add_argument("--classifier", default=None, choices=["procedure", "reference", "narrative", "config", "non-functional"])
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    idx = json.loads(args.index.read_text(encoding="utf-8"))
    results = query_index(idx, args.query, args.section, args.classifier, top=args.top)

    if args.json:
        print(json.dumps([{k: v for k, v in c.items()} for c in results], indent=2))
        return 0
    if not results:
        print("no matching chunks (query terms not found — try --section alone, or a broader query)" if args.query
              else "no chunks match --section/--classifier")
        return 0
    for c in results:
        preview = c["text"][:160].replace("\n", " ")
        print(f"{c['chunk_id']}  ({c['section_path']})")
        print(f"        {preview}...")
        if c["figure_refs"]:
            print(f"        figure refs: {', '.join(c['figure_refs'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
