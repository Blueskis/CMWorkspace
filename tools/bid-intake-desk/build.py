#!/usr/bin/env python3
"""Bake the Bid Intake Desk artifact: index.src.html -> index.html.

    python tools/bid-intake-desk/build.py

Only the two sample tenders are baked in — both Airtable tables are read live through
the viewer's own connector, so nothing about the knowledge bank is frozen into the page.
Re-run after editing index.src.html, then republish index.html as the artifact.
"""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
src = (HERE / "index.src.html").read_text(encoding="utf-8")
sample = {"name": "CFS Part 2, Ch 8 — Change Management and Training (sample)",
          "text": (ROOT / "examples/cfs-ch8/inputs/CFS-Part2-Ch8-Change-Mgt-and-Training.txt").read_text(encoding="utf-8")}
embed = lambda o: json.dumps(o, ensure_ascii=False).replace("<", "\\u003c")
sample2 = {"name": "Transport company — ERP change management (sample)",
           "text": (ROOT / "examples/transport-erp/inputs/Transport-Company-RFP.txt")
                   .read_text(encoding="utf-8")}
out = (src.replace("__SAMPLE_DOC_2__", embed(sample2))
          .replace("__SAMPLE_DOC__", embed(sample)))
assert not any(t in out for t in ("__SAMPLE_DOC__", "__SAMPLE_DOC_2__"))
(HERE / "index.html").write_text(out, encoding="utf-8")
print(f"built {(HERE / 'index.html').stat().st_size / 1024:.1f} KB "
      f"(both banks read live from Airtable)")
