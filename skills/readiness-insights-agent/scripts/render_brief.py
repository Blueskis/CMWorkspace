#!/usr/bin/env python3
"""Stage 6 - render the readiness brief as one self-contained HTML file.

    python render_brief.py insights.json analysis.json programme.json -o brief.html

No dependencies, no external assets, nothing fetched at open time - the file can be
mailed to a sponsor or opened from a locked-down laptop. Layout, in the order a steerco
reads it: headline, the heatmap, insights ordered by how little time is left to act,
themes with their quotes, blind spots, and the milestone strip.

Every insight card carries its evidence IDs and its action window. That is the point:
the brief and its audit trail are the same document.
"""

import argparse
import html
import json
from datetime import date
from pathlib import Path

BAND_STYLE = {
    "green": ("#1a7f4b", "#e6f4ec"), "amber": ("#8a5a00", "#fdf1dc"),
    "red": ("#a3252b", "#fbe9ea"), "thin": ("#5a5f6b", "#eef0f3"),
    "no_data": ("#8b8f98", "#f7f8fa"),
}
VERDICT_STYLE = {"too_late": "#a3252b", "act_now": "#8a5a00", "in_window": "#1a7f4b",
                 "unanchored": "#5a5f6b"}
CSS = """
*{box-sizing:border-box}body{margin:0;font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:#1c1f26;background:#f4f5f7}
.wrap{max-width:1080px;margin:0 auto;padding:40px 24px 72px}
header{border-bottom:3px solid #1c1f26;padding-bottom:20px;margin-bottom:32px}
h1{font-size:30px;margin:0 0 6px}h2{font-size:20px;margin:40px 0 14px;padding-bottom:6px;border-bottom:1px solid #d8dbe0}
.meta{color:#5a5f6b;font-size:14px}
.headline{background:#fff;border-left:5px solid #1c1f26;padding:18px 22px;margin:20px 0 0;font-size:18px}
table{border-collapse:collapse;width:100%;font-size:14px;background:#fff}
th,td{border:1px solid #e2e5ea;padding:8px 10px;text-align:left;vertical-align:top}
th{background:#eef0f3;font-weight:600}
.cell{font-weight:600;white-space:nowrap}.sub{display:block;font-weight:400;color:#5a5f6b;font-size:12px}
.card{background:#fff;border:1px solid #e2e5ea;border-left:5px solid #5a5f6b;padding:16px 20px;margin:14px 0}
.card h3{margin:0 0 6px;font-size:17px}
.tags span{display:inline-block;font-size:12px;padding:2px 8px;margin:0 6px 6px 0;border-radius:10px;background:#eef0f3;color:#3c414b}
.window{font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.04em}
.ev{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;color:#5a5f6b;margin-top:10px;word-break:break-word}
blockquote{margin:8px 0;padding:6px 14px;border-left:3px solid #c9ced6;color:#3c414b;font-style:italic}
.strip{display:flex;gap:10px;overflow-x:auto;padding-bottom:8px}
.ms{flex:0 0 190px;background:#fff;border:1px solid #e2e5ea;border-top:4px solid #5a5f6b;padding:12px}
.ms b{display:block;font-size:14px}.ms span{font-size:12px;color:#5a5f6b}
footer{margin-top:48px;padding-top:16px;border-top:1px solid #d8dbe0;color:#5a5f6b;font-size:13px}
"""


def esc(x):
    return html.escape(str(x if x is not None else ""))


def heatmap(analysis):
    index = {(c["dimension"], c["segment"]): c for c in analysis["cells"]}
    head = "".join(f"<th>{esc(d.replace('_', ' '))}</th>" for d in analysis["dimensions"])
    rows = []
    for seg in analysis["segments"]:
        tds = []
        for dim in analysis["dimensions"]:
            c = index[(dim, seg)]
            fg, bg = BAND_STYLE[c["band"]]
            if c["n"] == 0:
                body = "no data"
            else:
                delta = f" {c['delta']:+}" if "delta" in c else ""
                body = f"{c['mean']}{delta}<span class='sub'>n={c['n']}" \
                       + (" thin base" if c["band"] == "thin" else "") + "</span>"
            tds.append(f"<td class='cell' style='color:{fg};background:{bg}'>{body}</td>")
        rows.append(f"<tr><th>{esc(seg)}</th>{''.join(tds)}</tr>")
    p = analysis["params"]
    return (f"<table><tr><th>Segment</th>{head}</tr>{''.join(rows)}</table>"
            f"<p class='meta'>0-100 normalised. Green &ge; {p['bands']['green']}, "
            f"amber &ge; {p['bands']['amber']}, red below; a base under n={p['min_n']} is "
            f"shown as a thin base and never banded green. Deltas are wave on wave.</p>")


def windows(insights, programme):
    """Days to milestone and verdict, recomputed here so the brief stands alone."""
    ms = {m["milestone_id"]: m for m in programme["milestones"]}
    as_of = date.fromisoformat(insights["programme"]["as_of"])
    out = {}
    for ins in insights["insights"]:
        m = ms.get(ins.get("milestone_id", ""))
        if not m:
            out[ins["insight_id"]] = ("unanchored", None, "no dated milestone")
            continue
        left = (date.fromisoformat(m["date"]) - as_of).days
        lead = ins.get("remediation_lead_time_days")
        if lead is None:
            v = "act_now"
        elif lead > left:
            v = "too_late"
        elif left - lead <= 5:
            v = "act_now"
        else:
            v = "in_window"
        label = f"{m['name']} in {left} day(s)" + (f"; action needs {lead}" if lead is not None else "")
        out[ins["insight_id"]] = (v, left, label)
    return out


def insight_cards(insights, win):
    order = {"too_late": 0, "act_now": 1, "in_window": 2, "unanchored": 3}
    cards = []
    for ins in sorted(insights["insights"],
                      key=lambda i: (order[win[i["insight_id"]][0]],
                                     win[i["insight_id"]][1] if win[i["insight_id"]][1] is not None else 9999)):
        verdict, _, label = win[ins["insight_id"]]
        colour = VERDICT_STYLE[verdict]
        ev = ins.get("evidence", {})
        ids = ev.get("analysis_cells", []) + ev.get("theme_ids", []) + ev.get("signal_ids", [])
        tags = [ins["dimension"].replace("_", " ")] + list(ins.get("segments", [])) + \
               [f"confidence: {ins.get('confidence')}"]
        gap = (f"<p><b>[GAP]</b> {esc(ins.get('gap_note'))}</p>" if ins.get("gap") else "")
        cards.append(f"""
<div class="card" style="border-left-color:{colour}">
  <h3>{esc(ins['insight_id'])} &mdash; {esc(ins['headline'])}</h3>
  <p class="window" style="color:{colour}">{esc(verdict.replace('_', ' '))} &middot; {esc(label)}</p>
  <p><b>So what:</b> {esc(ins['so_what'])}</p>
  <p><b>Do:</b> {esc(ins['recommended_action'])}
     {(' &mdash; <i>' + esc(ins['owner_hint']) + '</i>') if ins.get('owner_hint') else ''}</p>
  {gap}
  <p class="tags">{''.join(f'<span>{esc(t)}</span>' for t in tags)}</p>
  <p class="ev">evidence: {esc(', '.join(ids)) or 'none cited'}
     {('&middot; ' + esc(ins['confidence_note'])) if ins.get('confidence_note') else ''}</p>
</div>""")
    return "".join(cards)


def theme_blocks(insights):
    out = []
    for t in insights.get("themes", []):
        quote = f"<blockquote>{esc(t['illustrative_quote'])}</blockquote>" if t.get("illustrative_quote") else ""
        out.append(f"""
<div class="card">
  <h3>{esc(t['theme_id'])} &mdash; {esc(t['label'])}</h3>
  <p class="meta">{esc(t['dimension'].replace('_', ' '))}
     {(' &middot; ' + esc(', '.join(t.get('segments', [])))) if t.get('segments') else ''}
     {(' &middot; ' + esc(t['prevalence'])) if t.get('prevalence') else ''}</p>
  {quote}
  {('<p><b>Counter-signal:</b> ' + esc(t['counter_signal']) + '</p>') if t.get('counter_signal') else ''}
  <p class="ev">quotes: {esc(', '.join(t['signal_ids']))}</p>
</div>""")
    return "".join(out)


def blind_spot_table(insights):
    def row(b):
        n = b.get("n")
        status = b["status"] if n is None else f"{b['status']} (n={n})"
        return (f"<tr><td>{esc(b['segment'])}</td>"
                f"<td>{esc(b['dimension'].replace('_', ' '))}</td>"
                f"<td>{esc(status)}</td>"
                f"<td>{esc(b.get('why_it_matters'))}</td>"
                f"<td>{esc(b.get('how_to_close'))}</td></tr>")

    rows = "".join(row(b) for b in insights.get("blind_spots", []))
    if not rows:
        return "<p>Every segment and dimension carries a readable base.</p>"
    return ("<table><tr><th>Segment</th><th>Dimension</th><th>Status</th>"
            "<th>Why it matters</th><th>How to close it</th></tr>" + rows + "</table>")


def milestone_strip(programme, as_of):
    cards = []
    for m in sorted(programme["milestones"], key=lambda m: m["date"]):
        left = (date.fromisoformat(m["date"]) - as_of).days
        when = f"in {left} day(s)" if left >= 0 else f"{abs(left)} day(s) ago"
        cards.append(f"<div class='ms'><b>{esc(m['name'])}</b>"
                     f"<span>{esc(m['date'])} &middot; {esc(when)}</span>"
                     f"<span>{esc(m['type'].replace('_', ' '))}"
                     f"{(' &middot; ' + esc(m['owner'])) if m.get('owner') else ''}</span></div>")
    return f"<div class='strip'>{''.join(cards)}</div>"


def build(insights, analysis, programme):
    as_of = date.fromisoformat(insights["programme"]["as_of"])
    win = windows(insights, programme)
    name = insights["programme"]["name"]
    counts = {v: sum(1 for k in win if win[k][0] == v) for v in VERDICT_STYLE}
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Readiness brief - {esc(name)}</title><style>{CSS}</style></head>
<body><div class="wrap">
<header>
  <h1>Change readiness brief</h1>
  <p class="meta">{esc(name)} &middot; as of {esc(as_of.isoformat())} &middot;
     {len(analysis['cells'])} matrix cells, {len(insights['insights'])} insights,
     {counts['too_late']} past the action window</p>
  <p class="headline">{esc(insights['programme'].get('headline', '(no headline written)'))}</p>
</header>
<h2>Readiness heatmap</h2>{heatmap(analysis)}
<h2>Insights, ordered by how little time is left</h2>{insight_cards(insights, win)}
<h2>What people actually said</h2>{theme_blocks(insights)}
<h2>Blind spots</h2>
<p class="meta">Cells with no data or too thin a base to read. Listed because an empty
cell is not a green one.</p>{blind_spot_table(insights)}
<h2>Upcoming milestones</h2>{milestone_strip(programme, as_of)}
<footer>Draft for practitioner review. Every insight above cites the signal IDs,
analysis cells, and themes behind it; anything unsourced is marked [GAP]. Generated by
readiness-insights-agent v0.1.</footer>
</div></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("insights")
    ap.add_argument("analysis")
    ap.add_argument("programme")
    ap.add_argument("-o", "--output", default="brief.html")
    args = ap.parse_args()
    load = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
    doc = build(load(args.insights), load(args.analysis), load(args.programme))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(doc, encoding="utf-8")
    print(f"brief written to {args.output} ({len(doc) // 1024} KB)")


if __name__ == "__main__":
    main()
