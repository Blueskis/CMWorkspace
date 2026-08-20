#!/usr/bin/env python3
"""Download past-bid decks from Airtable, so they can be turned into bank entries.

    export AIRTABLE_TOKEN=pat...
    python sync_airtable.py --out-dir proposals/sources
    python ingest_source.py proposals/sources/<deck>.pptx \\
        -o proposal-assets/knowledge-bank/methodology/<entry>.md --outcome won

This is the one manual link in an otherwise hands-off contribution path. A colleague adds
a bid to `CM Knowledge Bank -> Proposals and Tenders` and attaches its deck — that is all
they do. Neither the intake page nor the pipeline can read that attachment on its own: the
files sit on a host the artifact's CSP blocks, and a sandboxed environment usually blocks
the same hosts at the proxy. Given network access and a token, this closes that gap.

Decks only by default. An RFP is the client's own tender: useful for judging how closely a
past bid resembles the current one, never a source to draft our content from.

What comes out is drafting material, not entries. `ingest_source.py` extracts, a person
splits and clears, and only then does `index_kb.py` see it.

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
from pathlib import Path

API_ROOT = "https://api.airtable.com/v0"
TOKEN_ENV = "AIRTABLE_TOKEN"

BASE_ID = "appAi9h5mT0hPz5o2"
PROPOSALS_AND_TENDERS = "tblxQyGlAV81vz3ES"

# Field ids, not field names: a column renamed in the Airtable UI keeps its id, so the
# register survives a rename. Mirrors AIRTABLE.field in tools/bid-intake-desk/index.src.html.
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

    returnFieldsByFieldId keeps the response keyed the way REGISTER_FIELD expects.
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
    ap.add_argument("--out-dir", type=Path, default=Path("proposals/sources"),
                    help="where to put the downloads (default: proposals/sources)")
    ap.add_argument("--base", default=BASE_ID, help=f"base id (default: {BASE_ID})")
    ap.add_argument("--table", default=PROPOSALS_AND_TENDERS,
                    help=f"register table id (default: {PROPOSALS_AND_TENDERS})")
    ap.add_argument("--include-rfp", action="store_true",
                    help="also download the tenders. Off by default: an RFP is the "
                         "client's document, not ours to mine")
    ap.add_argument("--from-file", type=Path, metavar="FILE",
                    help="read a saved API response instead of listing the table — the "
                         "attachment urls in it must still be live")
    args = ap.parse_args()

    token = None
    if args.from_file:
        records = load_saved(args.from_file)
    else:
        token = token_or_exit()
        records = fetch_records(args.base, args.table, token)
    print(f"{len(records)} record(s) in the register")

    saved, failed = download_attachments(records, args.out_dir, token, args.include_rfp)
    kinds = ", ".join(sorted({k for k, _ in saved})) or "nothing"
    print(f"Downloaded {len(saved)} attachment(s) ({kinds}) -> {args.out_dir}")
    for kind, path in saved:
        print(f"    {kind}: {path.name}")
    for problem in failed:
        print(f"  COULD NOT DOWNLOAD {problem}", file=sys.stderr)

    if saved:
        print("\nThese are drafting material, not entries. For each one worth using:")
        print("  python ingest_source.py <file> -o "
              "proposal-assets/knowledge-bank/<section>/<entry>.md --outcome <won|lost|...>")
        print("then split it into single-idea entries, check every number, set clearance, "
              "and rebuild\nthe intake page so the entries reach a deck.")
    elif not failed:
        print("Nothing to download — no decks are attached to any record yet."
              + ("" if args.include_rfp else " (Tenders are skipped; --include-rfp to add them.)"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
