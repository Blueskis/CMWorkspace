#!/usr/bin/env python3
"""Stage 1 extraction: a weekly document becomes a normalised snapshot.

    python extract.py <file> --period "Week 12" -o snapshot.json

Handles .xlsx, .docx, .pptx (Office Open XML, read with zipfile + ElementTree — no
third-party libraries) and .csv. Everything lands in the same shape, defined by
schemas/snapshot.schema.json, so the diff stage never needs to know which kind of
document it came from.

The one thing that matters here is the **item key**. Diffing is matching, and matching is
only as good as the key: a training row keyed on the learner, a plan row keyed on the
activity ID, a slide keyed on its title. Get the key wrong and every item reads as one
removal plus one addition. See reference/extraction-guide.md.
"""

import argparse
import csv
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {
    "s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/package/2006/relationships",
}

# Header names that make a good stable key, best first. Matched case-insensitively as a
# substring, so "RICEFW ID" and "Employee Email" both hit.
KEY_HINTS = [
    "ricefw", "ricefwa", "wricef",
    "deliverable id", "activity id", "task id", "item id", "id", "ref",
    "employee", "learner", "participant", "attendee", "user",
    "course", "curriculum", "module",
    "activity", "deliverable", "task", "milestone", "workstream", "name", "title",
]


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def norm(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def slug(text, limit=60):
    out = re.sub(r"[^a-z0-9]+", "-", norm(text).lower()).strip("-")
    return out[:limit] or "unnamed"


# --------------------------------------------------------------------------- xlsx


def _xlsx_shared_strings(zf):
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return ["".join(t.text or "" for t in si.iter(f"{{{NS['s']}}}t")) for si in root]


def _xlsx_sheets(zf):
    """Sheet name -> part path, via the workbook's relationships."""
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    target = {
        rel.get("Id"): rel.get("Target").lstrip("/")
        for rel in rels
        if rel.get("Type", "").endswith("/worksheet")
    }
    rid = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    out = []
    for sheet in wb.iter(f"{{{NS['s']}}}sheet"):
        part = target.get(sheet.get(rid))
        if part:
            out.append((sheet.get("name"), part if part.startswith("xl/") else f"xl/{part}"))
    return out


def _col_index(ref):
    letters = re.match(r"([A-Z]+)", ref or "A").group(1)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _xlsx_rows(zf, part, strings):
    root = ET.fromstring(zf.read(part))
    for row in root.iter(f"{{{NS['s']}}}row"):
        cells = {}
        for cell in row.iter(f"{{{NS['s']}}}c"):
            value = cell.find(f"{{{NS['s']}}}v")
            if cell.get("t") == "inlineStr":
                text = "".join(
                    t.text or "" for t in cell.iter(f"{{{NS['s']}}}t")
                )
            elif value is None:
                continue
            elif cell.get("t") == "s":
                text = strings[int(value.text)]
            else:
                text = value.text
            cells[_col_index(cell.get("r"))] = norm(text)
        if cells:
            width = max(cells) + 1
            yield [cells.get(i, "") for i in range(width)]


def _pick_key_column(headers):
    for hint in KEY_HINTS:
        for i, h in enumerate(headers):
            if hint in h.lower():
                return i
    for i, h in enumerate(headers):
        if h:
            return i
    return 0


def _table_items(rows, source, prefix, item_kind):
    """Shared shape for any header-plus-data-rows table, from xlsx, csv, or a doc table."""
    rows = [r for r in rows if any(c for c in r)]
    if len(rows) < 2:
        return []
    header_i = 0
    # A title row above the header is common; the header is the first row with >= 2 cells.
    for i, row in enumerate(rows[:5]):
        if sum(1 for c in row if c) >= 2:
            header_i = i
            break
    headers = [norm(h) for h in rows[header_i]]
    key_col = _pick_key_column(headers)
    items, seen = [], {}
    for row in rows[header_i + 1 :]:
        row = list(row) + [""] * (len(headers) - len(row))
        key = row[key_col] if key_col < len(row) else ""
        if not key:
            continue
        base = f"{prefix}:{slug(key)}"
        seen[base] = seen.get(base, 0) + 1
        item_id = base if seen[base] == 1 else f"{base}#{seen[base]}"
        fields = {
            headers[i]: row[i]
            for i in range(len(headers))
            if i != key_col and headers[i] and row[i]
        }
        items.append(
            {
                "item_id": item_id,
                "kind": item_kind,
                "label": key,
                "source_ref": source,
                "fields": fields,
                "text": "",
            }
        )
    return items


def extract_xlsx(path):
    items = []
    with zipfile.ZipFile(path) as zf:
        strings = _xlsx_shared_strings(zf)
        for name, part in _xlsx_sheets(zf):
            rows = list(_xlsx_rows(zf, part, strings))
            items += _table_items(rows, f"sheet '{name}'", slug(name), "row")
    return items


def extract_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = [[norm(c) for c in row] for row in csv.reader(fh)]
    return _table_items(rows, path.name, slug(path.stem), "row")


# --------------------------------------------------------------------------- docx


def _docx_text(node):
    return norm("".join(t.text or "" for t in node.iter(f"{{{NS['w']}}}t")))


def _docx_style(para):
    style = para.find(f"{{{NS['w']}}}pPr/{{{NS['w']}}}pStyle")
    return (style.get(f"{{{NS['w']}}}val") if style is not None else "") or ""


def extract_docx(path):
    with zipfile.ZipFile(path) as zf:
        body = ET.fromstring(zf.read("word/document.xml")).find(f"{{{NS['w']}}}body")

    items, current, table_n = [], None, 0
    for node in body:
        tag = node.tag.split("}")[-1]
        if tag == "p":
            text = _docx_text(node)
            if not text:
                continue
            if _docx_style(node).lower().startswith("heading"):
                current = {
                    "item_id": f"section:{slug(text)}",
                    "kind": "section",
                    "label": text,
                    "source_ref": f"heading '{text}'",
                    "fields": {},
                    "text": "",
                }
                items.append(current)
            elif current is not None:
                current["text"] = norm(f"{current['text']} {text}")
            else:
                items.append(
                    {
                        "item_id": "section:preamble",
                        "kind": "section",
                        "label": "(preamble)",
                        "source_ref": "before first heading",
                        "fields": {},
                        "text": text,
                    }
                )
                current = items[-1]
        elif tag == "tbl":
            table_n += 1
            rows = [
                [_docx_text(tc) for tc in tr.findall(f"{{{NS['w']}}}tc")]
                for tr in node.findall(f"{{{NS['w']}}}tr")
            ]
            label = current["label"] if current else f"table {table_n}"
            items += _table_items(
                rows, f"table {table_n} under '{label}'", f"t{table_n}", "row"
            )
    return items


# --------------------------------------------------------------------------- pptx


def _pptx_slide_parts(zf):
    names = [n for n in zf.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]
    return sorted(names, key=lambda n: int(re.search(r"(\d+)", n.split("/")[-1]).group(1)))


def _shape_is_title(shape):
    ph = shape.find(
        f"{{{NS['p']}}}nvSpPr/{{{NS['p']}}}nvPr/{{{NS['p']}}}ph"
    )
    return ph is not None and (ph.get("type") or "").startswith(("title", "ctrTitle"))


# Bullets that carry their own object ID — the RICEFWA-deck convention — become items in
# their own right, so an object's status can be tracked across weeks even when the slide
# it sits on is re-titled or re-ordered.
OBJECT_ID = re.compile(r"^([A-Z]{2,4}[-_][A-Z]?[-_]?\d{2,4}|[A-Z]{2,4}-[A-Z]-\d{2,4})\b[\s:.-]*(.*)$")
SEGMENT = re.compile(r"\s+[-–|]\s+")
METRIC = re.compile(r"^([A-Za-z][A-Za-z0-9 %/&'()-]{0,40}):\s*(.+)$")

STATUS_WORDS = (
    "not started", "backlog", "on hold", "blocked", "planned", "scoped", "in progress",
    "in build", "wip", "drafted", "in review", "in test", "testing", "uat", "complete",
    "completed", "done", "signed off", "closed",
)
RAG_WORDS = ("red", "amber", "yellow", "green", "blue")


def parse_object_bullet(line, source):
    """'FI-R-014 Payment run report - In Build - amber' -> a keyed item with fields."""
    segments = SEGMENT.split(line)
    head = OBJECT_ID.match(norm(segments[0]))
    if not head:
        return None
    obj_id, description = head.group(1), norm(head.group(2))
    fields = {}
    if description:
        fields["Description"] = description
    for segment in segments[1:]:
        value = norm(segment)
        low = value.lower()
        if low in RAG_WORDS:
            fields["RAG"] = value
        elif any(w in low for w in STATUS_WORDS):
            fields["Status"] = value
        else:
            fields.setdefault("Note", value)
    return {
        "item_id": f"object:{slug(obj_id)}",
        "kind": "object",
        "label": obj_id,
        "source_ref": source,
        "fields": fields,
        "text": "",
    }


def extract_pptx(path):
    items = []
    with zipfile.ZipFile(path) as zf:
        for n, part in enumerate(_pptx_slide_parts(zf), start=1):
            root = ET.fromstring(zf.read(part))
            title, body = "", []
            for shape in root.iter(f"{{{NS['p']}}}sp"):
                paras = [
                    norm("".join(t.text or "" for t in para.iter(f"{{{NS['a']}}}t")))
                    for para in shape.iter(f"{{{NS['a']}}}p")
                ]
                text = [p for p in paras if p]
                if not text:
                    continue
                if _shape_is_title(shape) and not title:
                    title = text[0]
                else:
                    body += text

            label = title or f"Slide {n}"
            slide = {
                "item_id": f"slide:{slug(label)}",
                "kind": "slide",
                "label": label,
                "source_ref": f"slide {n}",
                "fields": {},
                "text": "",
            }
            prose = []
            for line in body:
                obj = parse_object_bullet(line, f"slide {n} ('{label}')")
                if obj:
                    items.append(obj)
                    continue
                metric = METRIC.match(line)
                if metric and len(line) <= 60:
                    slide["fields"][norm(metric.group(1))] = norm(metric.group(2))
                    continue
                prose.append(line)
            slide["text"] = " • ".join(prose)
            items.append(slide)

            for ti, tbl in enumerate(root.iter(f"{{{NS['a']}}}tbl"), start=1):
                rows = [
                    [
                        norm("".join(t.text or "" for t in tc.iter(f"{{{NS['a']}}}t")))
                        for tc in tr.findall(f"{{{NS['a']}}}tc")
                    ]
                    for tr in tbl.findall(f"{{{NS['a']}}}tr")
                ]
                items += _table_items(
                    rows, f"slide {n} table {ti}", f"s{n}t{ti}", "row"
                )
    return items


EXTRACTORS = {
    ".xlsx": extract_xlsx,
    ".xlsm": extract_xlsx,
    ".docx": extract_docx,
    ".pptx": extract_pptx,
    ".csv": extract_csv,
}


def extract(path, period=None, doc_name=None):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in EXTRACTORS:
        raise SystemExit(
            f"{path.name}: unsupported type '{suffix}'. Supported: "
            + ", ".join(sorted(EXTRACTORS))
            + ".\nFor .doc/.ppt/.xls, resave as the Open XML format first."
        )
    items = EXTRACTORS[suffix](path)
    return {
        "document": {
            "name": doc_name or path.stem,
            "path": str(path),
            "doc_type": suffix.lstrip("."),
            "period_label": period or "(unlabelled)",
            "extracted_at": now(),
        },
        "items": items,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--period", help="e.g. 'Week 11' or '2026-08-14' — printed in the update")
    ap.add_argument("--name", help="document name to use instead of the filename stem")
    ap.add_argument("-o", "--out", help="write JSON here (default: stdout)")
    args = ap.parse_args()

    snapshot = extract(args.file, args.period, args.name)
    text = json.dumps(snapshot, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        kinds = {}
        for item in snapshot["items"]:
            kinds[item["kind"]] = kinds.get(item["kind"], 0) + 1
        summary = ", ".join(f"{v} {k}" for k, v in sorted(kinds.items())) or "nothing"
        print(f"{args.file} -> {args.out}: {summary}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
