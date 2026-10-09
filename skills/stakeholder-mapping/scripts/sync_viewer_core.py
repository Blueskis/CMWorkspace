#!/usr/bin/env python3
"""Embed viewer/viewer-core.js and the three example maps into viewer/stakeholder-map.html.

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
# The viewer ships three fictional industry samples. aviation-mro is the fuller worked example
# for the skill (with a transcript and an org chart image) and is not embedded.
SAMPLES = [("airline", "Airline", "Meridian Air"),
           ("healthcare", "Healthcare", "Harbourview Hospital"),
           ("financial", "Financial services", "Crestline Bank")]
FOLDERS = {"airline": "airline", "healthcare": "healthcare", "financial": "financial-services"}


def replace_between(text, begin, end, body):
    a, b = text.index(begin), text.index(end)
    return text[: a + len(begin)] + body + text[b:]


def main():
    html = HTML.read_text(encoding="utf-8")
    core = CORE.read_text(encoding="utf-8").strip()
    html = replace_between(html, "/* core:begin */", "/* core:end */", "\n" + core + "\n")
    bundle = {}
    for key, industry, company in SAMPLES:
        path = SKILL / "examples" / FOLDERS[key] / "stakeholder_map.json"
        bundle[key] = {"label": f"{industry} ({company})", "map": json.loads(path.read_text(encoding="utf-8"))}
    sample = json.dumps(bundle, ensure_ascii=False, separators=(",", ":"))
    sample = sample.replace("</", "<\\/")  # never close the script tag from data
    html = replace_between(html, "/* sample:begin */", "/* sample:end */", " " + sample + " ")
    HTML.write_text(html, encoding="utf-8")
    print(f"synced core ({len(core)} bytes) and {len(bundle)} sample maps ({len(sample)} bytes) into {HTML.name}")


if __name__ == "__main__":
    sys.exit(main())
