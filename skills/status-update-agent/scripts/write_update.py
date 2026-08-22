#!/usr/bin/env python3
"""Stage 3: merge this week's diffs into one change brief for the consultant to speak from.

    python write_update.py changes-*.json -o change_brief.json --md change_brief.md

Several documents are compared each week — a plan, a tracker, a status deck — and the
meeting hears one update, not three. This merges them into a single ID space (C1, C2, …,
each tagged with the document it came from), groups the changes the way an update is
actually delivered, and orders them by materiality.

It deliberately does **not** write the prose. It produces the evidence the narrative is
written from; the skill writes the update against this file and cites these IDs, and
qa_update.py then checks the two against each other.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

# The running order of a cadence update: what moved, what is going wrong, what is new,
# what changed hands, what the numbers say, what is being asked for.
GROUPS = [
    ("progress", "Progress since last week", ["status_forward", "rag_better", "date_pull_in"]),
    ("slippage", "Slipping or regressing", ["date_slip", "status_backward", "rag_worse"]),
    ("new", "New this week", ["item_added", "field_added"]),
    ("dropped", "Dropped or missing", ["item_removed", "field_removed"]),
    ("ownership", "Ownership and naming", ["owner_changed", "renamed"]),
    ("metrics", "Metrics", ["number_changed", "percent_changed"]),
    ("narrative", "Narrative changes", ["text_changed"]),
]
GROUP_OF = {t: key for key, _, types in GROUPS for t in types}
TITLES = {key: title for key, title, _ in GROUPS}
RANK = {"high": 0, "medium": 1, "low": 2}


def merge(paths):
    changes, documents, rollups, counter = [], [], [], 0
    for path in paths:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        comparison = data["comparison"]
        doc_name = comparison["current"]["name"]
        documents.append(
            {
                "document": doc_name,
                "doc_type": comparison["current"]["doc_type"],
                "previous_period": comparison["previous"]["period_label"],
                "current_period": comparison["current"]["period_label"],
                "changes_file": str(path),
                "summary": data["summary"],
            }
        )
        for roll in data.get("rollups", []):
            rollups.append(dict(roll, document=doc_name))
        for change in data["changes"]:
            counter += 1
            record = dict(change)
            record["local_change_id"] = change["change_id"]
            record["change_id"] = f"C{counter}"
            record["document"] = doc_name
            record["group"] = GROUP_OF.get(change["change_type"], "narrative")
            changes.append(record)

    # Local subsumption references have to be re-pointed at the merged IDs.
    remap = {(c["document"], c["local_change_id"]): c["change_id"] for c in changes}
    for change in changes:
        if change.get("subsumed_by"):
            change["subsumed_by"] = remap.get(
                (change["document"], change["subsumed_by"]), change["subsumed_by"]
            )

    changes.sort(key=lambda c: (RANK[c["materiality"]], int(c["change_id"][1:])))
    counts = {}
    for change in changes:
        counts[change["materiality"]] = counts.get(change["materiality"], 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "documents": documents,
        "totals": {
            "changes": len(changes),
            "by_materiality": {k: counts.get(k, 0) for k in ("high", "medium", "low")},
        },
        "rollups": rollups,
        "changes": changes,
    }


def describe(change):
    kind = change["change_type"]
    label = change["item_label"]
    field = change.get("field")
    before, after, detail = change.get("before"), change.get("after"), change.get("detail")

    if kind == "item_added":
        return f"**{label}** added — {detail}"
    if kind == "item_removed":
        return f"**{label}** no longer present — {detail}"
    if kind == "renamed":
        return f"**{before}** renamed to **{after}** ({detail})"
    if kind == "text_changed":
        added = "; ".join(change.get("added_text", []))[:400]
        removed = "; ".join(change.get("removed_text", []))[:400]
        parts = [f"**{label}** wording changed (similarity {change.get('similarity')})"]
        if added:
            parts.append(f"now says: {added}")
        if removed:
            parts.append(f"previously said: {removed}")
        return " — ".join(parts)
    suffix = f" ({detail})" if detail else ""
    return f"**{label}** · {field}: {before} → {after}{suffix}"


def render_md(brief):
    lines = ["# Change brief", ""]
    periods = {
        (d["previous_period"], d["current_period"]) for d in brief["documents"]
    }
    if len(periods) == 1:
        prev, curr = periods.pop()
        lines.append(f"Comparing **{prev}** with **{curr}**.")
    else:
        lines.append("⚠️ Documents cover different periods — check the inputs pair up:")
        for d in brief["documents"]:
            lines.append(f"- {d['document']}: {d['previous_period']} → {d['current_period']}")
    totals = brief["totals"]["by_materiality"]
    lines += [
        "",
        f"{brief['totals']['changes']} changes across {len(brief['documents'])} documents "
        f"— {totals['high']} high, {totals['medium']} medium, {totals['low']} low.",
        "",
        "Sources:",
    ]
    for d in brief["documents"]:
        lines.append(f"- `{d['document']}` (.{d['doc_type']}) — {d['summary']['changes_total']} changes")

    if brief["rollups"]:
        lines += ["", "## Roll-ups", ""]
        for roll in brief["rollups"]:
            values = sorted(set(roll["before"]) | set(roll["after"]))
            moved = [
                f"{v or '(blank)'} {roll['before'].get(v, 0)}→{roll['after'].get(v, 0)}"
                for v in values
                if roll["before"].get(v, 0) != roll["after"].get(v, 0)
            ]
            if not moved:
                continue
            lines.append(
                f"- `{roll['document']}` · **{roll['field']}** "
                f"(n {roll['population_before']}→{roll['population_after']}): "
                + ", ".join(moved)
            )

    for key, title, _ in GROUPS:
        group = [c for c in brief["changes"] if c["group"] == key]
        if not group:
            continue
        lines += ["", f"## {title}", ""]
        for change in group:
            flag = {"high": "🔴", "medium": "🟠", "low": "⚪"}[change["materiality"]]
            note = f" _(follows {change['subsumed_by']})_" if change.get("subsumed_by") else ""
            lines.append(
                f"- `[{change['change_id']}]` {flag} {describe(change)}{note}  \n"
                f"  <sub>{change['document']} · {change['source_ref'].get('current') or ''}</sub>"
            )

    lines += [
        "",
        "---",
        "",
        "Write the spoken update from this file. Cite `[C#]` on every claim, and mark any "
        "framing that is your own read rather than a change in the documents with "
        "`[JUDGEMENT]`. Deliberately leaving something out is fine — record it as "
        "`<!-- omit: C# reason -->` so the QA stage can tell an omission from an oversight.",
        "",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("changes", nargs="+", help="one or more changes.json from diff_snapshots.py")
    ap.add_argument("-o", "--out", required=True, help="merged change_brief.json")
    ap.add_argument("--md", help="also write the readable brief here")
    args = ap.parse_args()

    brief = merge(args.changes)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(brief, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.md:
        Path(args.md).write_text(render_md(brief), encoding="utf-8")
    t = brief["totals"]
    print(
        f"{args.out}: {t['changes']} changes from {len(brief['documents'])} documents "
        f"({t['by_materiality']['high']} high, {t['by_materiality']['medium']} medium)"
    )


if __name__ == "__main__":
    main()
