#!/usr/bin/env python3
"""Embed viewer/viewer-core.js and the example map into viewer/stakeholder-map.html.

The published page is a single file, so the tested core and the sample data are inlined
between marker comments. Edit the sources, then run this; the Node test fails if they drift.

    python scripts/sync_viewer_core.py
"""

import json
import re
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
HTML = SKILL / "viewer" / "stakeholder-map.html"
CORE = SKILL / "viewer" / "viewer-core.js"
SAMPLE = SKILL / "examples" / "aviation-mro" / "stakeholder_map.json"


def replace_between(text, begin, end, body):
    a, b = text.index(begin), text.index(end)
    return text[: a + len(begin)] + body + text[b:]


def main():
    html = HTML.read_text(encoding="utf-8")
    core = CORE.read_text(encoding="utf-8").strip()
    html = replace_between(html, "/* core:begin */", "/* core:end */", "\n" + core + "\n")
    sample = json.dumps(json.loads(SAMPLE.read_text(encoding="utf-8")), ensure_ascii=False, separators=(",", ":"))
    sample = sample.replace("</", "<\\/")  # never close the script tag from data
    html = replace_between(html, "/* sample:begin */", "/* sample:end */", " " + sample + " ")
    HTML.write_text(html, encoding="utf-8")
    print(f"synced core ({len(core)} bytes) and sample map ({len(sample)} bytes) into {HTML.name}")


if __name__ == "__main__":
    sys.exit(main())
