#!/usr/bin/env python3
"""Stage 3a - roll the quantitative signals up into a segment x dimension matrix.

    python analyze_quant.py signals.json --programme programme.json -o analysis.json
    python analyze_quant.py signals.json --programme programme.json --markdown

Produces one cell per (dimension, segment) with n, mean normalised score, the share of
detractors, a RAG band, and the wave-on-wave movement where the sources carry wave
labels. Cell IDs ('A:confidence:Field Ops') are what insights cite, so a number in the
brief can always be traced back to the rows behind it.

Two things this deliberately does, because the failure mode of readiness reporting is a
green dashboard over a hole in the data:

  * A base below --min-n is banded 'thin', never green, however good the score.
  * Every segment named in programme.json is carried into the matrix even when it
    returned nothing at all - those cells are banded 'no_data' and flow through to the
    brief's blind spots.

Bands (on the 0-100 normalised score): green >= 70, amber >= 55, red below.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

DIMENSION_ORDER = [
    "awareness", "understanding", "buy_in", "skills",
    "system_readiness", "capacity", "leadership_support", "confidence",
]


def band(mean, n, min_n):
    if n == 0:
        return "no_data"
    if n < min_n:
        return "thin"
    if mean >= 70:
        return "green"
    if mean >= 55:
        return "amber"
    return "red"


def wave_order(sources):
    """Waves sorted by collection end date, falling back to source_id order."""
    waves = {}
    for src in sources:
        w = src.get("wave")
        if not w:
            continue
        key = src.get("collected_to") or src.get("collected_from") or src["source_id"]
        waves[w] = min(waves.get(w, key), key)
    return [w for w, _ in sorted(waves.items(), key=lambda kv: kv[1])]


def analyse(data, programme, segment_key, min_n, detractor_max):
    sources = {s["source_id"]: s for s in data["sources"]}
    order = wave_order(data["sources"])

    observed, buckets, wave_buckets = set(), {}, {}
    for sig in data["signals"]:
        if sig["type"] != "quant":
            continue
        seg = (sig.get("segment") or {}).get(segment_key, "(unstated)")
        observed.add(seg)
        buckets.setdefault((sig["dimension"], seg), []).append(sig)
        wave = sources.get(sig["source_id"], {}).get("wave")
        if wave:
            wave_buckets.setdefault((sig["dimension"], seg, wave), []).append(sig["normalised"])

    segments = [s["name"] for s in programme["segments"]] if programme else []
    for seg in sorted(observed):
        if seg not in segments:
            segments.append(seg)

    dimensions = [d for d in DIMENSION_ORDER
                  if any(k[0] == d for k in buckets)] or DIMENSION_ORDER

    cells = []
    for dim in dimensions:
        for seg in segments:
            sigs = buckets.get((dim, seg), [])
            scores = [s["normalised"] for s in sigs]
            n = len(scores)
            mean = round(statistics.fmean(scores), 1) if n else None
            cell = {
                "cell_id": f"A:{dim}:{seg}",
                "dimension": dim,
                "segment": seg,
                "n": n,
                "mean": mean,
                "band": band(mean if mean is not None else 0, n, min_n),
                "signal_ids": [s["signal_id"] for s in sigs],
            }
            if n:
                cell["median"] = round(statistics.median(scores), 1)
                cell["detractor_pct"] = round(
                    sum(1 for s in scores if s <= detractor_max) / n * 100, 1
                )
                cell["sources"] = sorted({s["source_id"] for s in sigs})
                by_wave = {
                    w: round(statistics.fmean(wave_buckets[(dim, seg, w)]), 1)
                    for w in order if (dim, seg, w) in wave_buckets
                }
                if by_wave:
                    cell["by_wave"] = by_wave
                if len(by_wave) >= 2:
                    seq = list(by_wave.values())
                    cell["delta"] = round(seq[-1] - seq[-2], 1)
                    cell["trend"] = (
                        "improving" if cell["delta"] >= 3
                        else "declining" if cell["delta"] <= -3
                        else "flat"
                    )
            cells.append(cell)

    blind = [
        {"segment": c["segment"], "dimension": c["dimension"],
         "status": "no_data" if c["band"] == "no_data" else "thin", "n": c["n"]}
        for c in cells if c["band"] in ("no_data", "thin")
    ]
    return {
        "params": {"segment_key": segment_key, "min_n": min_n,
                   "detractor_max": detractor_max, "bands": {"green": 70, "amber": 55}},
        "segments": segments,
        "dimensions": dimensions,
        "waves": order,
        "cells": cells,
        "coverage": {
            "cells_total": len(cells),
            "cells_with_data": sum(1 for c in cells if c["n"]),
            "blind_spots": blind,
        },
    }


SYMBOL = {"green": "G", "amber": "A", "red": "R", "thin": "~", "no_data": "-"}


def markdown(result):
    out = ["| Segment | " + " | ".join(d.replace("_", " ") for d in result["dimensions"]) + " |",
           "|---" * (len(result["dimensions"]) + 1) + "|"]
    index = {(c["dimension"], c["segment"]): c for c in result["cells"]}
    for seg in result["segments"]:
        row = [seg]
        for dim in result["dimensions"]:
            c = index[(dim, seg)]
            row.append("-" if c["n"] == 0 else
                       f"{SYMBOL[c['band']]} {c['mean']} (n={c['n']})"
                       + (f" {c['delta']:+}" if "delta" in c else ""))
        out.append("| " + " | ".join(row) + " |")
    cov = result["coverage"]
    out += ["",
            f"G >= 70, A >= 55, R below, ~ thin base (n < {result['params']['min_n']}), - no data.",
            f"{cov['cells_with_data']}/{cov['cells_total']} cells carry data; "
            f"{len(cov['blind_spots'])} blind spot(s)."]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("signals")
    ap.add_argument("--programme", help="programme.json - supplies the full segment list")
    ap.add_argument("--segment-key", default="group", help="segment attribute to roll up by (default: group)")
    ap.add_argument("--min-n", type=int, default=5, help="below this a cell is banded 'thin' (default: 5)")
    ap.add_argument("--detractor-max", type=float, default=40.0,
                    help="normalised score at or below which a response counts as a detractor (default: 40)")
    ap.add_argument("--markdown", action="store_true", help="print the matrix instead of writing JSON")
    ap.add_argument("-o", "--output", default="analysis.json")
    args = ap.parse_args()

    data = json.loads(Path(args.signals).read_text(encoding="utf-8"))
    programme = json.loads(Path(args.programme).read_text(encoding="utf-8")) if args.programme else None
    result = analyse(data, programme, args.segment_key, args.min_n, args.detractor_max)

    if args.markdown:
        print(markdown(result))
        return
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(markdown(result))
    print(f"\nwritten to {args.output}")
    if not result["coverage"]["cells_with_data"]:
        print("no quantitative signals found - check the adapters", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
