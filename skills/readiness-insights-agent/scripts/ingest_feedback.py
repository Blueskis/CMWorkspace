#!/usr/bin/env python3
"""Stage 1 - normalise heterogeneous feedback files into one signal set.

    python ingest_feedback.py --map adapters/training_eval_w2.json \
                              --map adapters/comms_form.json \
                              -o signals.json

Each --map is a source adapter: a small JSON file saying which columns of one CSV are
quantitative items, which are free text, which carry segment attributes, and which
readiness dimension each item measures. See reference/source-adapters.md for the format
and for the reason the mapping is written down rather than inferred per row.

The script does no interpretation. It reads columns, coerces scales to a 0-100
normalised score (applying reverse-coding where the adapter declares it), assigns every
value a stable signal ID, and refuses to guess: a row whose value is blank, non-numeric,
or off-scale is dropped and counted, never silently coerced to zero.
"""

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

DIMENSIONS = {
    "awareness", "understanding", "buy_in", "skills",
    "system_readiness", "capacity", "leadership_support", "confidence",
}


def normalise(value, scale):
    lo, hi = float(scale["min"]), float(scale["max"])
    if hi == lo:
        raise ValueError("scale min and max are equal")
    if not lo <= value <= hi:
        return None
    pct = (value - lo) / (hi - lo) * 100.0
    return round(100.0 - pct if scale.get("reverse") else pct, 1)


def read_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def ingest_one(adapter, adapter_path, warnings):
    doc = (adapter_path.parent / adapter["document"]).resolve()
    if not doc.exists():
        doc = Path(adapter["document"]).resolve()
    rows = read_rows(doc)

    sid = adapter["source_id"]
    for item in adapter.get("quant", []) + adapter.get("verbatim", []):
        if item["dimension"] not in DIMENSIONS:
            raise SystemExit(
                f"{adapter_path}: unknown dimension {item['dimension']!r} "
                f"(expected one of {', '.join(sorted(DIMENSIONS))})"
            )

    source = {
        "source_id": sid,
        "label": adapter["label"],
        "instrument": adapter["instrument"],
        "document": str(doc),
        "responses": len(rows),
    }
    for key in ("collected_from", "collected_to", "population", "wave"):
        if key in adapter:
            source[key] = adapter[key]

    signals, counter, dropped = [], 0, 0
    seg_cols = adapter.get("segment_columns", {})
    date_col = adapter.get("date_column")

    for row in rows:
        segment = {}
        for out_key, col in seg_cols.items():
            val = (row.get(col) or "").strip()
            segment[out_key] = val if val else "(unstated)"
        row_date = (row.get(date_col) or "").strip() if date_col else ""
        row_date = row_date or adapter.get("default_date", "")
        respondent = (row.get(adapter["respondent_column"]) or "").strip() if adapter.get("respondent_column") else ""

        def base(item):
            rec = {"source_id": sid, "dimension": item["dimension"]}
            if item.get("question"):
                rec["question"] = item["question"]
            if segment:
                rec["segment"] = dict(segment)
            if row_date:
                rec["date"] = row_date
            if respondent:
                rec["respondent_ref"] = respondent
            return rec

        for item in adapter.get("quant", []):
            raw = (row.get(item["column"]) or "").strip()
            if raw == "":
                dropped += 1
                continue
            try:
                value = float(raw)
            except ValueError:
                dropped += 1
                warnings.append(f"{sid}: non-numeric value {raw!r} in column {item['column']!r}")
                continue
            scale = item.get("scale", adapter.get("default_scale", {"min": 1, "max": 5}))
            norm = normalise(value, scale)
            if norm is None:
                dropped += 1
                warnings.append(
                    f"{sid}: value {value} outside scale "
                    f"{scale['min']}-{scale['max']} in column {item['column']!r}"
                )
                continue
            counter += 1
            rec = base(item)
            rec.update({
                "signal_id": f"{sid}-{counter:03d}",
                "type": "quant",
                "value": value,
                "normalised": norm,
                "scale": scale,
            })
            signals.append(rec)

        for item in adapter.get("verbatim", []):
            text = (row.get(item["column"]) or "").strip()
            if len(text) < adapter.get("min_verbatim_chars", 3):
                dropped += 1
                continue
            counter += 1
            rec = base(item)
            rec.update({
                "signal_id": f"{sid}-{counter:03d}",
                "type": "verbatim",
                "text": text,
            })
            signals.append(rec)

    if dropped:
        warnings.append(f"{sid}: {dropped} blank or unusable cell(s) dropped, not imputed")
    if source.get("population"):
        rate = len(rows) / source["population"] * 100
        source["response_rate_pct"] = round(rate, 1)
        if rate < 30:
            warnings.append(
                f"{sid}: response rate {rate:.0f}% - too thin to generalise from on its own"
            )
    return source, signals


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--map", dest="maps", action="append", required=True,
                    help="source adapter JSON (repeatable, one per feedback file)")
    ap.add_argument("-o", "--output", default="signals.json")
    args = ap.parse_args()

    sources, signals, warnings = [], [], []
    seen = set()
    for m in args.maps:
        path = Path(m)
        adapter = json.loads(path.read_text(encoding="utf-8"))
        if adapter["source_id"] in seen:
            raise SystemExit(f"duplicate source_id {adapter['source_id']!r} across adapters")
        seen.add(adapter["source_id"])
        src, sigs = ingest_one(adapter, path, warnings)
        sources.append(src)
        signals.extend(sigs)

    out = {"generated": date.today().isoformat(), "sources": sources, "signals": signals}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    quant = sum(1 for s in signals if s["type"] == "quant")
    print(f"{len(sources)} source(s) -> {len(signals)} signals ({quant} quant, {len(signals) - quant} verbatim)")
    for src in sources:
        rate = f", {src['response_rate_pct']}% response" if "response_rate_pct" in src else ""
        print(f"  {src['source_id']}  {src['label']}  ({src['responses']} responses{rate})")
    for w in warnings:
        print(f"  warning: {w}", file=sys.stderr)
    print(f"written to {args.output}")


if __name__ == "__main__":
    main()
