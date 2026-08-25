#!/usr/bin/env python3
"""Bake the Bid Intake Desk artifact: index.src.html -> index.html.

    python tools/bid-intake-desk/build.py

Inlines what the published page cannot fetch (a strict CSP blocks every external host):
the two sample tenders. The page reads past bids live from Airtable through the viewer's
own connector, so nothing about that store needs baking in.

Re-run after editing index.src.html, then republish index.html.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

src = (HERE / "index.src.html").read_text(encoding="utf-8")

# Escaping "<" keeps any string in the JSON from closing the <script> element early.
embed = lambda o: json.dumps(o, ensure_ascii=False).replace("<", "\\u003c")

ROOT = HERE.parents[1]
samples = [
    ("__SAMPLE_DOC_2__", "Transport company — ERP change management (sample)",
     ROOT / "examples/transport-erp/inputs/Transport-Company-RFP.txt"),
    ("__SAMPLE_DOC__", "CFS Part 2, Ch 8 — Change Management and Training (sample)",
     ROOT / "examples/cfs-ch8/inputs/CFS-Part2-Ch8-Change-Mgt-and-Training.txt"),
]

out = src
for token, name, path in samples:
    out = out.replace(token, embed({"name": name, "text": path.read_text(encoding="utf-8")}))

left = [t for t in ("__SAMPLE_DOC__", "__SAMPLE_DOC_2__") if t in out]
assert not left, f"unfilled placeholders: {left}"

(HERE / "index.html").write_text(out, encoding="utf-8")
print(f"built {(HERE / 'index.html').stat().st_size / 1024:.0f} KB "
      f"(two sample tenders inlined; past bids read live)")
