#!/usr/bin/env python3
"""
Publish a change impact assessment to Airtable as a live, relational workspace.

    export AIRTABLE_PAT=pat_xxx
    python3 push_to_airtable.py cia_input.json --check
    python3 push_to_airtable.py cia_input.json --base-id appXXXX --dry-run
    python3 push_to_airtable.py cia_input.json --base-id appXXXX --create
    python3 push_to_airtable.py cia_input.json --base-id appXXXX          # re-sync

This is not a port of the workbook. Airtable is relational, so the assessment gets a
shape the spreadsheet could not have:

  * **Two linked tables.** `Sources` holds the documents; `Change Impacts` links to them.
    Open a source and you see every impact derived from it — traceability that works in
    both directions, where the workbook's Traceability sheet only counted one way.
  * **Views replace sheets.** Training plan, comms plan, open questions and the
    stakeholder heatmap are filters and groupings over one table, not four copies of the
    data that can drift apart.
  * **Re-running syncs rather than duplicates.** Records upsert on Impact ID, so the JSON
    stays the master: edit it, re-run, and the base updates in place.

Standard library only — no dependencies.

`Overall Impact` and `Rating` are created as **formula fields**, so the score recalculates
live when someone re-scores a dimension in a validation workshop — the same behaviour the
workbook has. Verified against a live base. If a token or API version ever rejects the
formula type, the script falls back to a written value and says so.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import Counter

API = "https://api.airtable.com/v0"
BATCH = 10          # Airtable's per-request record limit
RATE_PAUSE = 0.25   # 5 requests/second/base; stay comfortably under

IMPACTS_TABLE = "Change Impacts"
SOURCES_TABLE = "Sources"

OVERALL_FORMULA = (
    "IF(AND({People (0-3)} != BLANK(), {Process (0-3)} != BLANK(), "
    "{Technology (0-3)} != BLANK()), "
    "ROUND(({People (0-3)} + {Process (0-3)} + {Technology (0-3)}) / 3, 2), BLANK())"
)
RATING_FORMULA = (
    'IF({Overall Impact} = BLANK(), "", '
    'IF({Overall Impact} >= 2.5, "High", '
    'IF({Overall Impact} >= 1.5, "Medium", '
    'IF({Overall Impact} >= 0.5, "Low", "No / Minimal"))))'
)


# --------------------------------------------------------------------------------------
# Schema — mirrors reference/input-schema.md, in Airtable's field vocabulary
# --------------------------------------------------------------------------------------

def sel(*names_colors):
    return {"choices": [{"name": n, "color": c} for n, c in names_colors]}


SCORE_CHOICES = sel(("0", "grayLight2"), ("1", "greenLight2"),
                    ("2", "yellowLight2"), ("3", "orangeLight2"))

SOURCES_FIELDS = [
    {"name": "Ref", "type": "singleLineText"},
    {"name": "Type", "type": "singleLineText"},
    {"name": "Title", "type": "multilineText"},
    {"name": "Date", "type": "singleLineText"},
    {"name": "Author / Participants", "type": "multilineText"},
]

# (airtable field name, type, options, json key)
IMPACT_FIELDS = [
    ("Impact ID", "singleLineText", None, "impact_id"),
    ("L1", "singleLineText", None, "l1"),
    ("L1 Code", "number", {"precision": 0}, "l1_code"),
    ("L2", "singleLineText", None, "l2"),
    ("L2 Code", "number", {"precision": 0}, "l2_code"),
    ("L3", "singleLineText", None, "l3"),
    ("L3 Code", "number", {"precision": 0}, "l3_code"),
    ("L4", "singleLineText", None, "l4"),
    ("L4 Code", "number", {"precision": 0}, "l4_code"),
    ("Stakeholder Group", "singleLineText", None, "stakeholder_group"),
    ("Current Roles", "multilineText", None, "current_roles"),
    ("Approx Headcount", "number", {"precision": 0}, "headcount_impacted"),
    ("As-Is", "multilineText", None, "as_is"),
    ("To-Be", "multilineText", None, "to_be"),
    ("People Impact", "multilineText", None, "people_impact"),
    ("People (0-3)", "number", {"precision": 0}, "score_people"),
    ("Process Impact", "multilineText", None, "process_impact"),
    ("Process (0-3)", "number", {"precision": 0}, "score_process"),
    ("Technology Impact", "multilineText", None, "tech_impact"),
    ("Technology (0-3)", "number", {"precision": 0}, "score_technology"),
    ("Anticipated Resistance", "singleSelect",
     sel(("Low", "greenLight2"), ("Medium", "yellowLight2"), ("High", "orangeLight2")),
     "resistance_risk"),
    ("Benefit / WIIFM", "multilineText", None, "benefit_narrative"),
    ("Other Impacts", "multilineText", None, "other_impacts"),
    ("Mitigation Actions", "multilineText", None, "mitigation_actions"),
    ("Training Required", "singleSelect", sel(("Yes", "greenLight2"), ("No", "grayLight2")),
     "training_required"),
    ("Training Method", "singleSelect",
     sel(("Classroom ILT", "blueLight2"), ("Virtual ILT", "cyanLight2"),
         ("e-Learning", "tealLight2"), ("Job Aid", "greenLight2"),
         ("In-App Guidance", "yellowLight2"), ("Floorwalking / Hypercare", "orangeLight2"),
         ("Webinar", "purpleLight2"), ("Not Required", "grayLight2")), "training_type"),
    ("Training Module Ref", "singleLineText", None, "training_module_ref"),
    ("Training Duration (hrs)", "number", {"precision": 2}, "training_duration_hrs"),
    ("Training Audience", "number", {"precision": 0}, "training_audience_size"),
    ("Training Timing", "singleLineText", None, "training_timing"),
    ("Comms Required", "singleSelect", sel(("Yes", "greenLight2"), ("No", "grayLight2")),
     "comms_required"),
    ("Key Message", "multilineText", None, "key_message"),
    ("Comms Channel", "multilineText", None, "comms_channel"),
    ("Comms Timing", "singleLineText", None, "comms_timing"),
    ("Comms Owner", "multilineText", None, "comms_owner"),
    ("Change Champion", "multilineText", None, "change_champion"),
    ("Confidence", "singleSelect",
     sel(("High", "greenLight2"), ("Medium", "yellowLight2"), ("Low", "redLight2")),
     "confidence"),
    ("Validation Status", "singleSelect",
     sel(("Draft", "grayLight2"), ("In Review", "yellowLight2"),
         ("Validated", "greenLight2"), ("Baselined", "blueLight2")), "validation_status"),
    ("Source Ref", "singleLineText", None, "source_ref"),
    ("Notes / Open Questions", "multilineText", None, "notes"),
]

COMPUTED = {"Overall Impact", "Rating"}
LINK_FIELD = "Sources"

# Added after the table exists, so the formulas can reference fields by name.
# Formula first; if the API rejects the type, fall back to a written value.
COMPUTED_SPECS = [
    ("Overall Impact",
     {"name": "Overall Impact", "type": "formula",
      "description": "Unweighted average of the three dimension scores, per the client "
                     "CIA template.",
      "options": {"formula": OVERALL_FORMULA}},
     {"name": "Overall Impact", "type": "number", "options": {"precision": 2}}),
    ("Rating",
     {"name": "Rating", "type": "formula",
      "description": "Band on the 0-3 average. High >= 2.50, Medium 1.50-2.49, "
                     "Low 0.50-1.49, No/Minimal < 0.50. These cut-offs are an assumption of "
                     "the assessment method, not the client template, which defines only the "
                     "per-dimension scale. Confirm before baselining.",
      "options": {"formula": RATING_FORMULA}},
     {"name": "Rating", "type": "singleSelect",
      "options": sel(("No / Minimal", "grayLight2"), ("Low", "greenLight2"),
                     ("Medium", "yellowLight2"), ("High", "orangeLight2"))}),
]

VIEWS_TO_CREATE = [
    ("Impact Register", "All impacts. Group by Stakeholder Group or L1 to read the heatmap."),
    ("Training Plan", "Filter: Training Required = Yes. Group by Training Method."),
    ("Comms Plan", "Filter: Comms Required = Yes. Group by Comms Timing."),
    ("Open Questions", "Filter: Confidence = Low, or Notes is not empty."),
    ("High Impact", "Filter: Rating = High. Sort by Anticipated Resistance descending."),
]


# --------------------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------------------

class AirtableError(Exception):
    pass


def request(method, url, token, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read().decode()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:600]
        raise AirtableError(explain_http(e.code, detail)) from None
    except urllib.error.URLError as e:
        raise AirtableError(
            f"Could not reach api.airtable.com ({e.reason}).\n"
            "      If you are on a corporate network, this host may be blocked by policy — "
            "that is a network decision, not a broken token."
        ) from None


def explain_http(code, detail):
    """Airtable's errors are terse; the fix usually depends on a PAT scope."""
    hints = {
        401: "Token rejected. Check AIRTABLE_PAT is a current personal access token.",
        403: ("Authorised but not permitted. The usual cause is a missing PAT scope or the "
              "base not being added to the token.\n"
              "      Needed: schema.bases:read, schema.bases:write, data.records:read, "
              "data.records:write\n"
              "      And the token must list this base under its access."),
        404: "Not found. Check the base ID (starts `app`) and that the token can see it.",
        422: ("Airtable rejected the payload — usually a field name or select option that "
              "does not exist on the table."),
        429: "Rate limited. Re-run; the script paces itself but a shared base can still trip it.",
    }
    head = hints.get(code, f"HTTP {code}.")
    return f"{head}\n      Airtable said: {detail}"


# --------------------------------------------------------------------------------------
# Value mapping
# --------------------------------------------------------------------------------------

def average_score(imp):
    try:
        return round((imp["score_people"] + imp["score_process"]
                      + imp["score_technology"]) / 3, 2)
    except (KeyError, TypeError):
        return None


def rating_for(imp):
    if imp.get("rating_override"):
        return imp["rating_override"]
    s = average_score(imp)
    if s is None:
        return None
    for lo, label in ((2.5, "High"), (1.5, "Medium"), (0.5, "Low"), (0.0, "No / Minimal")):
        if s >= lo:
            return label
    return "No / Minimal"


def split_refs(value):
    if not value:
        return []
    return [p.split("@")[0].strip()
            for p in str(value).replace(",", ";").split(";") if p.split("@")[0].strip()]


def build_impact_fields(imp, source_ids, skip=()):
    """Map one impact onto Airtable field names, omitting blanks and computed fields."""
    out = {}
    for name, _type, _opts, key in IMPACT_FIELDS:
        if name in skip:
            continue
        if name == "Overall Impact":
            v = average_score(imp)
        elif name == "Rating":
            v = rating_for(imp)
        else:
            v = imp.get(key)
            if name == "Training Audience" and v in (None, ""):
                v = imp.get("headcount_impacted")
            if name == "Validation Status" and not v:
                v = "Draft"
        if v is None or (isinstance(v, str) and not v.strip()):
            continue
        out[name] = v

    linked = [source_ids[r] for r in split_refs(imp.get("source_ref")) if r in source_ids]
    if linked:
        out[LINK_FIELD] = linked
    return out


def chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


# --------------------------------------------------------------------------------------
# Operations
# --------------------------------------------------------------------------------------

def cmd_check(token):
    print("\n  Airtable connection\n  " + "─" * 58)
    try:
        who = request("GET", f"{API}/meta/whoami", token)
    except AirtableError as e:
        print(f"\n  ✗ {e}\n")
        return 1
    print(f"\n  ✓ token valid — user {who.get('id')}")
    scopes = who.get("scopes")
    if scopes:
        need = {"schema.bases:read", "schema.bases:write",
                "data.records:read", "data.records:write"}
        have = set(scopes)
        print(f"    scopes: {', '.join(sorted(have))}")
        missing = need - have
        if missing:
            print(f"    ✗ missing: {', '.join(sorted(missing))}")
            print("      Add them to the token at airtable.com/create/tokens")
        else:
            print("    ✓ all required scopes present")

    try:
        bases = request("GET", f"{API}/meta/bases", token).get("bases", [])
    except AirtableError as e:
        print(f"\n  ✗ could not list bases: {e}\n")
        return 1
    print(f"\n  Bases this token can see ({len(bases)}):")
    for b in bases[:25]:
        print(f"    {b['id']}   {b.get('name')}")
    if not bases:
        print("    (none — add a base to the token's access list)")
    print("\n  Then:  push_to_airtable.py <input.json> --base-id <appXXXX> --create\n")
    return 0


def get_tables(base_id, token):
    return request("GET", f"{API}/meta/bases/{base_id}/tables", token).get("tables", [])


def impact_base_fields():
    """The non-computed fields. Link and formula fields are added once the table exists."""
    out = []
    for name, ftype, opts, _k in IMPACT_FIELDS:
        f = {"name": name, "type": ftype}
        if opts:
            f["options"] = opts
        out.append(f)
    return out


def finalise_impacts_table(base_id, impacts_id, sources_id, token, existing_names):
    """Add the link to Sources and the two formula fields."""
    if LINK_FIELD not in existing_names:
        request("POST", f"{API}/meta/bases/{base_id}/tables/{impacts_id}/fields", token, {
            "name": LINK_FIELD, "type": "multipleRecordLinks",
            "description": "The documents this impact was derived from. Open a source to see "
                           "every impact traced to it.",
            "options": {"linkedTableId": sources_id},
        })
        print(f"    ✓ {LINK_FIELD:18} link to {SOURCES_TABLE}")
        time.sleep(RATE_PAUSE)
    return add_computed_fields(base_id, impacts_id, token, existing_names)


def create_base_with_tables(workspace_id, name, token):
    """
    Create a new base holding just this assessment.

    Airtable cannot move a table between bases, so 'moving' an assessment means creating
    it fresh here and re-syncing from the JSON. That is lossless precisely because the
    JSON is the master — unless someone has already edited in the old base, in which case
    export those edits first.
    """
    res = request("POST", f"{API}/meta/bases", token, {
        "name": name,
        "workspaceId": workspace_id,
        "tables": [
            {"name": SOURCES_TABLE,
             "description": "Documents each impact was derived from. Linked from "
                            f"{IMPACTS_TABLE}, so opening a source shows every impact "
                            "traced to it.",
             "fields": SOURCES_FIELDS},
            {"name": IMPACTS_TABLE,
             "description": "Baseline change impact assessment. One record per process "
                            "change x stakeholder group. Scored 0-3 on People, Process and "
                            "Technology; Overall Impact is the unweighted average.",
             "fields": impact_base_fields()},
        ],
    })
    by_name = {t["name"]: t for t in res.get("tables", [])}
    print(f"    ✓ base `{name}` created ({res['id']})")
    for n in (SOURCES_TABLE, IMPACTS_TABLE):
        print(f"      {n:18} {by_name[n]['id']}")
    time.sleep(RATE_PAUSE)
    return res["id"], by_name


def create_tables(base_id, token, existing):
    by_name = {t["name"]: t for t in existing}
    created = {}
    formulas = set()

    if SOURCES_TABLE in by_name:
        print(f"    · {SOURCES_TABLE:18} already exists — reusing")
        created[SOURCES_TABLE] = by_name[SOURCES_TABLE]
    else:
        t = request("POST", f"{API}/meta/bases/{base_id}/tables", token, {
            "name": SOURCES_TABLE,
            "description": "Documents the assessment was derived from. Each impact links here.",
            "fields": SOURCES_FIELDS,
        })
        print(f"    ✓ {SOURCES_TABLE:18} created ({t['id']})")
        created[SOURCES_TABLE] = t
        time.sleep(RATE_PAUSE)

    if IMPACTS_TABLE in by_name:
        print(f"    · {IMPACTS_TABLE:18} already exists — reusing")
        created[IMPACTS_TABLE] = by_name[IMPACTS_TABLE]
        # Self-healing: a table made by hand, or by an older version of this script, may be
        # missing the link or the formula fields. finalise_ adds only what is absent.
        formulas = finalise_impacts_table(
            base_id, by_name[IMPACTS_TABLE]["id"], created[SOURCES_TABLE]["id"], token,
            {f["name"] for f in by_name[IMPACTS_TABLE].get("fields", [])})
    else:
        fields = impact_base_fields()
        t = request("POST", f"{API}/meta/bases/{base_id}/tables", token, {
            "name": IMPACTS_TABLE,
            "description": "Baseline change impact assessment. One row per process change "
                           "x stakeholder group.",
            "fields": fields,
        })
        print(f"    ✓ {IMPACTS_TABLE:18} created ({t['id']}) with {len(fields)} fields")
        created[IMPACTS_TABLE] = t
        time.sleep(RATE_PAUSE)
        formulas = finalise_impacts_table(base_id, t["id"], created[SOURCES_TABLE]["id"],
                                          token, {f["name"] for f in t.get("fields", [])})

    return created, formulas


def add_computed_fields(base_id, table_id, token, existing_names):
    """
    Add Overall Impact and Rating as formula fields.

    Verified against a live base: the API does accept type `formula`, so these come out
    live and the script never writes to them. If a future API version or a restricted
    token rejects it, fall back to a plain number/select that the script populates —
    correct either way, just not self-updating.
    """
    formulas = set()
    for name, formula_spec, fallback_spec in COMPUTED_SPECS:
        if name in existing_names:
            continue
        try:
            f = request("POST", f"{API}/meta/bases/{base_id}/tables/{table_id}/fields",
                        token, formula_spec)
            valid = f.get("options", {}).get("isValid", True)
            print(f"    ✓ {name:18} formula field" + ("" if valid else "  ⚠ formula invalid"))
            if valid:
                formulas.add(name)
        except AirtableError:
            request("POST", f"{API}/meta/bases/{base_id}/tables/{table_id}/fields",
                    token, fallback_spec)
            print(f"    · {name:18} formula rejected — created as a written value instead")
        time.sleep(RATE_PAUSE)
    return formulas


def upsert(base_id, table, token, records, merge_on):
    """PATCH with performUpsert — idempotent, so re-running syncs instead of duplicating."""
    done = 0
    ids = {}
    for batch in chunked(records, BATCH):
        res = request("PATCH", f"{API}/{base_id}/{table['id']}", token, {
            "performUpsert": {"fieldsToMergeOn": [merge_on]},
            "records": [{"fields": f} for f in batch],
            "typecast": True,
        })
        for rec in res.get("records", []):
            key = rec.get("fields", {}).get(merge_on)
            if key:
                ids[key] = rec["id"]
        done += len(batch)
        print(f"      {done}/{len(records)} records", flush=True)
        time.sleep(RATE_PAUSE)
    return ids


def formula_fields_present(table):
    return {f["name"] for f in table.get("fields", []) if f.get("type") == "formula"}


# --------------------------------------------------------------------------------------

def cmd_dry_run(data):
    impacts = data["impacts"]
    sources = data["meta"].get("source_documents", [])
    print("\n  Dry run — nothing will be sent\n  " + "─" * 58)
    print(f"\n  Would create 2 tables in the target base:\n")
    print(f"    {SOURCES_TABLE:18} {len(SOURCES_FIELDS)} fields, {len(sources)} records")
    print(f"    {IMPACTS_TABLE:18} {len(IMPACT_FIELDS) + 1} fields "
          f"(incl. link to {SOURCES_TABLE}), {len(impacts)} records")

    print(f"\n  {IMPACTS_TABLE} field types:")
    kinds = Counter(t for _n, t, _o, _k in IMPACT_FIELDS)
    for k, n in kinds.most_common():
        print(f"    {n:3}  {k}")
    print(f"      1  multipleRecordLinks  ({LINK_FIELD})")

    source_ids = {s["ref"]: f"recFAKE{i:04d}" for i, s in enumerate(sources)}
    print(f"\n  First record as it would be sent:\n")
    sample = build_impact_fields(impacts[0], source_ids)
    for k, v in list(sample.items())[:10]:
        txt = str(v)
        print(f"    {k:26} {txt[:64]}{'…' if len(txt) > 64 else ''}")
    print(f"    … {len(sample) - 10} more fields")

    ratings = Counter(rating_for(i) for i in impacts)
    print(f"\n  Computed ratings: " + "  ".join(f"{k}: {v}" for k, v in ratings.items()))
    unresolved = {r for i in impacts for r in split_refs(i.get("source_ref"))} - set(source_ids)
    print(f"  Source links: {len(source_ids)} sources"
          + (f"  ⚠ unresolved refs: {sorted(unresolved)}" if unresolved else ", all refs resolve"))
    print("\n  Re-runs upsert on `Impact ID`, so this is safe to run repeatedly.\n")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Publish a change impact assessment to Airtable as a live workspace.")
    ap.add_argument("input", nargs="?", help="cia_input.json")
    ap.add_argument("--base-id", help="Target base, e.g. appXXXXXXXXXXXXXX")
    ap.add_argument("--check", action="store_true", help="Verify token, scopes and bases")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be sent")
    ap.add_argument("--create", action="store_true", help="Create the tables if absent")
    ap.add_argument("--create-base", metavar="NAME",
                    help="Create a NEW base of this name holding just this assessment. "
                         "Use to move an assessment out of a cluttered base — Airtable "
                         "cannot move tables, so this recreates and re-syncs from the JSON.")
    ap.add_argument("--workspace-id", metavar="wspXXXX",
                    help="Workspace for --create-base. Take it from the Airtable URL: "
                         "airtable.com/<wspXXXX>/...")
    ap.add_argument("--token-env", default="AIRTABLE_PAT",
                    help="Env var holding the personal access token (default AIRTABLE_PAT)")
    args = ap.parse_args()

    token = os.environ.get(args.token_env) or os.environ.get("AIRTABLE_API_KEY")
    if not token and not args.dry_run:
        print(f"\n✗ No token. Create a personal access token at "
              f"https://airtable.com/create/tokens with scopes:")
        print("    schema.bases:read  schema.bases:write  data.records:read  data.records:write")
        print(f"  then:  export {args.token_env}=pat_xxx\n")
        print("  Never paste a token into a chat — keep it in the environment.\n")
        return 1

    if args.check:
        return cmd_check(token)

    if not args.input:
        ap.print_help()
        return 1
    with open(args.input, encoding="utf-8") as fh:
        data = json.load(fh)
    if not data.get("impacts"):
        print("✗ No impacts in the input file.")
        return 1

    if args.dry_run:
        return cmd_dry_run(data)

    if args.create_base and not args.workspace_id:
        print("✗ --create-base also needs --workspace-id (the wspXXXX in your Airtable URL).")
        return 1
    if not args.base_id and not args.create_base:
        print("✗ --base-id is required, or --create-base NAME --workspace-id wspXXXX to "
              "start a new one.\n  Run --check to list the bases your token can see.")
        return 1

    impacts = data["impacts"]
    sources = data["meta"].get("source_documents", [])
    created_formulas = set()

    try:
        if args.create_base:
            print(f"\n  New base in workspace {args.workspace_id}")
            args.base_id, tables = create_base_with_tables(
                args.workspace_id, args.create_base, token)
            created_formulas = finalise_impacts_table(
                args.base_id, tables[IMPACTS_TABLE]["id"],
                tables[SOURCES_TABLE]["id"], token, set())
        else:
            print(f"\n  → base {args.base_id}")
            existing = {t["name"]: t for t in get_tables(args.base_id, token)}
            if args.create:
                print("\n  Tables")
                tables, created_formulas = create_tables(
                    args.base_id, token, list(existing.values()))
            else:
                missing = [n for n in (SOURCES_TABLE, IMPACTS_TABLE) if n not in existing]
                if missing:
                    print(f"\n✗ Missing table(s): {', '.join(missing)}. "
                          f"Re-run with --create.\n")
                    return 1
                tables = {n: existing[n] for n in (SOURCES_TABLE, IMPACTS_TABLE)}

        print("\n  Sources")
        src_records = [{"Ref": s.get("ref"), "Type": s.get("type", ""),
                        "Title": s.get("title", ""), "Date": s.get("date", ""),
                        "Author / Participants": s.get("author_or_participants", "")}
                       for s in sources if s.get("ref")]
        source_ids = upsert(args.base_id, tables[SOURCES_TABLE], token, src_records, "Ref") \
            if src_records else {}

        # A formula field cannot be written to; if the user converted it, respect that.
        fresh = {t["name"]: t for t in get_tables(args.base_id, token)}
        computed = (formula_fields_present(fresh.get(IMPACTS_TABLE, {})) | created_formulas) \
            & COMPUTED
        if computed:
            print(f"\n  {', '.join(sorted(computed))} is a formula field — leaving it to Airtable")

        print("\n  Impacts")
        recs = [build_impact_fields(i, source_ids, skip=computed) for i in impacts]
        upsert(args.base_id, tables[IMPACTS_TABLE], token, recs, "Impact ID")

    except AirtableError as e:
        print(f"\n  ✗ {e}\n")
        return 1

    url = f"https://airtable.com/{args.base_id}"
    print(f"\n  ✓ {len(impacts)} impacts and {len(src_records)} sources synced")
    print(f"    {url}\n")

    if computed:
        print(f"  {', '.join(sorted(computed))} recalculate live — re-scoring a dimension in "
              f"a workshop\n  updates the rating without a re-run.\n")
    else:
        print("  Overall Impact / Rating hold written values rather than formulas. To make "
              "them live,\n  change each to a Formula field in the UI:")
        print(f"    Overall Impact:  {OVERALL_FORMULA}")
        print(f"    Rating:          {RATING_FORMULA}")
        print("  Re-runs then leave both to Airtable.\n")

    print("  Views worth adding (each is a filter over the one table, not a copy):")
    for name, how in VIEWS_TO_CREATE:
        print(f"    {name:18} {how}")
    print("\n  Edit the JSON and re-run to sync — records upsert on Impact ID.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
