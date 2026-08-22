#!/usr/bin/env python3
"""Stage 5 audit - evidence, coverage, timeline anchoring, and confidence honesty.

    python qa_insights.py signals.json analysis.json insights.json \
        --programme programme.json -o qa_report.md

The four checks that must not be done by eye:

  1. Evidence resolves      every cited signal ID, analysis cell, and theme ID exists;
                            every insight cites something or is flagged as a gap.
  2. Coverage declared      every no-data or thin cell in the analysis appears in
                            blind_spots. A cell the brief never mentions reads as fine,
                            which is the single most common way these reports mislead.
  3. Timeline anchored      every insight names a real milestone or sets not_time_bound.
  4. Confidence honest      an insight resting only on a thin cell, or only on a source
                            under the response-rate floor, must be confidence 'low'.

Hard failures (non-zero exit): unresolved evidence, an undeclared blind spot, a broken
or missing milestone anchor, an overstated confidence, a theme with fewer than two
quotes, or a gap insight without a gap_note.
"""

import argparse
import json
import sys
from pathlib import Path


def audit(signals, analysis, insights, programme, min_rate):
    sig_ids = {s["signal_id"] for s in signals["signals"]}
    sources = {s["source_id"]: s for s in signals["sources"]}
    cells = {c["cell_id"]: c for c in analysis["cells"]}
    themes = {t["theme_id"]: t for t in insights.get("themes", [])}
    milestones = {m["milestone_id"] for m in programme["milestones"]} if programme else set()
    low_rate = {sid for sid, s in sources.items()
                if s.get("response_rate_pct") is not None and s["response_rate_pct"] < min_rate}

    fail, warn = [], []

    # 1 - evidence resolves
    for t in insights.get("themes", []):
        missing = [i for i in t["signal_ids"] if i not in sig_ids]
        if missing:
            fail.append(f"theme {t['theme_id']} cites unknown signal(s): {', '.join(missing)}")
        if len(t["signal_ids"]) < 2:
            fail.append(f"theme {t['theme_id']} rests on {len(t['signal_ids'])} quote(s) - "
                        "a theme needs at least two")
        if not t.get("counter_signal"):
            warn.append(f"theme {t['theme_id']} records no counter-signal - "
                        "state what cuts against it, or 'none found'")

    for ins in insights["insights"]:
        iid = ins["insight_id"]
        ev = ins.get("evidence", {})
        cited_sigs = ev.get("signal_ids", [])
        cited_cells = ev.get("analysis_cells", [])
        cited_themes = ev.get("theme_ids", [])

        for i in cited_sigs:
            if i not in sig_ids:
                fail.append(f"{iid} cites unknown signal {i}")
        for c in cited_cells:
            if c not in cells:
                fail.append(f"{iid} cites unknown analysis cell {c}")
        for t in cited_themes:
            if t not in themes:
                fail.append(f"{iid} cites unknown theme {t}")

        if not (cited_sigs or cited_cells or cited_themes):
            if ins.get("gap"):
                if not ins.get("gap_note"):
                    fail.append(f"{iid} is a gap with no gap_note")
            else:
                fail.append(f"{iid} carries no evidence and is not flagged as a gap")

        # 3 - timeline anchored
        if ins.get("not_time_bound"):
            pass
        elif not ins.get("milestone_id"):
            fail.append(f"{iid} names no milestone and is not marked not_time_bound")
        elif milestones and ins["milestone_id"] not in milestones:
            fail.append(f"{iid} points at milestone {ins['milestone_id']}, "
                        "which is not in the programme")
        elif ins.get("remediation_lead_time_days") is None:
            warn.append(f"{iid} has no remediation_lead_time_days - "
                        "the action window cannot be computed")

        # 4 - confidence honest
        resting_cells = [cells[c] for c in cited_cells if c in cells]
        thin_only = resting_cells and all(c["band"] in ("thin", "no_data") for c in resting_cells)
        sig_sources = {s.split("-")[0] for s in cited_sigs}
        for c in resting_cells:
            sig_sources.update(c.get("sources", []))
        rate_only = bool(sig_sources) and sig_sources <= low_rate
        if (thin_only or rate_only) and ins.get("confidence") != "low":
            why = "a thin base" if thin_only else f"sources under a {min_rate}% response rate"
            fail.append(f"{iid} is confidence '{ins.get('confidence')}' but rests only on {why}")

    # 2 - coverage declared
    declared = {(b["segment"], b["dimension"]) for b in insights.get("blind_spots", [])}
    undeclared = [b for b in analysis["coverage"]["blind_spots"]
                  if (b["segment"], b["dimension"]) not in declared]
    for b in undeclared:
        fail.append(f"blind spot not declared: {b['segment']} x {b['dimension']} "
                    f"({b['status']}, n={b['n']})")

    spurious = declared - {(b["segment"], b["dimension"])
                           for b in analysis["coverage"]["blind_spots"]}
    for seg, dim in sorted(spurious):
        warn.append(f"blind spot declared for {seg} x {dim}, but the analysis has data there")

    return fail, warn, {
        "signals": len(sig_ids), "sources": len(sources),
        "insights": len(insights["insights"]), "themes": len(themes),
        "cells_with_data": analysis["coverage"]["cells_with_data"],
        "cells_total": analysis["coverage"]["cells_total"],
        "blind_spots": len(analysis["coverage"]["blind_spots"]),
        "low_rate_sources": sorted(low_rate),
        "gaps": [i["insight_id"] for i in insights["insights"] if i.get("gap")],
    }


def render(fail, warn, stats):
    out = ["# Readiness brief QA", "",
           f"- {stats['signals']} signals from {stats['sources']} source(s)",
           f"- {stats['insights']} insight(s), {stats['themes']} theme(s)",
           f"- {stats['cells_with_data']}/{stats['cells_total']} matrix cells carry data; "
           f"{stats['blind_spots']} blind spot(s)",
           ""]
    if stats["low_rate_sources"]:
        out.append("Sources under the response-rate floor: "
                   + ", ".join(stats["low_rate_sources"]))
    if stats["gaps"]:
        out.append("Open gaps: " + ", ".join(stats["gaps"]))
    out += ["", "## Result", ""]
    out.append("**FAIL**" if fail else "**PASS**")
    if fail:
        out += ["", "### Must fix", ""] + [f"- {f}" for f in fail]
    if warn:
        out += ["", "### Worth a look", ""] + [f"- {w}" for w in warn]
    out += ["", "## What this does not check", "",
            "- Whether a theme is a fair reading of the quotes behind it.",
            "- Whether a recommended action is the right one.",
            "- Whether a lead-time estimate is realistic.",
            "",
            "A practitioner reads for those. This checks that nothing is unsourced,",
            "nothing silently missing, and nothing floating free of the timeline.", ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("signals")
    ap.add_argument("analysis")
    ap.add_argument("insights")
    ap.add_argument("--programme")
    ap.add_argument("--min-response-rate", type=float, default=30.0)
    ap.add_argument("-o", "--output")
    args = ap.parse_args()

    load = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
    programme = load(args.programme) if args.programme else None
    fail, warn, stats = audit(load(args.signals), load(args.analysis),
                              load(args.insights), programme, args.min_response_rate)
    report = render(fail, warn, stats)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(report, encoding="utf-8")
    print(report)
    if fail:
        print(f"\n{len(fail)} hard failure(s)", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
