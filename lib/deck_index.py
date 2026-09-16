#!/usr/bin/env python3
"""Chunk a source_map.json and answer BM25 queries against it (deck-builder Stage 1/3).

    python lib/deck_index.py index source_map.json vision_notes.json -o chunk_index.json
    python lib/deck_index.py query chunk_index.json --query "approval threshold" --top 6
    python lib/deck_index.py query chunk_index.json --section fsd#4.2.1 --top 6
    python lib/deck_index.py query chunk_index.json --query "colleagues" --brand brand_profile.json --top 6

Promoted out of training-material-generator's index_chunks.py/retrieve_chunks.py (which now
shim to this module — same precedent as lib/profile_template.py's shim in
cm-proposal-generator) and widened for deck-builder:

  * **origin field** — every chunk carries `origin: "prose" | "table" | "vision"`. A
    vision-derived chunk (from vision_notes.json, produced by a human/model reading a
    rasterised PDF page or image — see reference/vision-reading.md) is retrievable exactly
    like a text chunk, and `--origin vision` filters to it.
  * **query expansion** — `--brand profile.json` expands the query against
    messaging.terminology (term/definition pairs) and tone.preferred_terms, so a query
    using a generic phrase also matches the client's own word for it. Still no embeddings:
    this is a literal synonym substitution from data the client actually approved, not a
    learned similarity.
  * **section-path boost** — a term matching a chunk's section_path outranks the same term
    buried in body text (small multiplier, not a separate scoring pass).
  * **RRF fusion** — the raw-query ranking and the expanded-query ranking are fused with
    reciprocal-rank fusion, so expansion can only ADD candidates to the shortlist, never
    displace a chunk that matched the literal query.

Same doctrine as before, restated because it is the reason this file has no embeddings:
BM25 over an inverted index is literal and explainable — a ranking a practitioner can't
reason about can't be debugged when it pulls the wrong clause. `source_map.json` (the
complete outline) drives what a deck covers; retrieval only fills slides. Never let top-k
decide the story.

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
K1, B = 1.5, 0.75
SECTION_PATH_BOOST = 1.5


def tokenize(text):
    return [w.lower() for w in WORD_RE.findall(text) if w.lower() not in STOPWORDS]


def chunk_section(section, origin="prose"):
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
            "classifier": section.get("classifier", "narrative"),
            "origin": origin,
            "text": text,
            "figure_refs": figure_refs,
        })
    return chunks


def vision_note_to_chunk(note):
    """A vision_notes.json entry -> a retrievable chunk, origin='vision'.

    See reference/vision-reading.md for the note shape. section_id is synthesised from
    source_ref + page so a vision chunk still sorts and scopes (--section) like any other.
    """
    text = note.get("transcription", "")
    if note.get("structured"):
        text += " " + json.dumps(note["structured"])
    section_id = f"{note.get('source_ref', 'vision')}#p{note.get('page', 0)}"
    return {
        "chunk_id": f"vision::{note['note_id']}",
        "section_id": section_id,
        "document_id": note.get("source_ref", ""),
        "section_path": f"{note.get('source_ref', '')} / page {note.get('page', '?')} / {note.get('kind', 'image')}",
        "classifier": "reference",
        "origin": "vision",
        "text": text,
        "figure_refs": [],
        "note_id": note["note_id"],
        "confidence": note.get("confidence", "medium"),
    }


def build_index(chunks):
    df = {}
    postings = {}
    for c in chunks:
        terms = tokenize(c["text"] + " " + c["section_path"])
        counts = {}
        for t in terms:
            counts[t] = counts.get(t, 0) + 1
        postings[c["chunk_id"]] = counts
        for t in counts:
            df[t] = df.get(t, 0) + 1
    return df, postings


def build(source_map, vision_notes=None):
    chunks = []
    for section in source_map.get("sections", []):
        chunks.extend(chunk_section(section))
    for note in (vision_notes or {}).get("notes", []):
        chunks.append(vision_note_to_chunk(note))
    if not chunks:
        sys.exit("no chunkable text or vision notes found — did map_source.py / the vision pass run?")
    df, postings = build_index(chunks)
    return {
        "run_id": source_map.get("run_id"),
        "source_map_ref": None,
        "chunk_count": len(chunks),
        "doc_count": len(chunks),
        "avg_chunk_len": sum(len(p) for p in postings.values()) / len(postings) if postings else 0,
        "chunks": chunks,
        "postings": postings,
        "doc_freq": df,
    }


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def bm25_score(query_terms, chunk_id, postings, df, doc_count, avg_len, section_path_terms=None):
    counts = postings.get(chunk_id, {})
    doc_len = sum(counts.values()) or 1
    score = 0.0
    section_path_terms = section_path_terms or set()
    for t in query_terms:
        f = counts.get(t, 0)
        if f == 0:
            continue
        n_t = df.get(t, 0)
        idf = math.log((doc_count - n_t + 0.5) / (n_t + 0.5) + 1)
        term_score = idf * (f * (K1 + 1)) / (f + K1 * (1 - B + B * doc_len / avg_len))
        if t in section_path_terms:
            term_score *= SECTION_PATH_BOOST
        score += term_score
    return score


def expand_query(query_terms, brand_profile):
    """Add synonym terms from the brand profile's terminology map / preferred terms.
    Returns a NEW term list — the caller keeps the original for RRF fusion."""
    if not brand_profile:
        return list(query_terms)
    extra = set()
    for entry in brand_profile.get("messaging", {}).get("terminology", []):
        term_words = set(tokenize(entry.get("term", "")))
        def_words = set(tokenize(entry.get("definition", "")))
        if term_words & set(query_terms) or def_words & set(query_terms):
            extra |= term_words | def_words
    for avoid, use in brand_profile.get("tone", {}).get("preferred_terms", {}).items():
        if set(tokenize(avoid)) & set(query_terms):
            extra |= set(tokenize(use))
    return list(dict.fromkeys(list(query_terms) + list(extra)))  # dedupe, keep order


def rrf_fuse(rankings, k=60):
    """rankings: list of ordered chunk_id lists (best first). Reciprocal-rank fusion —
    expansion can only ADD candidates to the top of the list, never remove one that a
    literal-query ranking already put there (case: retrieval #25)."""
    scores = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda c: scores[c], reverse=True)


def query_index(idx, query="", section=None, classifier=None, origin=None, top=5, brand_profile=None):
    chunks = {c["chunk_id"]: c for c in idx["chunks"]}
    candidates = list(chunks.values())
    if section:
        candidates = [c for c in candidates if c["section_id"] == section or c["section_id"].startswith(section + ".")]
    if classifier:
        candidates = [c for c in candidates if c["classifier"] == classifier]
    if origin:
        candidates = [c for c in candidates if c["origin"] == origin]
    if not candidates:
        return []
    cand_ids = {c["chunk_id"] for c in candidates}

    if not query:
        return candidates[:top]

    query_terms = tokenize(query)

    def rank_for(terms):
        scored = []
        for c in candidates:
            path_terms = set(tokenize(c["section_path"]))
            s = bm25_score(terms, c["chunk_id"], idx["postings"], idx["doc_freq"], idx["doc_count"], idx["avg_chunk_len"], path_terms)
            if s > 0:
                scored.append((s, c["chunk_id"]))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [cid for _, cid in scored]

    literal_rank = rank_for(query_terms)
    expanded_terms = expand_query(query_terms, brand_profile)
    if expanded_terms != query_terms:
        expanded_rank = rank_for(expanded_terms)
        fused = rrf_fuse([literal_rank, expanded_rank])
    else:
        fused = literal_rank

    fused = [cid for cid in fused if cid in cand_ids][:top]
    return [chunks[cid] for cid in fused]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    idx_ap = sub.add_parser("index")
    idx_ap.add_argument("source_map", type=Path)
    idx_ap.add_argument("vision_notes", type=Path, nargs="?")
    idx_ap.add_argument("-o", "--out", type=Path, default=Path("chunk_index.json"))

    q_ap = sub.add_parser("query")
    q_ap.add_argument("index", type=Path)
    q_ap.add_argument("--query", default="")
    q_ap.add_argument("--section", default=None)
    q_ap.add_argument("--classifier", default=None, choices=["procedure", "reference", "narrative", "config", "non-functional"])
    q_ap.add_argument("--origin", default=None, choices=["prose", "table", "vision"])
    q_ap.add_argument("--brand", type=Path, default=None, help="brand_profile.json for query expansion")
    q_ap.add_argument("--top", type=int, default=5)
    q_ap.add_argument("--json", action="store_true")

    args = ap.parse_args()

    if args.cmd == "index":
        source_map = json.loads(args.source_map.read_text(encoding="utf-8"))
        vision_notes = json.loads(args.vision_notes.read_text(encoding="utf-8")) if args.vision_notes and args.vision_notes.is_file() else None
        index = build(source_map, vision_notes)
        index["source_map_ref"] = str(args.source_map)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(index, indent=2), encoding="utf-8")
        vc = sum(1 for c in index["chunks"] if c["origin"] == "vision")
        print(f"{index['chunk_count']} chunk(s) ({vc} from vision notes) -> {args.out}")
        return 0

    idx = json.loads(args.index.read_text(encoding="utf-8"))
    brand = json.loads(args.brand.read_text(encoding="utf-8")) if args.brand else None
    results = query_index(idx, args.query, args.section, args.classifier, args.origin, args.top, brand)

    if args.json:
        print(json.dumps(results, indent=2))
        return 0
    if not results:
        print("no matching chunks")
        return 0
    for c in results:
        preview = c["text"][:160].replace("\n", " ")
        print(f"[{c['origin']}] {c['chunk_id']}  ({c['section_path']})")
        print(f"        {preview}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
