#!/usr/bin/env python3
"""Stage 3 (BUILD): extraction.json + context.json -> stakeholder_map.json.

Deterministic, standard library only. Everything the model *decides* happens before this
script (grouping, relationship type, sentiment, ONA role); everything here is mechanical:
validation, de-duplication of people, merging a re-run into a previous map, contradiction
flagging, network metrics, and optional pseudonymisation.

    python build_map.py extraction.json context.json -o stakeholder_map.json
    python build_map.py extraction.json context.json -o map.json --merge previous_map.json
    python build_map.py extraction.json context.json -o map_shared.json --pseudonymise \
        --key-out pseudonym_key.json

Nothing is written when validation fails; every error is printed.
"""

import argparse
import copy
import datetime
import json
import re
import sys
from collections import deque
from pathlib import Path

SCHEMA_VERSION = 1
SENTIMENTS = ("Advocate", "Neutral", "Skeptic", "Unknown")
ONA_ROLES = ("Central Connector", "Broker", "Peripheral", "Energiser", "De-energiser")
CONFIDENCE = ("High", "Medium", "Low")
ATTRIBUTIONS = ("testimony", "claim", "hearsay", "document")
FORMAL_TYPES = ("reports_to", "approves", "hands_off_to", "escalates_to", "governs")
INFORMAL_TYPES = ("consults", "trusts", "influences", "bypasses", "conflicts_with", "gatekeeps")
MAX_TIER = 5  # 0 = executive ... 4 = frontline, 5 = external party

COMPUTED = ("metrics", "last_updated")
REF_KEYS = ("id", "from", "to", "group", "evidence", "source", "item", "kept", "dropped")


class MapError(Exception):
    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("\n".join(self.errors))


# --------------------------------------------------------------------------- names

def _name_parts(name):
    """-> (surname, [given tokens]) from 'Tan, Ah Kow', 'A.K. Tan' or 'Ah Kow Tan'."""
    if "," in name:
        last, first = name.split(",", 1)
        given = re.findall(r"[A-Za-z']+", first)
        sur = re.findall(r"[A-Za-z']+", last)
        return (sur[-1].lower() if sur else ""), given
    toks = re.findall(r"[A-Za-z']+", name)
    if not toks:
        return "", []
    return toks[-1].lower(), toks[:-1]


def same_person(a, b):
    """Conservative: same group, same surname, compatible given names, no conflicting title."""
    if a["group"] != b["group"]:
        return False
    if a.get("title") and b.get("title") and a["title"].strip().lower() != b["title"].strip().lower():
        return False
    sa, ga = _name_parts(a["name"])
    sb, gb = _name_parts(b["name"])
    if not sa or sa != sb or len(ga) != len(gb) or not ga:
        return False
    for x, y in zip(ga, gb):
        if x[0].lower() != y[0].lower():
            return False
        if len(x) > 1 and len(y) > 1 and x.lower() != y.lower():
            return False
    return True


def dedupe_individuals(ex):
    kept, log, remap = [], [], {}
    for p in ex["individuals"]:
        twin = next((k for k in kept if same_person(k, p)), None)
        if twin is None:
            kept.append(p)
            continue
        remap[p["id"]] = twin["id"]
        names = [twin["name"]] + twin.get("aliases", [])
        if p["name"] not in names:
            twin["aliases"] = twin.get("aliases", []) + [p["name"]]
        for a in p.get("aliases", []):
            if a not in twin.get("aliases", []) and a != twin["name"]:
                twin.setdefault("aliases", []).append(a)
        twin["evidence"] = _union(twin.get("evidence", []), p.get("evidence", []))
        for k, v in p.items():
            if k not in twin or twin[k] in ("", None, [], "Unknown"):
                twin[k] = v
        log.append({"kept": twin["id"], "dropped": p["id"], "names": [twin["name"], p["name"]]})
    ex["individuals"] = kept
    for r in ex["relationships"]:
        r["from"] = remap.get(r["from"], r["from"])
        r["to"] = remap.get(r["to"], r["to"])
    return log


# ------------------------------------------------------------------------ helpers

def _union(a, b):
    out = list(a)
    out.extend(x for x in b if x not in out)
    return out


def _empty(v):
    return v in ("", None, [], {})


def _strip(item):
    return {k: v for k, v in item.items() if k not in COMPUTED}


def _norm_extraction(ex):
    ex = copy.deepcopy(ex)
    for k in ("groups", "individuals", "relationships", "evidence"):
        ex.setdefault(k, [])
    for g in ex["groups"]:
        g.setdefault("sentiment", "Unknown")
        g.setdefault("influence", 3)
        g.setdefault("interest", 3)
        g.setdefault("confidence", "Medium")
        g.setdefault("evidence", [])
    for p in ex["individuals"]:
        p.setdefault("sentiment", "Unknown")
        p.setdefault("influence", 3)
        p.setdefault("confidence", "Medium")
        p.setdefault("evidence", [])
    for r in ex["relationships"]:
        r.setdefault("strength", 1)
        r.setdefault("confidence", "Medium")
        r.setdefault("evidence", [])
    return ex


# -------------------------------------------------------------------------- merge

def merge_with_previous(prev, new, as_of):
    """Overlay a new extraction on a previous map's items, flagging contradictions.

    Previous items keep their order (and so their ids); new items are appended. For an id in
    both, scalars from the new side win, evidence is unioned, and a changed sentiment (or
    relationship type) is recorded as a conflict and drops the item to Low confidence. The
    incoming side never sets `confidence` or `conflicts`: those are derived here.
    """
    out = {}
    for coll in ("groups", "individuals", "relationships"):
        old = [_strip(i) for i in prev.get(coll, [])]
        for i in old:
            i.pop("metrics", None)
        incoming = {i["id"]: i for i in new[coll]}
        merged = []
        for o in old:
            n = incoming.pop(o["id"], None)
            if n is None:
                merged.append(o)
                continue
            m = dict(o)
            for k, v in n.items():
                if k == "evidence":
                    m["evidence"] = _union(o.get("evidence", []), v)
                elif k in ("confidence", "conflicts"):
                    continue
                elif not _empty(v):
                    m[k] = v
            field = "type" if coll == "relationships" else "sentiment"
            nv, ov = n.get(field), o.get(field)
            if nv and ov and nv != ov and "Unknown" not in (nv, ov):
                m["conflicts"] = list(o.get("conflicts", [])) + [
                    {"field": field, "previous": ov, "new": nv, "as_of": as_of,
                     "evidence": list(n.get("evidence", []))}]
            if m.get("conflicts"):
                m["confidence"] = "Low"
            merged.append(m)
        out[coll] = merged + list(incoming.values())
    ev = {e["id"]: e for e in prev.get("evidence", [])}
    for e in new["evidence"]:
        ev[e["id"]] = e
    out["evidence"] = list(ev.values())
    return out


# ---------------------------------------------------------------------- validation

def validate(ex):
    errs = []
    if not ex["groups"]:
        errs.append("The extraction has no groups: nothing to map.")
    node_ids, seen = {}, set()
    for coll, label in (("groups", "group"), ("individuals", "individual")):
        for i in ex[coll]:
            iid = i.get("id")
            if not iid:
                errs.append(f"A {label} has no id.")
                continue
            if iid in seen:
                errs.append(f"Duplicate id {iid}.")
            seen.add(iid)
            node_ids[iid] = label
            if not i.get("name"):
                errs.append(f"{label} {iid} has no name.")
    ev_ids = set()
    for e in ex["evidence"]:
        if e.get("id") in ev_ids:
            errs.append(f"Duplicate evidence id {e.get('id')}.")
        ev_ids.add(e.get("id"))
        if e.get("attribution") not in ATTRIBUTIONS:
            errs.append(f"Evidence {e.get('id')}: attribution {e.get('attribution')!r} is not one of {ATTRIBUTIONS}.")
        if not e.get("source"):
            errs.append(f"Evidence {e.get('id')} has no source.")

    def check_ev(owner, refs):
        for r in refs:
            if r not in ev_ids:
                errs.append(f"{owner} cites evidence {r}, which does not exist.")

    for g in ex["groups"]:
        gid = g.get("id")
        if not isinstance(g.get("tier"), int) or not 0 <= g["tier"] <= MAX_TIER:
            errs.append(f"group {gid}: tier must be an integer 0-{MAX_TIER}, got {g.get('tier')!r}.")
        if g["sentiment"] not in SENTIMENTS:
            errs.append(f"group {gid}: sentiment {g['sentiment']!r} is not one of {SENTIMENTS}.")
        if g.get("ona_role") and g["ona_role"] not in ONA_ROLES:
            errs.append(f"group {gid}: ona_role {g['ona_role']!r} is not one of {ONA_ROLES}.")
        for f in ("influence", "interest"):
            if not isinstance(g[f], int) or not 1 <= g[f] <= 5:
                errs.append(f"group {gid}: {f} must be 1-5, got {g[f]!r}.")
        if g["confidence"] not in CONFIDENCE:
            errs.append(f"group {gid}: confidence {g['confidence']!r} is not one of {CONFIDENCE}.")
        check_ev(f"group {gid}", g["evidence"])
    for p in ex["individuals"]:
        pid = p.get("id")
        if p.get("group") not in {g["id"] for g in ex["groups"]}:
            errs.append(f"individual {pid}: group {p.get('group')} does not exist.")
        if p["sentiment"] not in SENTIMENTS:
            errs.append(f"individual {pid}: sentiment {p['sentiment']!r} is not one of {SENTIMENTS}.")
        if p.get("ona_role") and p["ona_role"] not in ONA_ROLES:
            errs.append(f"individual {pid}: ona_role {p['ona_role']!r} is not one of {ONA_ROLES}.")
        check_ev(f"individual {pid}", p["evidence"])
    rel_ids = set()
    for r in ex["relationships"]:
        rid = r.get("id")
        if rid in rel_ids:
            errs.append(f"Duplicate relationship id {rid}.")
        rel_ids.add(rid)
        for end in ("from", "to"):
            if r.get(end) not in node_ids:
                errs.append(f"relationship {rid}: {end} {r.get(end)!r} is not a group or individual in the extraction.")
        if r.get("from") == r.get("to"):
            errs.append(f"relationship {rid}: connects {r.get('from')} to itself.")
        kind = r.get("kind")
        if kind not in ("formal", "informal"):
            errs.append(f"relationship {rid}: kind {kind!r} must be 'formal' or 'informal'.")
        else:
            allowed = FORMAL_TYPES if kind == "formal" else INFORMAL_TYPES
            if r.get("type") not in allowed:
                errs.append(f"relationship {rid}: type {r.get('type')!r} is not a {kind} type {allowed}.")
        if r["strength"] not in (1, 2, 3):
            errs.append(f"relationship {rid}: strength must be 1, 2 or 3, got {r['strength']!r}.")
        if r["confidence"] not in CONFIDENCE:
            errs.append(f"relationship {rid}: confidence {r['confidence']!r} is not one of {CONFIDENCE}.")
        if kind == "informal" and not r["evidence"]:
            errs.append(f"relationship {rid}: an informal relationship must cite evidence (none given).")
        check_ev(f"relationship {rid}", r["evidence"])
    return errs


# ----------------------------------------------------------------------- metrics

def _betweenness(ids, rels):
    adj = {i: set() for i in ids}
    for r in rels:
        a, b = r["from"], r["to"]
        if a in adj and b in adj and a != b:
            adj[a].add(b)
            adj[b].add(a)
    n = len(ids)
    bc = {i: 0.0 for i in ids}
    for s in ids:
        stack, preds = [], {i: [] for i in ids}
        sigma = {i: 0 for i in ids}
        sigma[s] = 1
        dist = {i: -1 for i in ids}
        dist[s] = 0
        q = deque([s])
        while q:
            v = q.popleft()
            stack.append(v)
            for w in adj[v]:
                if dist[w] < 0:
                    dist[w] = dist[v] + 1
                    q.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    preds[w].append(v)
        delta = {i: 0.0 for i in ids}
        while stack:
            w = stack.pop()
            for v in preds[w]:
                delta[v] += sigma[v] / sigma[w] * (1 + delta[w])
            if w != s:
                bc[w] += delta[w]
    scale = ((n - 1) * (n - 2)) if n > 2 else 0  # undirected: each pair counted twice
    return {i: (bc[i] / scale if scale else 0.0) for i in ids}


def compute_metrics(nodes, rels):
    """Degree and Brandes betweenness (unweighted, undirected, normalised 0-1).

    `betweenness` uses every tie. `informal_betweenness` uses informal ties only, so a formal
    hub (the root of the reporting tree) is not mistaken for an informal broker.
    """
    ids = [n["id"] for n in nodes]
    adj = {i: set() for i in ids}
    formal = {i: 0 for i in ids}
    informal = {i: 0 for i in ids}
    for r in rels:
        a, b = r["from"], r["to"]
        if a in adj and b in adj and a != b:
            adj[a].add(b)
            adj[b].add(a)
            bucket = formal if r["kind"] == "formal" else informal
            bucket[a] += 1
            bucket[b] += 1
    n = len(ids)
    bc = _betweenness(ids, rels)
    ibc = _betweenness(ids, [r for r in rels if r["kind"] == "informal"])
    has_informal = any(r["kind"] == "informal" for r in rels)
    out = {}
    for i in ids:
        degree = len(adj[i])
        b = bc[i]
        # Once the map has any informal ties, only a node with an informal tie can be suggested
        # as a broker or connector; otherwise the root of the reporting tree always wins.
        eligible = informal[i] > 0 or not has_informal
        if eligible and b >= 0.25:
            role = "Broker"
        elif eligible and n >= 4 and degree / (n - 1) >= 0.5:
            role = "Central Connector"
        elif degree <= 1:
            role = "Peripheral"
        else:
            role = None
        out[i] = {"degree": degree, "formal_degree": formal[i], "informal_degree": informal[i],
                  "betweenness": round(b, 4), "informal_betweenness": round(ibc[i], 4),
                  "suggested_ona_role": role}
    return out


# ---------------------------------------------------------------- pseudonymisation

def apply_pseudonyms(m, individuals_before):
    """Rewrite names and individual ids; return (map, key). Key is private to the practitioner."""
    people = sorted(individuals_before, key=lambda p: p["id"])
    key, idmap, variants = {}, {}, {}
    for n, p in enumerate(people, 1):
        alias = f"Person-{n:02d}"
        idmap[p["id"]] = alias
        key[alias] = {"id": p["id"], "name": p["name"], "aliases": p.get("aliases", [])}
        for v in [p["name"]] + p.get("aliases", []):
            variants.setdefault(v.lower(), set()).add(alias)
            for t in re.findall(r"[A-Za-z']{3,}", v):
                variants.setdefault(t.lower(), set()).add(alias)
    repl = {v: (next(iter(a)) if len(a) == 1 else "[name]") for v, a in variants.items()}
    pattern = re.compile(r"(?<![A-Za-z])(" + "|".join(
        re.escape(v) for v in sorted(repl, key=len, reverse=True)) + r")(?![A-Za-z])", re.I) if repl else None

    def scrub(s):
        return pattern.sub(lambda mo: repl[mo.group(1).lower()], s) if pattern else s

    def walk(o, ref=False):
        if isinstance(o, str):
            return o if ref else scrub(o)
        if isinstance(o, list):
            return [walk(x, ref) for x in o]
        if isinstance(o, dict):
            return {k: walk(v, k in REF_KEYS) for k, v in o.items()}
        return o

    m = walk(m)
    for p in m["individuals"]:
        alias = idmap[p["id"]]
        p["id"] = alias
        p["name"] = alias
        p.pop("aliases", None)

    def fix(v):
        return idmap.get(v, v)

    for r in m["relationships"]:
        r["from"], r["to"] = fix(r["from"]), fix(r["to"])
    m["meta"]["merged_individuals"] = []  # the log carries real names
    for c in m["meta"].get("conflicts", []):
        c["item"] = fix(c["item"])
    m["meta"]["pseudonymised"] = True
    return m, key


# -------------------------------------------------------------------------- build

def build(extraction, context, pseudonymise=False, previous=None, as_of=None):
    """-> (map, pseudonym_key). Raises MapError listing every problem found."""
    as_of = as_of or datetime.date.today().isoformat()
    ex = _norm_extraction(extraction)
    prev_items = {}
    if previous is not None:
        if previous.get("meta", {}).get("pseudonymised"):
            raise MapError(["--merge needs the original (un-pseudonymised) map as the previous map; "
                            "pseudonymise only the copy that goes to the viewer."])
        for coll in ("groups", "individuals", "relationships"):
            prev_items[coll] = {i["id"]: _strip(i) for i in previous.get(coll, [])}
            for i in prev_items[coll].values():
                i.pop("metrics", None)
        ex = merge_with_previous(previous, ex, as_of)
    merged_log = dedupe_individuals(ex)
    errors = validate(ex)
    if errors:
        raise MapError(errors)

    nodes = ex["groups"] + ex["individuals"]
    metrics = compute_metrics(nodes, ex["relationships"])
    for coll in ("groups", "individuals", "relationships"):
        for item in ex[coll]:
            if coll != "relationships":
                item["metrics"] = metrics[item["id"]]
            old = prev_items.get(coll, {}).get(item["id"])
            same = old is not None and _strip({k: v for k, v in item.items() if k != "metrics"}) == old
            item["last_updated"] = (previous_item_date(previous, coll, item["id"]) if same else as_of)
    conflicts = [{"item": i["id"], **c} for coll in ("groups", "individuals", "relationships")
                 for i in ex[coll] for c in i.get("conflicts", [])]
    meta = {
        "schema_version": SCHEMA_VERSION,
        "client": context.get("client", ""),
        "programme": context.get("programme", ""),
        "as_of": as_of,
        "org_context": copy.deepcopy(context),
        "sources": (previous or {}).get("meta", {}).get("sources", []),
        "pseudonymised": False,
        "merged_individuals": merged_log,
        "conflicts": conflicts,
    }
    m = {"meta": meta, "groups": ex["groups"], "individuals": ex["individuals"],
         "relationships": ex["relationships"], "evidence": ex["evidence"]}
    key = {}
    if pseudonymise:
        m, key = apply_pseudonyms(m, ex["individuals"])
    return m, key


def previous_item_date(previous, coll, item_id):
    for i in (previous or {}).get(coll, []):
        if i["id"] == item_id:
            return i.get("last_updated")
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("extraction")
    ap.add_argument("context")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--merge", metavar="PREVIOUS_MAP")
    ap.add_argument("--pseudonymise", action="store_true")
    ap.add_argument("--key-out", metavar="FILE", help="where to write the pseudonym key (keep private)")
    ap.add_argument("--sources", metavar="SOURCES_JSON", help="ingest manifest to carry into meta.sources")
    ap.add_argument("--as-of")
    a = ap.parse_args(argv)
    load = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
    previous = load(a.merge) if a.merge else None
    try:
        m, key = build(load(a.extraction), load(a.context), a.pseudonymise, previous, a.as_of)
    except MapError as e:
        print(f"build_map: {len(e.errors)} problem(s), nothing written:", file=sys.stderr)
        for line in e.errors:
            print(f"  - {line}", file=sys.stderr)
        return 1
    if a.sources:
        m["meta"]["sources"] = load(a.sources)
    Path(a.output).write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if a.pseudonymise:
        if a.key_out:
            Path(a.key_out).write_text(json.dumps(key, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        else:
            print("build_map: no --key-out given; the pseudonym key was discarded and cannot be recovered.",
                  file=sys.stderr)
    print(f"build_map: wrote {a.output} ({len(m['groups'])} groups, {len(m['individuals'])} individuals, "
          f"{len(m['relationships'])} relationships)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
