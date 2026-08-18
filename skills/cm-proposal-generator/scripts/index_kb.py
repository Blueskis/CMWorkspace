#!/usr/bin/env python3
"""Scan a knowledge-bank directory into a single index JSON.

    python index_kb.py proposal-assets/knowledge-bank -o kb_index.json

The index is what retrieve.py queries. Section is derived from the top-level folder
under the bank root, so an entry's location determines what it can be retrieved for.

Validation is deliberately noisy: a malformed entry is reported and skipped rather than
silently half-indexed, because an entry that fails to index is invisible to retrieval
and shows up later as an unexplained [GAP].

Stdlib only — PyYAML is used when present, otherwise a minimal frontmatter parser
handles the flat scalar/list frontmatter the entry schema allows.
"""

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

STALE_AFTER_DAYS = 730  # 24 months, per reference/knowledge-bank-guide.md
REQUIRED_FIELDS = ("id", "title", "tags", "last_reviewed")
NUMBER_RE = re.compile(r"\d")


def parse_frontmatter(text):
    """Return (frontmatter_dict, body). Raises ValueError if the block is malformed."""
    if not text.startswith("---"):
        raise ValueError("missing YAML frontmatter block")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("unterminated YAML frontmatter block")
    raw, body = parts[1], parts[2].lstrip("\n")

    try:
        import yaml

        data = yaml.safe_load(raw) or {}
        if not isinstance(data, dict):
            raise ValueError("frontmatter is not a mapping")
        return data, body
    except ImportError:
        pass

    data = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        data[key.strip()] = _coerce(value.strip())
    return data, body


def _coerce(value):
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [v.strip().strip("\"'") for v in inner.split(",") if v.strip()]
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    return value.strip("\"'")


def _jsonable(value):
    """Frontmatter passed through YAML can hold dates; the index is JSON.

    Applies to nested blocks like `bid`, where a `submitted:` field parses as a real date
    object and would otherwise fail the whole index at write time.
    """
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


def _as_date(value):
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def index_entry(path, bank_root):
    """Build one index record. Raises ValueError with a fixable message on bad input."""
    fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))

    missing = [f for f in REQUIRED_FIELDS if not fm.get(f)]
    if missing:
        raise ValueError(f"missing required frontmatter: {', '.join(missing)}")

    rel = path.relative_to(bank_root)
    section = fm.get("section") or (rel.parts[0] if len(rel.parts) > 1 else "uncategorised")

    tags = fm["tags"] if isinstance(fm["tags"], list) else [fm["tags"]]
    tags = [str(t).strip().lower() for t in tags if str(t).strip()]

    reviewed = _as_date(fm["last_reviewed"])
    stale = (date.today() - reviewed).days > STALE_AFTER_DAYS

    warnings = []
    if NUMBER_RE.search(body) and not fm.get("metrics_verified"):
        warnings.append(
            "body contains numbers but metrics_verified is not true — "
            "unverified metrics must not reach a bid"
        )
    if stale:
        warnings.append(f"last reviewed {reviewed.isoformat()} — confirm before shipping")

    # A past bid's outcome only matters if it survives into the index — retrieval and any
    # front end read the index, never the files. An entry from a lost bid that indexes as
    # indistinguishable from a won one defeats the point of recording the outcome at all.
    bid = fm.get("bid") if isinstance(fm.get("bid"), dict) else None
    if bid and not bid.get("outcome"):
        warnings.append("bid block has no outcome — record it, or set it to 'unknown'")
    if section in ("past-rfps", "presentations") and not bid:
        warnings.append(f"{section} entry has no bid block — outcome unknown to retrieval")

    return {
        "id": str(fm["id"]),
        "title": str(fm["title"]),
        "section": section,
        "tags": tags,
        "clearance": fm.get("clearance", "anonymised"),
        "last_reviewed": reviewed.isoformat(),
        "stale": stale,
        "owner": fm.get("owner"),
        "metrics_verified": bool(fm.get("metrics_verified", False)),
        "supersedes": fm.get("supersedes") or [],
        "bid": _jsonable(bid),
        "source_document": fm.get("source_document"),
        "path": str(rel),
        "word_count": len(body.split()),
        "excerpt": " ".join(body.split())[:300],
        "warnings": warnings,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("bank_root", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("kb_index.json"))
    args = ap.parse_args()

    if not args.bank_root.is_dir():
        sys.exit(f"not a directory: {args.bank_root}")

    entries, errors, seen = [], [], {}
    for path in sorted(args.bank_root.rglob("*.md")):
        if path.name.upper() in ("README.MD",):
            continue
        try:
            entry = index_entry(path, args.bank_root)
        except (ValueError, KeyError) as exc:
            errors.append({"path": str(path), "error": str(exc)})
            continue
        if entry["id"] in seen:
            errors.append(
                {"path": str(path), "error": f"duplicate id '{entry['id']}' (also in {seen[entry['id']]})"}
            )
            continue
        seen[entry["id"]] = entry["path"]
        entries.append(entry)

    superseded = {sid for e in entries for sid in e["supersedes"]}
    for entry in entries:
        entry["superseded"] = entry["id"] in superseded

    index = {
        "bank_root": str(args.bank_root),
        "generated": datetime.now().isoformat(timespec="seconds"),
        "entry_count": len(entries),
        "sections": sorted({e["section"] for e in entries}),
        "entries": entries,
        "errors": errors,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(index, indent=2), encoding="utf-8")

    print(f"Indexed {len(entries)} entries across {len(index['sections'])} sections -> {args.out}")
    warned = sum(1 for e in entries if e["warnings"])
    if warned:
        print(f"  {warned} of {len(entries)} entries carry warnings (see index)")
    for err in errors:
        print(f"  SKIPPED {err['path']}: {err['error']}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
