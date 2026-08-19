#!/usr/bin/env python3
"""Pull the Airtable half of the knowledge bank into a file index_kb.py can merge.

    export AIRTABLE_TOKEN=pat...
    python sync_airtable.py -o airtable_entries.json
    python index_kb.py proposal-assets/knowledge-bank \\
        --merge airtable_entries.json -o proposals/<run>/kb_index.json

`CM Knowledge Bank -> Content Library` holds reusable prose; the Markdown folders hold the
rest. Retrieval must not be able to tell them apart, so this writes the same field names
`build_record()` reads and lets `index_kb.py` do the validating. Two validators drift.

Without this, `retrieve.py` cannot see a single Airtable row: the intake page reads the
table live through the viewer's connector, the pipeline reads Markdown, and the two rank
different banks. That gap is what this closes.

`--fetch-attachments` additionally downloads past-bid **decks** from
`Proposals and Tenders`, so `ingest_source.py` has something local to extract. Tenders are
skipped unless asked for: an RFP is the client's document, not ours to mine.

Stdlib only, like every other script here. Airtable's REST API is plain JSON over HTTPS.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_ROOT = "https://api.airtable.com/v0"
TOKEN_ENV = "AIRTABLE_TOKEN"

BASE_ID = "appAi9h5mT0hPz5o2"
CONTENT_LIBRARY = "tblf1nFLP3p30Fg3S"
PROPOSALS_AND_TENDERS = "tblxQyGlAV81vz3ES"

# Field ids, not field names. A column renamed in the Airtable UI keeps its id, so the
# bank survives a rename; matching on names would empty it silently instead.
# Mirrors LIBRARY.field in tools/bid-intake-desk/index.src.html.
LIBRARY_FIELD = {
    "title":     "fldcEZJuXYRIFIqNv",
    "entry_id":  "fld2m3EQm558160ke",
    "section":   "fldbSZfbXGqpslVJT",
    "content":   "fldcYvk92SVj2PBAj",
    "tags":      "fldL5nPnkyJnwORhJ",
    "clearance": "fldqNYERgJLcny0DO",
    "reviewed":  "fldXwxfBJ9rOiWZsg",
    "verified":  "fldbX9JRc3DDKUfYN",
    "owner":     "fldvFL7gfs6SfdF0m",
    "outcome":   "fldTo1GfrCgUuBUbG",
}

# Mirrors AIRTABLE.field in the same file.
REGISTER_FIELD = {
    "name":     "fld2pcQSSx8pxXaGi",
    "location": "fldAICNuwryB6il5R",
    "rfp":      "fld9cmwu4nuBkQnuS",
    "deck":     "fldXrhDwayxbGplBC",
    "price":    "fldW3eQtJ67m8wt56",
}


# --- cell readers ----------------------------------------------------------
#
# Airtable encodes a cell differently per field type, and differently again depending on
# how it is read: the REST API returns a singleSelect as a plain string, while the MCP
# connector returns {id, name, color} for the same cell. Read both tolerantly rather than
# asserting one shape — a wrong assertion yields a blank cell, which is indistinguishable
# from missing data. Ports of cellText/cellNames/cellFiles in index.src.html.


def cell_text(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return ""
    if isinstance(value, (str, int, float)):
        return str(value)
    if isinstance(value, list):
        return ", ".join(t for t in (cell_text(v) for v in value) if t)
    if isinstance(value, dict):
        for key in ("name", "text", "value", "filename"):
            if value.get(key):
                return str(value[key])
    return ""


def cell_names(value):
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        name = item.get("name") if isinstance(item, dict) else item
        if name:
            out.append(str(name))
    return out


def cell_files(value):
    if not isinstance(value, list):
        return []
    return [{"name": a.get("filename") or a.get("name") or "attachment",
             "url": a.get("url")}
            for a in value if isinstance(a, dict)]


# --- fetching --------------------------------------------------------------


def token_or_exit():
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        sys.exit(
            f"{TOKEN_ENV} is not set.\n"
            "  Create a read-only personal access token at "
            "https://airtable.com/create/tokens with scopes\n"
            "  data.records:read and schema.bases:read, granted to the CM Knowledge Bank "
            "base, then:\n"
            f"      export {TOKEN_ENV}=pat...\n"
            "  It is read from the environment and never accepted as a flag, so it stays "
            "out of shell history."
        )
    return token


def fetch_records(base, table, token):
    """Every record in a table, following Airtable's offset pagination.

    returnFieldsByFieldId keeps the response keyed the way LIBRARY_FIELD expects.
    """
    records, offset = [], None
    while True:
        query = {"returnFieldsByFieldId": "true", "pageSize": "100"}
        if offset:
            query["offset"] = offset
        url = f"{API_ROOT}/{base}/{table}?{urllib.parse.urlencode(query)}"
        request = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })
        try:
            with urllib.request.urlopen(request) as response:
                page = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            hint = {
                401: "  The token was rejected — check it is current and not revoked.",
                403: "  The token is valid but lacks access — grant it the CM Knowledge "
                     "Bank base and the data.records:read scope.",
                404: f"  No such base/table: {base}/{table}.",
                422: "  Airtable rejected the request parameters.",
            }.get(exc.code, "")
            sys.exit(f"Airtable returned HTTP {exc.code}.\n{hint}\n  {detail}".rstrip())
        except urllib.error.URLError as exc:
            sys.exit(f"Could not reach Airtable: {exc.reason}")

        records += page.get("records", [])
        offset = page.get("offset")
        if not offset:
            return records


def load_saved(path):
    """A saved API response, for working offline or debugging without spending calls.

    Accepts a single response object, a bare list of records, or a list of response
    pages — whichever form somebody happened to save.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data.get("records", [])
    if isinstance(data, list):
        if data and isinstance(data[0], dict) and "records" in data[0]:
            return [r for page in data for r in page.get("records", [])]
        return data
    sys.exit(f"{path} is not an Airtable response or a list of records")


# --- mapping ---------------------------------------------------------------


def entry_from(record):
    """One Content Library row in the field names build_record() reads.

    A port of entryFrom() in the intake page, with three deliberate differences the
    merge contract requires — see the module notes and the comments below.
    """
    cells = record.get("fields") or record.get("cellValuesByFieldId") or {}
    get = lambda key: cells.get(LIBRARY_FIELD[key])  # noqa: E731

    reviewed = cell_text(get("reviewed"))
    # The full Content cell, not a truncated excerpt: build_record() derives both excerpt
    # and word_count from `body`, so sending the page's 300-char excerpt would index every
    # entry as empty and nought words long.
    body = cell_text(get("content"))

    entry = {
        "id": cell_text(get("entry_id")) or record.get("id"),
        "title": cell_text(get("title")) or "Untitled entry",
        "section": cell_text(get("section")),
        "tags": [t.lower() for t in cell_names(get("tags"))],
        # Airtable's API cannot set a default on a single select, so a blank Clearance is
        # read as the most restrictive value. Always sent explicitly: build_record()
        # defaults an absent clearance to "anonymised", which would leave the pipeline
        # quietly more permissive than the page for exactly the rows nobody finished.
        "clearance": cell_text(get("clearance")) or "internal-only",
        "metrics_verified": get("verified") is True,
        "last_reviewed": reviewed or None,
        "owner": cell_text(get("owner")) or None,
        "body": body,
        "record_url": f"https://airtable.com/{BASE_ID}/{CONTENT_LIBRARY}/{record.get('id')}",
    }

    # Only when there is an outcome to carry. build_record() warns about a bid block with
    # no outcome, and most entries — boilerplate, team bios — never came from a bid at all.
    outcome = cell_text(get("outcome"))
    if outcome:
        entry["bid"] = {"outcome": outcome}
    return entry


def incomplete_reasons(entry):
    """What would stop this row being retrievable, in the page's own words.

    index_kb.py remains the validator; this only lets the operator see it coming.
    """
    return [label for missing, label in (
        (not entry["section"], "Section"),
        (not entry["tags"], "Tags"),
        (not entry["body"], "Content"),
        (not entry["last_reviewed"], "Last reviewed"),
    ) if missing]


# --- attachments -----------------------------------------------------------


def safe_name(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "attachment"


def download_attachments(records, out_dir, token, include_rfp):
    """Past-bid decks onto disk, so ingest_source.py has a local file to read.

    Attachment URLs are pre-signed and short-lived (a couple of hours), so they are
    fetched now rather than recorded for later. The token is not sent with them — these
    are signed URLs, and Airtable rejects the pair.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    wanted = ["deck"] + (["rfp"] if include_rfp else [])
    saved, failed = [], []

    for record in records:
        cells = record.get("fields") or record.get("cellValuesByFieldId") or {}
        project = cell_text(cells.get(REGISTER_FIELD["name"])) or record.get("id")
        for kind in wanted:
            for attachment in cell_files(cells.get(REGISTER_FIELD[kind])):
                if not attachment["url"]:
                    failed.append(f"{project}: {attachment['name']} has no download link")
                    continue
                target = out_dir / f"{safe_name(project)}--{safe_name(attachment['name'])}"
                try:
                    with urllib.request.urlopen(attachment["url"]) as response:
                        target.write_bytes(response.read())
                except (urllib.error.HTTPError, urllib.error.URLError) as exc:
                    reason = getattr(exc, "reason", exc)
                    failed.append(f"{project}: {attachment['name']} — {reason}")
                    continue
                saved.append((kind, target))
    return saved, failed


# --- main ------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", type=Path, default=Path("airtable_entries.json"),
                    help="merge file to write (default: airtable_entries.json)")
    ap.add_argument("--base", default=BASE_ID, help=f"base id (default: {BASE_ID})")
    ap.add_argument("--table", default=CONTENT_LIBRARY,
                    help=f"Content Library table id (default: {CONTENT_LIBRARY})")
    ap.add_argument("--from-file", type=Path, metavar="FILE",
                    help="read a saved API response instead of calling Airtable — for "
                         "working offline, or debugging a mapping without spending calls")
    ap.add_argument("--fetch-attachments", type=Path, metavar="DIR",
                    help="also download past-bid decks from Proposals and Tenders into "
                         "DIR, ready for ingest_source.py")
    ap.add_argument("--include-rfp", action="store_true",
                    help="with --fetch-attachments, also download the tenders. Off by "
                         "default: an RFP is the client's document, not ours to mine")
    ap.add_argument("--register-table", default=PROPOSALS_AND_TENDERS,
                    help=f"Proposals and Tenders table id (default: {PROPOSALS_AND_TENDERS})")
    args = ap.parse_args()

    if args.include_rfp and not args.fetch_attachments:
        ap.error("--include-rfp only means something with --fetch-attachments")

    token = None
    if args.from_file:
        records = load_saved(args.from_file)
        source_note = str(args.from_file)
    else:
        token = token_or_exit()
        records = fetch_records(args.base, args.table, token)
        source_note = None

    entries = [entry_from(r) for r in records]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "source": "airtable:content-library",
        "base": args.base,
        "table": args.table,
        "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "entries": entries,
    }, indent=2), encoding="utf-8")

    where = f" (from {source_note})" if source_note else ""
    print(f"Fetched {len(entries)} Content Library row(s){where} -> {args.out}")

    # A courtesy, not a gate: index_kb.py decides what is usable, and says so loudly.
    flagged = [(e, incomplete_reasons(e)) for e in entries]
    flagged = [(e, why) for e, why in flagged if why]
    if flagged:
        print(f"  {len(flagged)} row(s) are missing fields retrieval needs — "
              f"index_kb.py will report them:")
        for entry, why in flagged:
            print(f"    {entry['id']}: no {', '.join(why)}")

    restricted = sum(1 for e in entries if e["clearance"] == "internal-only")
    if restricted:
        print(f"  {restricted} row(s) are internal-only (a blank Clearance reads as "
              f"internal-only) and are excluded from retrieval by default")

    if args.fetch_attachments:
        if token is None:
            token = token_or_exit()
        register = fetch_records(args.base, args.register_table, token)
        saved, failed = download_attachments(
            register, args.fetch_attachments, token, args.include_rfp)
        kinds = ", ".join(sorted({k for k, _ in saved})) or "nothing"
        print(f"Downloaded {len(saved)} attachment(s) ({kinds}) -> {args.fetch_attachments}")
        for kind, path in saved:
            print(f"    {kind}: {path.name}")
        for problem in failed:
            print(f"  COULD NOT DOWNLOAD {problem}", file=sys.stderr)
        if saved:
            print("  Decks are drafting material, not entries. Run ingest_source.py on "
                  "one, then split, verify and clear what it drafts.")

    print(f"Next: python index_kb.py proposal-assets/knowledge-bank "
          f"--merge {args.out} -o kb_index.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
