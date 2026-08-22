#!/usr/bin/env python3
"""Stage 3b - lay the free-text feedback out for coding, with counts done for you.

    python prepare_verbatims.py signals.json -o verbatims.md
    python prepare_verbatims.py signals.json --dimension capacity --segment "Field Ops"

This does not cluster or interpret. Clustering by keyword produces themes that are about
vocabulary rather than meaning, and 'training' appearing 40 times is not a finding. What
it does is make honest coding cheap: every verbatim is listed once, under its dimension
and segment, with its signal ID attached so a theme can cite it, plus a term-frequency
table as a starting hint and a total to compute prevalence against.

The model reads this file and writes themes into insights.json. Stage 5 then checks that
every cited ID exists and every theme carries at least two of them.
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

STOPWORDS = set("""
a an and are as at be been but by can could do does for from get got had has have how i
if in is it its just like me more much my no not of on or our so than that the their them
then there they this to too us was we were what when which who will with would you your
've n't don't didn't it's i'm we're there's really very lot bit thing things
""".split())


def tokens(text):
    return [w for w in re.findall(r"[a-z][a-z'-]{2,}", text.lower()) if w not in STOPWORDS]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("signals")
    ap.add_argument("--segment-key", default="group")
    ap.add_argument("--dimension", help="filter to one readiness dimension")
    ap.add_argument("--segment", help="filter to one segment")
    ap.add_argument("--top-terms", type=int, default=15)
    ap.add_argument("-o", "--output", help="write markdown here (default: stdout)")
    args = ap.parse_args()

    data = json.loads(Path(args.signals).read_text(encoding="utf-8"))
    labels = {s["source_id"]: s["label"] for s in data["sources"]}

    verbatims = [s for s in data["signals"] if s["type"] == "verbatim"]
    total = len(verbatims)
    if args.dimension:
        verbatims = [s for s in verbatims if s["dimension"] == args.dimension]
    if args.segment:
        verbatims = [s for s in verbatims
                     if (s.get("segment") or {}).get(args.segment_key) == args.segment]

    grouped = {}
    for s in verbatims:
        seg = (s.get("segment") or {}).get(args.segment_key, "(unstated)")
        grouped.setdefault((s["dimension"], seg), []).append(s)

    lines = [
        "# Verbatim coding worksheet",
        "",
        f"{len(verbatims)} verbatim(s) shown of {total} in the signal set.",
        "Prevalence in a theme is counted against the total above, or against the",
        "dimension subtotal - state which.",
        "",
    ]
    for (dim, seg) in sorted(grouped):
        items = grouped[(dim, seg)]
        lines += [f"## {dim.replace('_', ' ')} - {seg}  ({len(items)} verbatims)", ""]
        for s in items:
            src = labels.get(s["source_id"], s["source_id"])
            q = f" - *{s['question']}*" if s.get("question") else ""
            lines.append(f"- `{s['signal_id']}` [{src}]{q}")
            lines.append(f"  > {s['text']}")
        counts = Counter(w for s in items for w in tokens(s["text"]))
        if counts:
            top = ", ".join(f"{w} ({c})" for w, c in counts.most_common(args.top_terms) if c > 1)
            lines += ["", f"  Frequent terms: {top or '(nothing repeats)'}", ""]
        else:
            lines.append("")

    all_counts = Counter(w for s in verbatims for w in tokens(s.get("text", "")))
    lines += ["## Term frequency across the shown set", "",
              ", ".join(f"{w} ({c})" for w, c in all_counts.most_common(args.top_terms)) or "(none)",
              "",
              "Frequency is a hint about where to look, not a theme. Code on meaning:",
              "two people saying 'training' about different problems are two themes.",
              ""]

    text = "\n".join(lines)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"{len(verbatims)} verbatim(s) in {len(grouped)} group(s) -> {args.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()
