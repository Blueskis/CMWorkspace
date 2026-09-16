#!/usr/bin/env python3
"""Shim — chunking/retrieval moved to lib/deck_index.py so deck-builder can share it.

    python index_chunks.py training/<run>/source_map.json -o training/<run>/chunk_index.json

Kept here, with its original CLI unchanged, so the commands documented in this skill's
SKILL.md keep working. See lib/deck_index.py for the actual implementation — it also
now handles vision-derived chunks and query expansion, neither of which this training
path uses, so its output here is unchanged except for one new field: every chunk now
carries `origin: "prose"`.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from deck_index import build, tokenize  # noqa: E402,F401 — tokenize re-exported for retrieve_chunks.py


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source_map", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("chunk_index.json"))
    args = ap.parse_args()

    source_map = json.loads(args.source_map.read_text(encoding="utf-8"))
    index = build(source_map)
    index["source_map_ref"] = str(args.source_map)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(index, indent=2), encoding="utf-8")

    with_figs = sum(1 for c in index["chunks"] if c["figure_refs"])
    print(f"{index['chunk_count']} chunk(s) from {len(source_map['sections'])} section(s) -> {args.out}")
    print(f"  {with_figs} chunk(s) reference a figure — check they line up with asset_index.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
