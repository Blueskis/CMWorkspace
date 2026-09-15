#!/usr/bin/env python3
"""Chunk source_map.json sections into retrieval units and index them (Stage 0).

    python index_chunks.py training/<run>/source_map.json -o training/<run>/chunk_index.json

This is the retrieval side of the pipeline, separate from source_map.json's role as the
complete-coverage inventory (see map_source.py's docstring for why those two must stay
separate: retrieval answers questions you thought to ask, and the module plan must not be
driven by top-k). Stage 3 queries this index per slide via retrieve_chunks.py; Stage 2's
module plan comes from source_map.json directly.

Each section's text is split into ~200-word chunks, never crossing a heading (a chunk
never spans two section_ids). Each chunk also records any figure references found in its
text ("Figure 7", "the screen below", "as shown above") so a chunk can be presented to
Stage 3 alongside the assets that travel with it.

Index is a simple inverted index (term -> chunk_ids) plus per-chunk term frequencies,
scored at query time by retrieve_chunks.py using BM25. Literal and explainable — no
embeddings, same reasoning cm-proposal-generator's retrieve.py gives for tag matching: a
ranking a practitioner can't reason about can't be debugged when it pulls the wrong clause.

Stdlib only.
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

CHUNK_WORDS = 200
FIGURE_REF_RE = re.compile(
    r"\bfigure\s+\d+[a-z]?\b|\bthe\s+(?:screen|screenshot|dialog|window|form)\s+below\b|"
    r"\bas\s+shown\s+(?:above|below)\b|\bscreen\s+below\b",
    re.IGNORECASE,
)
WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are", "be",
    "this", "that", "with", "as", "by", "it", "at", "from", "will", "shall", "must",
    "if", "then", "not", "can", "may", "into", "their", "its", "each", "such",
}


def tokenize(text):
    return [w.lower() for w in WORD_RE.findall(text) if w.lower() not in STOPWORDS]


def chunk_section(section):
    words = section["text"].split()
    if not words:
        return []
    chunks = []
    for i in range(0, len(words), CHUNK_WORDS):
        piece_words = words[i:i + CHUNK_WORDS]
        text = " ".join(piece_words)
        figure_refs = sorted(set(m.group(0) for m in FIGURE_REF_RE.finditer(text)))
        chunks.append({
            "chunk_id": f"{section['section_id']}::c{i // CHUNK_WORDS + 1}",
            "section_id": section["section_id"],
            "document_id": section["document_id"],
            "section_path": section["section_path"],
            "classifier": section["classifier"],
            "text": text,
            "figure_refs": figure_refs,
        })
    return chunks


def build_index(chunks):
    df = {}  # term -> doc frequency (chunks containing it)
    postings = {}  # chunk_id -> {term: count}
    for c in chunks:
        terms = tokenize(c["text"] + " " + c["section_path"])
        counts = {}
        for t in terms:
            counts[t] = counts.get(t, 0) + 1
        postings[c["chunk_id"]] = counts
        for t in counts:
            df[t] = df.get(t, 0) + 1
    return df, postings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source_map", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("chunk_index.json"))
    args = ap.parse_args()

    source_map = json.loads(args.source_map.read_text(encoding="utf-8"))
    chunks = []
    for section in source_map["sections"]:
        chunks.extend(chunk_section(section))

    if not chunks:
        sys.exit(f"no chunkable text found in {args.source_map} — did map_source.py run on the real inputs?")

    df, postings = build_index(chunks)
    index = {
        "run_id": source_map["run_id"],
        "source_map_ref": str(args.source_map),
        "chunk_count": len(chunks),
        "doc_count": len(chunks),  # each chunk is a "document" for BM25 purposes
        "avg_chunk_len": sum(len(p) for p in postings.values()) / len(postings) if postings else 0,
        "chunks": chunks,
        "postings": postings,
        "doc_freq": df,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(index, indent=2), encoding="utf-8")

    with_figs = sum(1 for c in chunks if c["figure_refs"])
    print(f"{len(chunks)} chunk(s) from {len(source_map['sections'])} section(s) -> {args.out}")
    print(f"  {with_figs} chunk(s) reference a figure — check they line up with asset_index.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
