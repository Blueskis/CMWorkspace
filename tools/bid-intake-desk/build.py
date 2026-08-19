#!/usr/bin/env python3
"""Bake the Bid Intake Desk artifact: index.src.html -> index.html.

    python tools/bid-intake-desk/build.py

Inlines four things the published page cannot fetch (a strict CSP blocks every external
host): the two sample tenders, the in-browser .pptx renderer, the generic template as
base64, and that template's profile. Both Airtable tables are read live through the
viewer's own connector, so nothing about the knowledge bank is frozen into the page.

Re-run after editing index.src.html or pptx.js, then republish index.html.
"""
import base64
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TEMPLATE = ROOT / "proposal-assets/templates/pptx-generic/pptx-generic.potx"
PROFILE = ROOT / "proposal-assets/templates/pptx-generic/template_profile.json"

src = (HERE / "index.src.html").read_text(encoding="utf-8")

# Escaping "<" keeps any string in the JSON from closing the <script> element early.
embed = lambda o: json.dumps(o, ensure_ascii=False).replace("<", "\\u003c")

samples = [
    ("__SAMPLE_DOC_2__", "Transport company — ERP change management (sample)",
     ROOT / "examples/transport-erp/inputs/Transport-Company-RFP.txt"),
    ("__SAMPLE_DOC__", "CFS Part 2, Ch 8 — Change Management and Training (sample)",
     ROOT / "examples/cfs-ch8/inputs/CFS-Part2-Ch8-Change-Mgt-and-Training.txt"),
]

out = src
for token, name, path in samples:
    out = out.replace(token, embed({"name": name, "text": path.read_text(encoding="utf-8")}))

out = out.replace("__PPTX_JS__", (HERE / "pptx.js").read_text(encoding="utf-8"))
out = out.replace("__TEMPLATE_PROFILE__", embed(json.loads(PROFILE.read_text(encoding="utf-8"))))
out = out.replace("__TEMPLATE_B64__", base64.b64encode(TEMPLATE.read_bytes()).decode("ascii"))

left = [t for t in ("__SAMPLE_DOC__", "__SAMPLE_DOC_2__", "__PPTX_JS__",
                    "__TEMPLATE_PROFILE__", "__TEMPLATE_B64__") if t in out]
assert not left, f"unfilled placeholders: {left}"

(HERE / "index.html").write_text(out, encoding="utf-8")
print(f"built {(HERE / 'index.html').stat().st_size / 1024:.0f} KB "
      f"(template {TEMPLATE.stat().st_size / 1024:.0f} KB inlined; banks read live)")
