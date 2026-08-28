#!/usr/bin/env python3
"""Stage 1 — read the source documents into one addressable index.

    python ingest_docs.py inputs/ -o training/<run>/source_index.json --assets training/<run>/assets
    python ingest_docs.py fsd.docx rules.xlsx -o source_index.json --assets assets/ --run-id po-20260828

Produces `source_index.json` against schemas/source_index.schema.json: heading-anchored
text chunks, tables kept as rows, images written out as their original bytes, and the
topic list the deck has to cover.

Everything downstream cites an **anchor** from this file (`FSD#4.2.1@p17`), which is what
makes a claim on a slide checkable against the spec. Get the anchors wrong here and the
provenance guarantee downstream is decorative.

.docx and .xlsx are both ZIPs of XML, so extraction is stdlib-only and lossless — image
bytes are copied out untouched, never re-encoded. Parsing is read-only, so the pptx
skill's warning about ElementTree corrupting OOXML on write does not apply.

Three deliberate behaviours:

  * **Tables stay tables.** An FSD's field rules live in a table whose columns say
    mandatory or optional. Flattened to prose that distinction is the first thing lost, and
    it is exactly what training has to get right.
  * **Images carry their context** — caption, nearest heading, document ordinal — because a
    screenshot is only useful on the slide for the step it illustrates.
  * **Nothing is silently discarded.** Unreadable parts, unknown formats and skipped files
    land in `warnings`, and repeated images are recorded with an occurrence count rather
    than dropped, so Stage 5 can tell a de-duplicated logo from a missing screenshot.
"""

import argparse
import hashlib
import json
import re
import shutil
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
V = "{urn:schemas-microsoft-com:vml}"
XL = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
XDR = "{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}"
PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"

CAPTION_RE = re.compile(r"^\s*(figure|fig\.?|exhibit|screenshot|table|diagram)\b", re.I)
CLAUSE_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)[.)]?\s+(.*)$")
# Document furniture: present in every spec, teachable in none of them.
OUT_OF_SCOPE_RE = re.compile(
    r"\b(revision history|version history|document control|document history|change log|"
    r"sign[- ]?off|approval history|distribution list|table of contents|"
    r"contents|amendment record|references|appendix a\b)\b",
    re.I,
)
MEDIA_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
    ".bmp": "image/bmp", ".tif": "image/tiff", ".tiff": "image/tiff", ".svg": "image/svg+xml",
    ".emf": "image/x-emf", ".wmf": "image/x-wmf", ".webp": "image/webp",
}


# --- small helpers ---------------------------------------------------------


def slugify(text, limit=60):
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug[:limit].rstrip("-")) or "untitled"


def image_size(data):
    """(width, height) for the raster formats a spec actually contains, else (None, None).

    Vector parts (EMF/WMF/SVG) have no pixel size; they return None and are exempt from
    the legibility check downstream rather than being guessed at.
    """
    try:
        if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
            return struct.unpack(">II", data[16:24])
        if data[:2] == b"\xff\xd8":  # JPEG: walk the marker segments to the frame header
            i = 2
            while i < len(data) - 9:
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker, seglen = data[i + 1], struct.unpack(">H", data[i + 2:i + 4])[0]
                if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                    h, w = struct.unpack(">HH", data[i + 5:i + 9])
                    return w, h
                i += 2 + seglen
        if data[:6] in (b"GIF87a", b"GIF89a"):
            return struct.unpack("<HH", data[6:10])
        if data[:2] == b"BM":
            return struct.unpack("<ii", data[18:26])
    except (struct.error, IndexError):
        pass
    return None, None


def classify_asset(caption, alt_text, width, height, occurrences, filename):
    """Best-guess asset kind, with the reasons kept so the model can overrule it at Stage 3.

    Only screenshot/diagram/chart are candidates for placement, so a misfiled logo costs a
    slide rather than filling the deck with page furniture. The model re-reads this at
    Stage 3 — these heuristics decide the default, not the outcome.
    """
    # The image's own name and alt text are how it is *labelled*; the caption is how the
    # document *talks about* it. Keep them apart — a caption reading "the header and lines
    # grid" describes a screenshot, and matching "header" there would file it as a logo.
    label = f"{alt_text or ''} {filename}".lower()
    described = f"{caption or ''} {alt_text or ''} {filename}".lower()
    reasons = []

    if re.search(r"\blogo\b|\bwatermark\b|\bbrand(ing)?\b", label):
        reasons.append("named as a logo or watermark")
        return "logo", reasons
    if re.search(r"\bheader\b|\bfooter\b", label) and not caption:
        reasons.append("named as page header/footer art and carries no figure caption")
        return "logo", reasons
    if occurrences > 1 and not caption:
        reasons.append(
            f"appears {occurrences}x with no figure caption — page furniture repeats, "
            f"a captioned figure does not"
        )
        return "logo", reasons
    if re.search(r"\bflow\b|\bprocess\b|\bdiagram\b|\bswimlane\b|\barchitecture\b|\blandscape\b", described):
        reasons.append("caption or name describes a diagram")
        return "diagram", reasons
    if re.search(r"\bchart\b|\bgraph\b|\bplot\b", described):
        reasons.append("caption or name describes a chart")
        return "chart", reasons
    if re.search(r"\bscreen\b|\bscreenshot\b|\bui\b|\bform\b|\bdialog\b|\btransaction\b|\bqueue\b", described):
        reasons.append("caption or name describes a screen")
        return "screenshot", reasons
    if occurrences > 1:
        reasons.append(f"appears {occurrences}x — repeated, but captioned; kind not determined")
        return "unknown", reasons
    if width and height:
        if width < 200 or height < 100:
            reasons.append(f"{width}x{height}px — too small to be a screen capture")
            return "icon", reasons
        if width >= 600:
            reasons.append(f"{width}x{height}px with a figure caption" if caption
                           else f"{width}x{height}px")
            return "screenshot", reasons
        reasons.append(f"{width}x{height}px — mid-size, kind not determined")
        return "unknown", reasons
    reasons.append("no pixel dimensions available (vector or unreadable header)")
    return "unknown", reasons


# --- docx ------------------------------------------------------------------


def docx_style_names(zf):
    """styleId -> human style name, so 'Heading 2' is found however Word spelled the id."""
    try:
        root = ET.fromstring(zf.read("word/styles.xml"))
    except KeyError:
        return {}
    names = {}
    for style in root.iterfind(f"{W}style"):
        name_el = style.find(f"{W}name")
        if name_el is not None:
            names[style.get(f"{W}styleId", "")] = name_el.get(f"{W}val", "")
    return names


def rels_map(zf, part_rels):
    """rId -> target path, resolved relative to the part's own directory."""
    try:
        root = ET.fromstring(zf.read(part_rels))
    except KeyError:
        return {}
    base = Path(part_rels).parent.parent
    out = {}
    for rel in root.iterfind(f"{PKG_REL}Relationship"):
        target = rel.get("Target", "")
        if target.startswith("/"):
            out[rel.get("Id")] = target.lstrip("/")
        elif not target.startswith("http"):
            out[rel.get("Id")] = str((base / target).as_posix()).replace("../", "")
    return out


def para_text(para):
    """Visible text of a paragraph, with tabs and line breaks preserved as spaces."""
    parts = []
    for node in para.iter():
        if node.tag == f"{W}t":
            parts.append(node.text or "")
        elif node.tag in (f"{W}tab", f"{W}br"):
            parts.append(" ")
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def heading_level(para, style_names):
    """Outline level of a paragraph, or None if it is body text."""
    ppr = para.find(f"{W}pPr")
    if ppr is None:
        return None
    style_el = ppr.find(f"{W}pStyle")
    if style_el is not None:
        style_id = style_el.get(f"{W}val", "")
        name = style_names.get(style_id, style_id)
        match = re.search(r"heading\s*(\d)", name, re.I) or re.search(r"^Heading(\d)$", style_id)
        if match:
            return int(match.group(1))
        if re.fullmatch(r"title", name, re.I):
            return 1
    outline = ppr.find(f"{W}outlineLvl")
    if outline is not None:
        try:
            return int(outline.get(f"{W}val", "9")) + 1
        except ValueError:
            return None
    return None


def para_images(para):
    """(rId, alt_text) for every image anchored in this paragraph, in order."""
    found = []
    for drawing in para.iter(f"{W}drawing"):
        alt = None
        doc_pr = drawing.find(f".//{WP}docPr")
        if doc_pr is not None:
            alt = doc_pr.get("descr") or doc_pr.get("name")
        for blip in drawing.iter(f"{A}blip"):
            rid = blip.get(f"{R}embed") or blip.get(f"{R}link")
            if rid:
                found.append((rid, alt))
    for imagedata in para.iter(f"{V}imagedata"):  # legacy VML pictures
        rid = imagedata.get(f"{R}id")
        if rid:
            found.append((rid, imagedata.get(f"{V}title") or imagedata.get("o:title")))
    return found


def table_rows(tbl):
    rows = []
    for tr in tbl.iterfind(f"{W}tr"):
        rows.append([
            re.sub(r"\s+", " ", " ".join(para_text(p) for p in tc.iterfind(f"{W}p"))).strip()
            for tc in tr.iterfind(f"{W}tc")
        ])
    return rows


def ingest_docx(path, doc_id, assets_dir, state):
    """Walk a .docx body in document order, emitting chunks, tables and assets."""
    chunks, assets, warnings = [], [], []
    with zipfile.ZipFile(path) as zf:
        style_names = docx_style_names(zf)
        rels = rels_map(zf, "word/_rels/document.xml.rels")
        body = ET.fromstring(zf.read("word/document.xml")).find(f"{W}body")
        if body is None:
            return [], [], [f"{path.name}: no document body"]

        heading_path, page, ordinal = [], 1, 0
        current = None
        pending_caption_for = []

        def close_chunk():
            if current and (current["text"].strip() or current["tables"] or current["asset_ids"]):
                chunks.append(current)

        def open_chunk(title, level, clause):
            nonlocal current
            close_chunk()
            slug = clause or slugify(title)
            anchor = f"{doc_id}#{slug}"
            if anchor in state["anchors"]:
                anchor = f"{anchor}-{state['anchors'][anchor] + 1}"
            state["anchors"][anchor] = state["anchors"].get(anchor, 0) + 1
            current = {
                "anchor": anchor, "doc_id": doc_id,
                "heading_path": list(heading_path), "clause": clause,
                "text": "", "ordinal": ordinal, "page": page,
                "word_count": 0, "tables": [], "asset_ids": [],
            }

        # A preamble chunk catches anything before the first heading.
        open_chunk(path.stem, 1, None)

        for node in body:
            if node.tag == f"{W}p":
                ordinal += 1
                page += sum(1 for _ in node.iter(f"{W}lastRenderedPageBreak"))
                page += sum(1 for br in node.iter(f"{W}br")
                            if br.get(f"{W}type") == "page")
                text = para_text(node)
                level = heading_level(node, style_names)

                if level and text:
                    heading_path = heading_path[: level - 1] + [text]
                    match = CLAUSE_RE.match(text)
                    clause = match.group(1) if match else None
                    open_chunk(text, level, clause)
                    continue

                for rid, alt in para_images(node):
                    target = rels.get(rid)
                    if not target:
                        warnings.append(f"{doc_id}: image relationship {rid} has no target")
                        continue
                    try:
                        data = zf.read(target)
                    except KeyError:
                        warnings.append(f"{doc_id}: missing image part {target}")
                        continue
                    asset = register_asset(
                        data, Path(target).suffix.lower(), doc_id, alt, heading_path,
                        current["anchor"], ordinal, assets_dir, state,
                    )
                    assets.append(asset)
                    current["asset_ids"].append(asset["asset_id"])
                    pending_caption_for.append(asset)

                if text:
                    style_el = node.find(f"{W}pPr/{W}pStyle")
                    style_name = style_names.get(
                        style_el.get(f"{W}val", "") if style_el is not None else "", ""
                    )
                    is_caption = "caption" in style_name.lower() or CAPTION_RE.match(text)
                    if is_caption and pending_caption_for:
                        for asset in pending_caption_for:
                            asset["caption"] = text
                        pending_caption_for = []
                    current["text"] += ("\n" if current["text"] else "") + text
                    if not is_caption:
                        pending_caption_for = []

            elif node.tag == f"{W}tbl":
                ordinal += 1
                rows = table_rows(node)
                if not rows:
                    continue
                table_id = f"{current['anchor']}-tbl{len(current['tables']) + 1}"
                current["tables"].append({
                    "table_id": table_id, "caption": None,
                    "header": rows[0], "rows": rows[1:], "sheet": None,
                })
                pending_caption_for = []

        close_chunk()

    for chunk in chunks:
        chunk["word_count"] = len(chunk["text"].split())
    return chunks, assets, warnings


# --- xlsx ------------------------------------------------------------------


def col_index(ref):
    letters = re.match(r"([A-Z]+)", ref or "")
    if not letters:
        return 0
    n = 0
    for ch in letters.group(1):
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def ingest_xlsx(path, doc_id, assets_dir, state):
    """Each worksheet becomes one chunk carrying one table; drawings become assets."""
    chunks, assets, warnings = [], [], []
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()

        shared = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.iterfind(f"{XL}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{XL}t")))

        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        wb_rels = rels_map(zf, "xl/_rels/workbook.xml.rels")

        for ordinal, sheet in enumerate(wb.iterfind(f".//{XL}sheet"), 1):
            sheet_name = sheet.get("name", f"Sheet{ordinal}")
            target = wb_rels.get(sheet.get(f"{R}id"))
            if not target or target not in names:
                warnings.append(f"{doc_id}: worksheet '{sheet_name}' part not found")
                continue

            rows = []
            sheet_root = ET.fromstring(zf.read(target))
            for row in sheet_root.iterfind(f".//{XL}row"):
                cells, width = {}, 0
                for cell in row.iterfind(f"{XL}c"):
                    idx = col_index(cell.get("r", ""))
                    if cell.get("t") == "s":
                        v = cell.find(f"{XL}v")
                        value = shared[int(v.text)] if v is not None and v.text else ""
                    elif cell.get("t") == "inlineStr":
                        value = "".join(t.text or "" for t in cell.iter(f"{XL}t"))
                    else:
                        v = cell.find(f"{XL}v")
                        value = (v.text or "") if v is not None else ""
                    if value:
                        cells[idx] = value.strip()
                        width = max(width, idx + 1)
                if cells:
                    rows.append([cells.get(i, "") for i in range(width)])
            if not rows:
                continue

            anchor = f"{doc_id}#{slugify(sheet_name)}"
            header, body_rows = rows[0], rows[1:]
            chunk = {
                "anchor": anchor, "doc_id": doc_id,
                "heading_path": [sheet_name], "clause": None,
                "text": f"Worksheet '{sheet_name}': {len(body_rows)} row(s) under "
                        f"columns {', '.join(h for h in header if h)}.",
                "ordinal": ordinal, "page": None, "word_count": 0,
                "tables": [{
                    "table_id": f"{anchor}-tbl1", "caption": sheet_name,
                    "header": header, "rows": body_rows, "sheet": sheet_name,
                }],
                "asset_ids": [],
            }

            sheet_rels = rels_map(zf, f"xl/worksheets/_rels/{Path(target).name}.rels")
            for rid, drawing_target in sheet_rels.items():
                if "drawing" not in drawing_target or drawing_target not in names:
                    continue
                drawing_rels = rels_map(
                    zf, f"xl/drawings/_rels/{Path(drawing_target).name}.rels"
                )
                drawing_root = ET.fromstring(zf.read(drawing_target))
                for anchor_el in drawing_root:
                    from_el = anchor_el.find(f"{XDR}from")
                    cell_ref = None
                    if from_el is not None:
                        col = from_el.findtext(f"{XDR}col", "0")
                        row_no = from_el.findtext(f"{XDR}row", "0")
                        cell_ref = f"{sheet_name}!r{int(row_no) + 1}c{int(col) + 1}"
                    for blip in anchor_el.iter(f"{A}blip"):
                        image_rid = blip.get(f"{R}embed")
                        image_target = drawing_rels.get(image_rid)
                        if not image_target or image_target not in names:
                            continue
                        asset = register_asset(
                            zf.read(image_target), Path(image_target).suffix.lower(),
                            doc_id, None, [sheet_name], anchor, ordinal,
                            assets_dir, state,
                        )
                        asset["sheet_ref"] = cell_ref
                        assets.append(asset)
                        chunk["asset_ids"].append(asset["asset_id"])

            chunk["word_count"] = len(chunk["text"].split())
            chunks.append(chunk)
    return chunks, assets, warnings


# --- plain text ------------------------------------------------------------


def ingest_text(path, doc_id, state):
    """Markdown/plain text, chunked on ATX headings."""
    chunks = []
    heading_path, current = [], None

    def open_chunk(title, level, ordinal):
        nonlocal current
        if current and current["text"].strip():
            chunks.append(current)
        match = CLAUSE_RE.match(title)
        clause = match.group(1) if match else None
        anchor = f"{doc_id}#{clause or slugify(title)}"
        if anchor in state["anchors"]:
            anchor = f"{anchor}-{state['anchors'][anchor] + 1}"
        state["anchors"][anchor] = state["anchors"].get(anchor, 0) + 1
        current = {
            "anchor": anchor, "doc_id": doc_id, "heading_path": list(heading_path),
            "clause": clause, "text": "", "ordinal": ordinal, "page": None,
            "word_count": 0, "tables": [], "asset_ids": [],
        }

    open_chunk(path.stem, 1, 0)
    for ordinal, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if match:
            level, title = len(match.group(1)), match.group(2).strip()
            heading_path = heading_path[: level - 1] + [title]
            open_chunk(title, level, ordinal)
        elif line.strip():
            current["text"] += ("\n" if current["text"] else "") + line.strip()

    if current and current["text"].strip():
        chunks.append(current)
    for chunk in chunks:
        chunk["word_count"] = len(chunk["text"].split())
    return chunks, [], []


# --- assets ----------------------------------------------------------------


def register_asset(data, suffix, doc_id, alt_text, heading_path, anchor, ordinal,
                   assets_dir, state):
    """Write image bytes out once, keyed by content hash, and describe them.

    Identical bytes seen again return the first asset with its occurrence count bumped —
    that is how the logo in every page header collapses to one record that classifies as
    `logo` rather than a dozen phantom screenshots.
    """
    digest = hashlib.sha256(data).hexdigest()
    if digest in state["by_hash"]:
        existing = state["by_hash"][digest]
        existing["occurrences"] += 1
        kind, reasons = classify_asset(
            existing.get("caption"), existing.get("alt_text"),
            existing.get("width_px"), existing.get("height_px"),
            existing["occurrences"], Path(existing["path"]).name,
        )
        existing["asset_kind"], existing["classification_reasons"] = kind, reasons
        return existing

    state["asset_no"] += 1
    asset_id = f"{doc_id}-img{state['asset_no']:02d}"
    suffix = suffix if suffix in MEDIA_TYPES else ".bin"
    out_path = assets_dir / f"{asset_id}{suffix}"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)

    width, height = image_size(data)
    kind, reasons = classify_asset(None, alt_text, width, height, 1, out_path.name)
    asset = {
        "asset_id": asset_id, "doc_id": doc_id, "path": str(out_path),
        "media_type": MEDIA_TYPES.get(suffix, "application/octet-stream"),
        "asset_kind": kind, "caption": None, "alt_text": alt_text,
        "heading_path": list(heading_path), "anchor": anchor, "ordinal": ordinal,
        "width_px": width, "height_px": height, "bytes": len(data),
        "sha256": digest, "occurrences": 1, "sheet_ref": None,
        "classification_reasons": reasons,
    }
    state["by_hash"][digest] = asset
    return asset


def reclassify_with_captions(assets):
    """Re-run classification now that captions are attached — a caption outranks pixels."""
    for asset in assets:
        kind, reasons = classify_asset(
            asset.get("caption"), asset.get("alt_text"),
            asset.get("width_px"), asset.get("height_px"),
            asset["occurrences"], Path(asset["path"]).name,
        )
        asset["asset_kind"], asset["classification_reasons"] = kind, reasons


# --- topics ----------------------------------------------------------------


PLACEMENT_KINDS = ("screenshot", "diagram", "chart")


def build_topics(chunks, assets):
    """One topic per chunk that could plausibly be taught.

    A chunk carrying nothing but the page logo is not a topic — the substance test counts
    only placement-class images, so a section header's branding cannot make an empty
    heading look teachable.
    """
    kinds = {a["asset_id"]: a["asset_kind"] for a in assets}
    topics = []
    for i, chunk in enumerate(chunks, 1):
        title = chunk["heading_path"][-1] if chunk["heading_path"] else chunk["anchor"]
        substantive_assets = [
            aid for aid in chunk["asset_ids"] if kinds.get(aid) in PLACEMENT_KINDS
        ]
        furniture = bool(OUT_OF_SCOPE_RE.search(title))
        thin = (chunk["word_count"] < 15 and not chunk["tables"]
                and not substantive_assets)
        topic = {
            "id": f"T{i}", "title": title, "anchor": chunk["anchor"],
            "heading_path": chunk["heading_path"], "word_count": chunk["word_count"],
            "asset_ids": chunk["asset_ids"], "in_scope": not (furniture or thin),
        }
        if furniture:
            topic["scope_note"] = "document furniture, not teachable content"
        elif thin:
            topic["scope_note"] = "heading with no substantive body text, table or image"
        topics.append(topic)
    return topics


# --- driver ----------------------------------------------------------------


HANDLERS = {".docx": "docx", ".xlsx": "xlsx", ".txt": "text", ".md": "text"}


def collect_inputs(paths):
    files = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(p for p in path.rglob("*") if p.is_file()))
        else:
            files.append(path)
    return files


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("inputs", nargs="+", type=Path, help="Files, or directories of them")
    ap.add_argument("-o", "--out", type=Path, default=Path("source_index.json"))
    ap.add_argument("--assets", type=Path, default=Path("assets"),
                    help="Directory to write extracted images into")
    ap.add_argument("--run-id", help="Defaults to the first input's stem plus today's date")
    args = ap.parse_args()

    files = collect_inputs(args.inputs)
    if not files:
        sys.exit(f"no files found under {', '.join(str(p) for p in args.inputs)}")

    state = {"by_hash": {}, "anchors": {}, "asset_no": 0}
    documents, chunks, assets, warnings = [], [], [], []
    used_ids = set()

    for path in files:
        kind = HANDLERS.get(path.suffix.lower())
        if kind is None:
            if path.suffix.lower() == ".pdf":
                warnings.append(
                    f"{path.name}: PDF skipped. Extract its text with the `pdf` skill and "
                    f"pass that as .txt — this pipeline does not read images out of PDFs, "
                    f"and a PDF ingested as text has images_extracted=false so Stage 5 "
                    f"does not report a clean sweep it never made."
                )
            else:
                warnings.append(f"{path.name}: unsupported format {path.suffix}, skipped")
            continue

        doc_id = re.sub(r"[^A-Za-z0-9]+", "", path.stem.upper())[:8] or "DOC"
        base, n = doc_id, 2
        while doc_id in used_ids:
            doc_id, n = f"{base}{n}", n + 1
        used_ids.add(doc_id)
        state["asset_no"] = 0

        try:
            if kind == "docx":
                c, a, w = ingest_docx(path, doc_id, args.assets, state)
            elif kind == "xlsx":
                c, a, w = ingest_xlsx(path, doc_id, args.assets, state)
            else:
                c, a, w = ingest_text(path, doc_id, state)
        except (zipfile.BadZipFile, ET.ParseError, KeyError) as exc:
            warnings.append(f"{path.name}: could not read ({type(exc).__name__}: {exc})")
            continue

        chunks.extend(c)
        assets.extend(a)
        warnings.extend(w)
        documents.append({
            "doc_id": doc_id, "path": str(path), "kind": kind if kind != "text" else path.suffix.lstrip("."),
            "title": path.stem,
            "images_extracted": kind in ("docx", "xlsx"),
            "chunk_count": len(c), "asset_count": len({x["asset_id"] for x in a}),
        })

    # De-duplicate assets by id — a repeated image is registered once and referenced many.
    unique_assets = list({a["asset_id"]: a for a in assets}.values())
    reclassify_with_captions(unique_assets)

    index = {
        "run_id": args.run_id or f"{slugify(files[0].stem)}-{datetime.now():%Y%m%d}",
        "generated": datetime.now().isoformat(timespec="seconds"),
        "documents": documents,
        "chunks": chunks,
        "assets": unique_assets,
        "topics": build_topics(chunks, unique_assets),
        "warnings": warnings,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(index, indent=2), encoding="utf-8")

    kinds = {}
    for asset in unique_assets:
        kinds[asset["asset_kind"]] = kinds.get(asset["asset_kind"], 0) + 1
    in_scope = sum(1 for t in index["topics"] if t["in_scope"])

    print(f"Ingested {len(documents)} document(s) -> {args.out}")
    print(f"  {len(chunks)} chunk(s), {sum(len(c['tables']) for c in chunks)} table(s), "
          f"{in_scope}/{len(index['topics'])} topics in scope")
    print(f"  {len(unique_assets)} image(s) -> {args.assets}"
          + (f"  ({', '.join(f'{v} {k}' for k, v in sorted(kinds.items()))})" if kinds else ""))
    placeable = [a for a in unique_assets if a["asset_kind"] in ("screenshot", "diagram", "chart")]
    if placeable:
        print(f"  {len(placeable)} placement-class asset(s) — every one must be placed or "
              f"excluded with a reason, or Stage 5 fails")
    for warning in warnings:
        print(f"  WARNING {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
