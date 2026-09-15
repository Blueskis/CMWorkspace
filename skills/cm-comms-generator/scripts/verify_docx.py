#!/usr/bin/env python3
"""Check that a produced .docx still contains what the plan promised.

    python verify_docx.py draft.docx --plan comms_plan.json --brief change_brief.json

QA runs on the plan; this runs on the artifact. Between the two sits a producer that can
silently drop content — a block that rendered to an empty expression, a table that lost its
rows, a [GAP] that vanished instead of staying visible. This catches that.

Three checks, all hard:

  1. Structure   the file is a readable OOXML package with a non-empty document body
  2. Coverage    every non-gap block's text survived into the document
  3. Gaps        every [GAP] in the plan is still VISIBLE in the document — a gap that
                 disappears during production is the worst possible failure, because the
                 draft then reads as complete when it is not

Also reports the sender and help route from the brief, since those are the two things a
comm most often loses in translation.

STATUS (v0.2): this reads text, not layout. It cannot tell you the document looks right —
overflowing tables, bad page breaks and clashing fonts need eyes. Where LibreOffice is
available, `soffice --convert-to pdf` then rasterise and look; that path is not available
in every environment, and this check is what remains true regardless.
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def document_paragraphs(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    out = []
    for p in root.iter(f"{{{W}}}p"):
        text = "".join(t.text or "" for t in p.iter(f"{{{W}}}t")).strip()
        if text:
            out.append(text)
    tables = len(list(root.iter(f"{{{W}}}tbl")))
    return out, tables


def normalise(s):
    """Compare on words, not punctuation — producers legitimately re-wrap text.

    Runs of whitespace collapse to one space: stripping punctuation leaves gaps where
    an em-dash or newline was, and without collapsing, every probe spanning one would
    fail against a document that is actually correct.
    """
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", str(s).lower()).split())


def block_strings(block):
    """Every human-readable string a block should contribute."""
    if block.get("gap"):
        return []
    out = []

    def walk(v):
        if isinstance(v, str):
            if v.strip():
                out.append(v)
        elif isinstance(v, list):
            for i in v:
                walk(i)
        elif isinstance(v, dict):
            for i in v.values():
                walk(i)

    walk(block.get("content"))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("docx", type=Path)
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--brief", type=Path)
    ap.add_argument("--sample-words", type=int, default=6,
                    help="Words of each block compared against the document (default 6)")
    args = ap.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    brief = json.loads(args.brief.read_text(encoding="utf-8")) if args.brief else {}

    try:
        paras, tables = document_paragraphs(args.docx)
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        sys.exit(f"{args.docx} is not a readable .docx: {type(exc).__name__}: {exc}")

    if not paras:
        sys.exit(f"{args.docx} has no text content — the producer wrote an empty document")

    haystack = normalise(" ".join(paras))
    failures, gaps_found, checked = [], 0, 0

    for section in plan.get("sections", []):
        for part in section.get("slides", []):
            for i, block in enumerate(part.get("blocks", [])):
                if block.get("gap"):
                    note = normalise(block.get("gap_note", ""))
                    probe = " ".join(note.split()[:args.sample_words])
                    if probe and probe in haystack:
                        gaps_found += 1
                    else:
                        failures.append(
                            f"{part['slide_id']} block {i}: the [GAP] is NOT visible in the "
                            f"document — a gap lost in production makes an incomplete draft "
                            f"read as finished")
                    continue
                for s in block_strings(block):
                    checked += 1
                    probe = " ".join(normalise(s).split()[:args.sample_words])
                    if probe and probe not in haystack:
                        failures.append(
                            f"{part['slide_id']} block {i}: text did not survive into the "
                            f"document — \"{s[:60]}\"")

    # The two things a comm most often loses in translation.
    gov = brief.get("governance") or {}
    for label, value in (("sender", (gov.get("sender") or {}).get("name")),
                         ("help route", (gov.get("help_route") or {}).get("detail"))):
        if value and normalise(value) not in haystack:
            failures.append(f"the {label} ({value}) is not in the document")

    print(f"{args.docx}: {len(paras)} paragraphs, {tables} table(s)")
    print(f"  {checked} block string(s) checked, {gaps_found} [GAP](s) still visible")

    if failures:
        for f in failures:
            print(f"  FAIL {f}", file=sys.stderr)
        print(f"  {len(failures)} failure(s)", file=sys.stderr)
        return 1

    print("  all plan content survived into the artifact")
    print("  NOTE: this checks text, not layout — look at the rendered pages where you can.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
