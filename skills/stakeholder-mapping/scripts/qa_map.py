#!/usr/bin/env python3
"""Stage 4 (QA): audit a stakeholder_map.json before anyone opens the viewer.

Hard failures exit 1 (the map is not safe to show); warnings exit 0 and become the agenda
for the next interview round.

    python qa_map.py stakeholder_map.json -o qa_report.md
    python qa_map.py map_shared.json --key pseudonym_key.json     # also hunts for leaked names
    python qa_map.py stakeholder_map.json --sources ingested/sources.json

Hard:    unit_uncovered, dangling_reference, informal_no_evidence, pseudonym_leak
Warning: hearsay_high_confidence, no_sentiment_evidence, expected_group_missing,
         isolated_group, open_conflict, unknown_source
"""

import argparse
import json
import re
import sys
from pathlib import Path

LENSES = Path(__file__).resolve().parents[1] / "reference" / "industry_lenses.json"
ALIAS = re.compile(r"^Person-\d+$")


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def _item(code, message):
    return {"code": code, "message": message}


def load_lenses():
    return json.loads(LENSES.read_text(encoding="utf-8"))["lenses"]


def pick_lens(context, lenses):
    text = _norm(f"{context.get('industry', '')} {context.get('business_model', '')}")
    for name, lens in lenses.items():
        if any(k in text for k in lens["match"]):
            return name, lens
    return None, None


def audit(m, key=None, sources=None, lenses=None):
    hard, warn = [], []
    meta = m.get("meta", {})
    ctx = meta.get("org_context", {})
    groups, people, rels = m.get("groups", []), m.get("individuals", []), m.get("relationships", [])
    evidence = {e["id"]: e for e in m.get("evidence", [])}
    nodes = {i["id"]: i for i in groups + people}

    # Q1: every unit on the org chart is represented
    covered = set()
    for g in groups:
        covered |= {_norm(g.get("name")), _norm(g.get("business_unit"))}
        covered |= {_norm(u) for u in g.get("org_units", [])}
    for unit in ctx.get("org_chart_units", []):
        if _norm(unit) not in covered:
            hard.append(_item("unit_uncovered", f"Org chart unit '{unit}' has no stakeholder group "
                              "(add a group, or list it under an existing group's org_units)."))

    # reference integrity and the informal-evidence rule, re-checked for hand-edited maps
    for r in rels:
        for end in ("from", "to"):
            if r.get(end) not in nodes:
                hard.append(_item("dangling_reference", f"Relationship {r.get('id')}: {end} "
                                  f"'{r.get(end)}' is not a group or individual."))
        for ref in r.get("evidence", []):
            if ref not in evidence:
                hard.append(_item("dangling_reference", f"Relationship {r.get('id')} cites missing evidence {ref}."))
        if r.get("kind") == "informal" and not r.get("evidence"):
            hard.append(_item("informal_no_evidence", f"Informal relationship {r.get('id')} "
                              f"({r.get('from')} -> {r.get('to')}) has no evidence."))
    for coll in groups + people:
        for ref in coll.get("evidence", []):
            if ref not in evidence:
                hard.append(_item("dangling_reference", f"{coll.get('id')} cites missing evidence {ref}."))

    # Q2: pseudonymisation holds
    if meta.get("pseudonymised"):
        for p in people:
            if not ALIAS.match(p.get("name", "")):
                hard.append(_item("pseudonym_leak", f"Individual {p.get('id')} still carries a real-looking "
                                  f"name '{p.get('name')}' in a pseudonymised map."))
        if key:
            text = json.dumps(m, ensure_ascii=False).lower()
            names = set()
            for v in key.values():
                for n in [v.get("name", "")] + v.get("aliases", []):
                    if n:
                        names.add(n.lower())
                        names |= {t.lower() for t in re.findall(r"[A-Za-z']{3,}", n)}
            for n in sorted(names):
                if re.search(r"(?<![a-z])" + re.escape(n) + r"(?![a-z])", text):
                    hard.append(_item("pseudonym_leak", f"'{n}' from the pseudonym key appears in the map."))

    # Q3: hearsay holding up a confident informal tie
    for r in rels:
        if r.get("kind") == "informal" and r.get("confidence") == "High" and r.get("evidence"):
            if all(evidence.get(e, {}).get("attribution") == "hearsay" for e in r["evidence"]):
                warn.append(_item("hearsay_high_confidence", f"Relationship {r['id']} is rated High confidence "
                                  "but rests only on hearsay: corroborate or downgrade."))

    # Q4: sentiment with nothing behind it
    for g in groups:
        if g.get("sentiment", "Unknown") == "Unknown" or not g.get("evidence"):
            warn.append(_item("no_sentiment_evidence", f"Group {g['id']} ({g.get('name')}) has no evidence "
                              "behind its sentiment: ask directly in the next interview."))

    # Q5: groups this kind of organisation usually has but nobody has mentioned
    lenses = lenses or load_lenses()
    lens_name, lens = pick_lens(ctx, lenses)
    if lens:
        for exp in lens["expected_groups"]:
            hay = " ".join(_norm(f"{g.get('name')} {g.get('business_unit')} {' '.join(g.get('org_units', []))} "
                                 f"{g.get('summary', '')}") for g in groups)
            if not any(k in hay for k in exp["keywords"]):
                warn.append(_item("expected_group_missing", f"{lens_name} lens: no group looks like "
                                  f"'{exp['label']}'. {exp['why']} Probe: {exp['probe']}"))

    # Q6: groups with no relationships at all
    linked = {r["from"] for r in rels} | {r["to"] for r in rels}
    for g in groups:
        if g["id"] not in linked:
            warn.append(_item("isolated_group", f"Group {g['id']} ({g.get('name')}) has no relationships."))

    for c in meta.get("conflicts", []) or [c for i in groups + people for c in i.get("conflicts", [])]:
        warn.append(_item("open_conflict", f"{c.get('item', '')} {c.get('field')}: "
                          f"{c.get('previous')} vs {c.get('new')} is unresolved."))

    if sources is not None:
        known = {s.get("id") for s in sources}
        for e in evidence.values():
            if e.get("source") not in known:
                warn.append(_item("unknown_source", f"Evidence {e['id']} cites source '{e.get('source')}' "
                                  "which is not in the sources manifest."))
    return {"hard": hard, "warnings": warn, "lens": lens_name}


def render(report, path):
    h, w = report["hard"], report["warnings"]
    lines = [f"# Stakeholder map QA: {'FAIL' if h else 'PASS'}", "",
             f"Industry lens: {report['lens'] or 'none matched'}", "",
             f"{len(h)} hard failure(s), {len(w)} warning(s).", ""]
    if h:
        lines += ["## Hard failures (fix before showing this map)", ""] + [f"- `{x['code']}`: {x['message']}" for x in h] + [""]
    if w:
        lines += ["## Warnings (the agenda for the next interview round)", ""] + [f"- `{x['code']}`: {x['message']}" for x in w] + [""]
    if not h and not w:
        lines += ["Nothing to report."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("map")
    ap.add_argument("-o", "--output")
    ap.add_argument("--key", help="pseudonym key, to hunt for leaked names")
    ap.add_argument("--sources", help="ingest sources.json, to check evidence source refs")
    a = ap.parse_args(argv)
    load = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
    report = audit(load(a.map), key=load(a.key) if a.key else None,
                   sources=load(a.sources) if a.sources else None)
    text = render(report, a.output)
    if a.output:
        Path(a.output).write_text(text, encoding="utf-8")
    else:
        print(text)
    print(f"qa_map: {'FAIL' if report['hard'] else 'PASS'} "
          f"({len(report['hard'])} hard, {len(report['warnings'])} warnings)", file=sys.stderr)
    return 1 if report["hard"] else 0


if __name__ == "__main__":
    sys.exit(main())
