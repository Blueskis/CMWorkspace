#!/usr/bin/env python3
"""Stage 4b - read each insight against the clock.

    python timeline_join.py insights.json programme.json -o action_windows.md

An insight without a date attached is an observation. This joins every insight to the
milestone it bears on, works out the days left from the programme's as_of date, and
compares that against the lead time its recommended action actually needs.

Three verdicts:

  act_now        the window is open but the slack is under --slack days
  too_late       remediation needs longer than remains - the decision is now about
                 descoping, delaying, or accepting the risk, not about doing the action
  in_window      there is room, provided it starts

'too_late' is the output that earns this script its place. A readiness report that
recommends a four-week intervention nine days out is worse than no report.
"""

import argparse
import json
from datetime import date
from pathlib import Path

RANK = {"too_late": 0, "act_now": 1, "in_window": 2, "unanchored": 3}


def parse(d):
    return date.fromisoformat(d)


def join(insights, programme, slack):
    milestones = {m["milestone_id"]: m for m in programme["milestones"]}
    as_of = parse(insights["programme"].get("as_of") or programme["programme"]["as_of"])
    rows, unknown = [], []

    for ins in insights["insights"]:
        mid = ins.get("milestone_id")
        if not mid:
            rows.append({"insight_id": ins["insight_id"], "headline": ins["headline"],
                         "verdict": "unanchored", "milestone": "(not time bound)",
                         "days_left": None, "lead_time": ins.get("remediation_lead_time_days")})
            continue
        m = milestones.get(mid)
        if m is None:
            unknown.append((ins["insight_id"], mid))
            continue
        days_left = (parse(m["date"]) - as_of).days
        lead = ins.get("remediation_lead_time_days")
        if lead is None:
            verdict = "act_now"
        elif lead > days_left:
            verdict = "too_late"
        elif days_left - lead <= slack:
            verdict = "act_now"
        else:
            verdict = "in_window"
        rows.append({
            "insight_id": ins["insight_id"], "headline": ins["headline"],
            "milestone": f"{m['name']} ({m['date']})", "milestone_id": mid,
            "days_left": days_left, "lead_time": lead,
            "slack_days": None if lead is None else days_left - lead,
            "verdict": verdict, "action": ins.get("recommended_action", ""),
            "owner": ins.get("owner_hint", ""),
        })

    rows.sort(key=lambda r: (RANK[r["verdict"]], r["days_left"] if r["days_left"] is not None else 9999))
    return as_of, rows, unknown


def markdown(as_of, rows, unknown):
    out = [f"# Action windows (as of {as_of.isoformat()})", "",
           "| Insight | Milestone | Days left | Lead time | Slack | Verdict | Owner |",
           "|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append("| {id} | {ms} | {dl} | {lt} | {sl} | **{v}** | {ow} |".format(
            id=r["insight_id"], ms=r["milestone"],
            dl="-" if r["days_left"] is None else r["days_left"],
            lt="?" if r["lead_time"] is None else r["lead_time"],
            sl="-" if r.get("slack_days") is None else f"{r['slack_days']:+}",
            v=r["verdict"], ow=r["owner"] or "-"))
    late = [r for r in rows if r["verdict"] == "too_late"]
    if late:
        out += ["", "## Past the point the action fixes it", ""]
        for r in late:
            out += [f"- **{r['insight_id']}** - {r['headline']}",
                    f"  {r['milestone']} is {r['days_left']} days out; "
                    f"'{r['action']}' needs {r['lead_time']}.",
                    "  Escalate as a descope / delay / accept-the-risk decision, "
                    "not as an action item."]
    if unknown:
        out += ["", "## Broken milestone references", ""] + \
               [f"- {iid} points at {mid}, which is not in programme.json" for iid, mid in unknown]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("insights")
    ap.add_argument("programme")
    ap.add_argument("--slack", type=int, default=5,
                    help="days of slack at or below which an insight is 'act_now' (default: 5)")
    ap.add_argument("-o", "--output")
    args = ap.parse_args()

    insights = json.loads(Path(args.insights).read_text(encoding="utf-8"))
    programme = json.loads(Path(args.programme).read_text(encoding="utf-8"))
    as_of, rows, unknown = join(insights, programme, args.slack)
    text = markdown(as_of, rows, unknown)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text + "\n", encoding="utf-8")
        print(f"{len(rows)} insight(s) joined to the timeline -> {args.output}")
    else:
        print(text)
    raise SystemExit(1 if unknown else 0)


if __name__ == "__main__":
    main()
