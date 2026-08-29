#!/usr/bin/env python3
"""Query chunk_index.json for a shortlist of candidate chunks (Stage 3).

    python retrieve_chunks.py chunk_index.json --query "approval threshold" --top 6
    python retrieve_chunks.py chunk_index.json --section fsd#4.2.1 --top 6
    python retrieve_chunks.py chunk_index.json --query "approval" --classifier procedure --json

BM25 over the inverted index index_chunks.py built. A shortlist is not a decision — same
doctrine as cm-proposal-generator's retrieve.py: the model reads the shortlisted chunks
and chooses what actually goes on the slide and what its `sources` are. Ranking is
explainable term overlap, not a black box, so a wrong retrieval can be debugged by reading
the query and the chunk's terms side by side.

`--section` restricts the search to chunks from one section_id (and its sub-sections, by
prefix) — the common case once Stage 2 has already decided a slide teaches a specific
procedure and Stage 3 just needs the right passages from it.

Stdlib only.
"""

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from index_chunks import tokenize  # noqa: E402

K1, B = 1.5, 0.75


def bm25_score(query_terms, chunk_id, postings, df, doc_count, avg_len):
    counts = postings.get(chunk_id, {})
    doc_len = sum(counts.values()) or 1
    score = 0.0
    for t in query_terms:
        f = counts.get(t, 0)
        if f == 0:
            continue
        n_t = df.get(t, 0)
        idf = math.log((doc_count - n_t + 0.5) / (n_t + 0.5) + 1)
        score += idf * (f * (K1 + 1)) / (f + K1 * (1 - B + B * doc_len / avg_len))
    return score


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("index", type=Path)
    ap.add_argument("--query", default="", help="Free-text query, BM25-scored")
    ap.add_argument("--section", default=None, help="Restrict to this section_id (prefix match includes sub-sections)")
    ap.add_argument("--classifier", default=None, choices=["procedure", "reference", "narrative", "config", "non-functional"])
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--json", action="store_true", help="Machine-readable output")
    args = ap.parse_args()

    idx = json.loads(args.index.read_text(encoding="utf-8"))
    chunks = {c["chunk_id"]: c for c in idx["chunks"]}
    candidates = list(chunks.values())

    if args.section:
        candidates = [c for c in candidates if c["section_id"] == args.section or c["section_id"].startswith(args.section + ".")]
    if args.classifier:
        candidates = [c for c in candidates if c["classifier"] == args.classifier]
    if not candidates:
        print("[]" if args.json else "no chunks match --section/--classifier", file=sys.stderr)
        return 0 if args.json else 1

    if args.query:
        query_terms = tokenize(args.query)
        scored = [
            (bm25_score(query_terms, c["chunk_id"], idx["postings"], idx["doc_freq"], idx["doc_count"], idx["avg_chunk_len"]), c)
            for c in candidates
        ]
        scored = [(s, c) for s, c in scored if s > 0]
        scored.sort(key=lambda pair: pair[0], reverse=True)
    else:
        scored = [(0.0, c) for c in candidates]

    results = scored[: args.top]

    if args.json:
        print(json.dumps([{"score": round(s, 3), **c} for s, c in results], indent=2))
        return 0

    if not results:
        print("no matching chunks (query terms not found — try --section alone, or a broader query)")
        return 0

    for score, c in results:
        preview = c["text"][:160].replace("\n", " ")
        print(f"[{score:.2f}] {c['chunk_id']}  ({c['section_path']})")
        print(f"        {preview}...")
        if c["figure_refs"]:
            print(f"        figure refs: {', '.join(c['figure_refs'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
