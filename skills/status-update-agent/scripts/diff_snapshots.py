#!/usr/bin/env python3
"""Stage 2: compare last week's snapshot with this week's.

    python diff_snapshots.py prev.json curr.json -o changes.json

Produces one record per change, each with a stable `change_id` (C1, C2, …). Those IDs are
the spine of the rest of the run: the narrative cites them, and the QA stage checks that
nothing material was dropped and nothing was claimed that isn't here.

Matching runs in two passes. First on `item_id`. Then unmatched leftovers of the same kind
are paired on label/text similarity, so a renamed activity or a re-titled slide reads as
one rename rather than a deletion plus an unrelated addition.

Materiality is assigned by rule, not by judgement — see reference/materiality-rules.md.
`--print-rules` dumps the defaults as JSON; edit and pass back with `--rules` to fit a
programme's own vocabulary (status ladders, RAG words, thresholds).
"""

import argparse
import difflib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_RULES = {
    "status_ladder": [
        "not started", "backlog", "on hold", "blocked", "planned", "scoped",
        "in progress", "in build", "wip", "drafted", "in review", "in test",
        "testing", "uat", "complete", "completed", "done", "signed off", "closed",
    ],
    "rag_ladder": ["red", "amber", "yellow", "green", "blue"],
    "field_classes": {
        "status": ["status", "state", "stage", "progress status"],
        "rag": ["rag", "health", "flag", "confidence"],
        "percent": ["%", "percent", "complete %", "completion"],
        "date": ["date", "due", "deadline", "eta", "go-live", "start", "finish"],
        "owner": ["owner", "lead", "responsible", "accountable", "assignee"],
    },
    "percent_thresholds": {"high": 25, "medium": 10},
    "text_similarity": {"material_below": 0.90, "rename_match_above": 0.72},
    "materiality": {
        "item_added": "medium",
        "item_removed": "high",
        "renamed": "low",
        "owner_changed": "medium",
        "date_slip": "high",
        "date_pull_in": "medium",
        "status_forward": "medium",
        "status_backward": "high",
        "rag_worse": "high",
        "rag_better": "medium",
        "number_changed": "medium",
        "other_field": "low",
    },
}

RANK = {"high": 0, "medium": 1, "low": 2}


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def norm(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def classify_field(name, rules):
    low = name.lower()
    for cls, hints in rules["field_classes"].items():
        if any(h in low for h in hints):
            return cls
    return "other"


def ladder_pos(value, ladder):
    low = norm(value).lower()
    for i, rung in enumerate(ladder):
        if low == rung:
            return i
    for i, rung in enumerate(ladder):
        if rung in low:
            return i
    return None


def as_number(value):
    m = re.search(r"-?\d+(?:\.\d+)?", norm(value).replace(",", ""))
    return float(m.group()) if m else None


DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d %b %Y", "%d %B %Y", "%b %d, %Y"]


def as_date(value):
    text = norm(value)
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def field_change(field, before, after, rules):
    """One field moved. Say what kind of movement it was and how much it matters."""
    cls = classify_field(field, rules)
    mat = rules["materiality"]
    detail, kind, level = None, f"{cls}_changed", mat["other_field"]

    if cls == "status":
        a, b = ladder_pos(before, rules["status_ladder"]), ladder_pos(after, rules["status_ladder"])
        if a is not None and b is not None and a != b:
            forward = b > a
            kind = "status_forward" if forward else "status_backward"
            level = mat[kind]
            detail = "advanced" if forward else "regressed"
        else:
            kind, level = "status_changed", mat["status_forward"]
    elif cls == "rag":
        a, b = ladder_pos(before, rules["rag_ladder"]), ladder_pos(after, rules["rag_ladder"])
        if a is not None and b is not None and a != b:
            better = b > a
            kind = "rag_better" if better else "rag_worse"
            level = mat[kind]
            detail = "improved" if better else "deteriorated"
    elif cls == "date":
        a, b = as_date(before), as_date(after)
        if a and b and a != b:
            days = (b - a).days
            kind = "date_slip" if days > 0 else "date_pull_in"
            level = mat[kind]
            detail = f"{abs(days)} day {'slip' if days > 0 else 'pull-in'}"
    elif cls == "percent":
        a, b = as_number(before), as_number(after)
        if a is not None and b is not None:
            delta = b - a
            th = rules["percent_thresholds"]
            level = (
                "high" if abs(delta) >= th["high"]
                else "medium" if abs(delta) >= th["medium"]
                else "low"
            )
            kind = "percent_changed"
            detail = f"{delta:+g}"
    elif cls == "owner":
        kind, level = "owner_changed", mat["owner_changed"]

    if kind == "other_changed":
        a, b = as_number(before), as_number(after)
        if a is not None and b is not None and a != b:
            kind, level = "number_changed", mat["number_changed"]
            detail = f"{b - a:+g}"

    return {
        "change_type": kind,
        "field": field,
        "before": before,
        "after": after,
        "detail": detail,
        "materiality": level,
    }


def text_change(before, after, rules):
    ratio = difflib.SequenceMatcher(None, before, after).ratio()
    sm_before = re.split(r"(?<=[.!?])\s+", before)
    sm_after = re.split(r"(?<=[.!?])\s+", after)
    diff = list(difflib.ndiff(sm_before, sm_after))
    added = [d[2:] for d in diff if d.startswith("+ ") and norm(d[2:])]
    removed = [d[2:] for d in diff if d.startswith("- ") and norm(d[2:])]
    # A number moving inside otherwise-identical prose is exactly the kind of change a
    # similarity score hides, so it overrides the score.
    numbers_before = re.findall(r"-?\d+(?:\.\d+)?", before)
    numbers_after = re.findall(r"-?\d+(?:\.\d+)?", after)
    numbers_moved = numbers_before != numbers_after
    level = "medium" if (ratio < rules["text_similarity"]["material_below"] or numbers_moved) else "low"
    return {
        "change_type": "text_changed",
        "similarity": round(ratio, 3),
        "added_text": added,
        "removed_text": removed,
        "numbers_moved": numbers_moved,
        "materiality": level,
    }


def pair_leftovers(prev_only, curr_only, rules):
    """Second-pass matching: same kind, similar label+text, best-first, one-to-one."""
    threshold = rules["text_similarity"]["rename_match_above"]
    candidates = []
    for pid, p in prev_only.items():
        for cid, c in curr_only.items():
            if p["kind"] != c["kind"]:
                continue
            score = difflib.SequenceMatcher(
                None,
                f"{p['label']} {p.get('text', '')}".lower(),
                f"{c['label']} {c.get('text', '')}".lower(),
            ).ratio()
            if score >= threshold:
                candidates.append((score, pid, cid))
    candidates.sort(reverse=True)
    pairs, used_p, used_c = [], set(), set()
    for score, pid, cid in candidates:
        if pid in used_p or cid in used_c:
            continue
        used_p.add(pid)
        used_c.add(cid)
        pairs.append((pid, cid, round(score, 3)))
    return pairs


def rollups(prev_items, curr_items, rules):
    """Counts per status/RAG value, per field, so the narrative can quote a movement
    rather than a list of seven individual rows."""
    def tally(items):
        out = {}
        for item in items.values():
            for field, value in item.get("fields", {}).items():
                if classify_field(field, rules) in ("status", "rag"):
                    out.setdefault(field, {})
                    key = norm(value)
                    out[field][key] = out[field].get(key, 0) + 1
        return out

    before, after = tally(prev_items), tally(curr_items)
    out = []
    for field in sorted(set(before) | set(after)):
        b, a = before.get(field, {}), after.get(field, {})
        values = sorted(set(b) | set(a))
        out.append(
            {
                "field": field,
                "before": {v: b.get(v, 0) for v in values},
                "after": {v: a.get(v, 0) for v in values},
                "population_before": sum(b.values()),
                "population_after": sum(a.values()),
            }
        )
    return out


def diff(prev, curr, rules):
    prev_items = {i["item_id"]: i for i in prev["items"]}
    curr_items = {i["item_id"]: i for i in curr["items"]}
    changes, counter = [], 0

    def add(record, item, prev_item=None):
        nonlocal counter
        counter += 1
        record["change_id"] = f"C{counter}"
        record["item_id"] = item["item_id"]
        record["item_label"] = item["label"]
        record["item_kind"] = item["kind"]
        record["source_ref"] = {
            "previous": (prev_item or {}).get("source_ref"),
            "current": item.get("source_ref"),
        }
        changes.append(record)

    def compare(p, c):
        for field in sorted(set(p.get("fields", {})) | set(c.get("fields", {}))):
            before, after = p.get("fields", {}).get(field, ""), c.get("fields", {}).get(field, "")
            if norm(before) != norm(after):
                if not before:
                    add({"change_type": "field_added", "field": field, "before": "", "after": after,
                         "detail": None, "materiality": "low"}, c, p)
                elif not after:
                    add({"change_type": "field_removed", "field": field, "before": before, "after": "",
                         "detail": None, "materiality": "medium"}, c, p)
                else:
                    add(field_change(field, before, after, rules), c, p)
        if norm(p.get("text", "")) != norm(c.get("text", "")):
            add(text_change(norm(p.get("text", "")), norm(c.get("text", "")), rules), c, p)

    for item_id, c in curr_items.items():
        if item_id in prev_items:
            compare(prev_items[item_id], c)

    prev_only = {k: v for k, v in prev_items.items() if k not in curr_items}
    curr_only = {k: v for k, v in curr_items.items() if k not in prev_items}

    for pid, cid, score in pair_leftovers(prev_only, curr_only, rules):
        p, c = prev_only.pop(pid), curr_only.pop(cid)
        if norm(p["label"]) != norm(c["label"]):
            add({"change_type": "renamed", "before": p["label"], "after": c["label"],
                 "detail": f"matched at {score} similarity", "materiality":
                 rules["materiality"]["renamed"]}, c, p)
        compare(p, c)

    for item in curr_only.values():
        add({"change_type": "item_added", "before": None, "after": item["label"],
             "detail": item.get("text") or "; ".join(f"{k}: {v}" for k, v in item.get("fields", {}).items()),
             "materiality": rules["materiality"]["item_added"]}, item)
    for item in prev_only.values():
        add({"change_type": "item_removed", "before": item["label"], "after": None,
             "detail": "present last period, absent this period",
             "materiality": rules["materiality"]["item_removed"]}, item)

    subsume(changes)
    changes.sort(key=lambda ch: (RANK[ch["materiality"]], int(ch["change_id"][1:])))

    counts = {}
    for ch in changes:
        counts[ch["materiality"]] = counts.get(ch["materiality"], 0) + 1

    return {
        "comparison": {
            "previous": prev["document"],
            "current": curr["document"],
            "generated_at": now(),
        },
        "summary": {
            "items_previous": len(prev_items),
            "items_current": len(curr_items),
            "changes_total": len(changes),
            "by_materiality": {k: counts.get(k, 0) for k in ("high", "medium", "low")},
        },
        "rollups": rollups(prev_items, curr_items, rules),
        "changes": changes,
    }


def subsume(changes):
    """A completion percentage jumping to 100 in the same week the status went to
    'Complete' is one piece of news, not two. Keep the status change as the headline and
    mark the percentage as following from it, so the narrative doesn't say it twice."""
    by_item = {}
    for ch in changes:
        by_item.setdefault(ch["item_id"], []).append(ch)
    for item_changes in by_item.values():
        status = next(
            (c for c in item_changes if c["change_type"].startswith("status_")), None
        )
        if not status:
            continue
        for ch in item_changes:
            if ch["change_type"] == "percent_changed":
                ch["subsumed_by"] = status["change_id"]
                ch["materiality"] = "low"


def load_rules(path):
    if not path:
        return DEFAULT_RULES
    rules = json.loads(Path(path).read_text(encoding="utf-8"))
    merged = json.loads(json.dumps(DEFAULT_RULES))
    for key, value in rules.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("previous", nargs="?", help="last period's snapshot.json")
    ap.add_argument("current", nargs="?", help="this period's snapshot.json")
    ap.add_argument("--rules", help="JSON file of rule overrides")
    ap.add_argument("--print-rules", action="store_true", help="print default rules and exit")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()

    if args.print_rules:
        print(json.dumps(DEFAULT_RULES, indent=2))
        return
    if not (args.previous and args.current):
        ap.error("previous and current snapshots are both required")

    prev = json.loads(Path(args.previous).read_text(encoding="utf-8"))
    curr = json.loads(Path(args.current).read_text(encoding="utf-8"))
    if prev["document"]["doc_type"] != curr["document"]["doc_type"]:
        print(
            f"warning: comparing a .{prev['document']['doc_type']} with a "
            f".{curr['document']['doc_type']} — check these are the same report",
            file=sys.stderr,
        )

    result = diff(prev, curr, load_rules(args.rules))
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        s = result["summary"]
        print(
            f"{args.out}: {s['changes_total']} changes "
            f"({s['by_materiality']['high']} high, {s['by_materiality']['medium']} medium, "
            f"{s['by_materiality']['low']} low)",
            file=sys.stderr,
        )
    else:
        print(text)


if __name__ == "__main__":
    main()
