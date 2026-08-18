#!/usr/bin/env python3
"""Bake the Bid Intake Desk artifact: index.src.html + the bank -> index.html.

    python skills/cm-proposal-generator/scripts/index_kb.py proposal-assets/knowledge-bank \\
        -o tools/bid-intake-desk/kb_index.json
    python tools/bid-intake-desk/build.py

The page ships with a bank embedded so it opens with something to show. Re-run both
commands after changing the knowledge bank, then republish index.html as the artifact.
A viewer can also load their own kb_index.json from the page itself.
"""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
src = (HERE / "index.src.html").read_text(encoding="utf-8")
kb = json.loads((HERE / "kb_index.json").read_text(encoding="utf-8"))
keep = ("id","title","section","tags","clearance","last_reviewed","stale","owner",
        "metrics_verified","supersedes","superseded","bid","path","word_count",
        "excerpt","warnings")
slim = {"bank_root": kb["bank_root"], "generated": kb["generated"],
        "sections": kb["sections"],
        "entries": [{k: e.get(k) for k in keep} for e in kb["entries"]]}
sample = {"name": "CFS Part 2, Ch 8 — Change Management and Training (sample)",
          "text": (ROOT / "examples/cfs-ch8/inputs/CFS-Part2-Ch8-Change-Mgt-and-Training.txt").read_text(encoding="utf-8")}
embed = lambda o: json.dumps(o, ensure_ascii=False).replace("<", "\\u003c")
sample2 = {"name": "Transport company — ERP change management (sample)",
           "text": (ROOT / "examples/transport-erp/inputs/Transport-Company-RFP.txt")
                   .read_text(encoding="utf-8")}
out = (src.replace("__KB_SEED__", embed(slim))
          .replace("__SAMPLE_DOC_2__", embed(sample2))
          .replace("__SAMPLE_DOC__", embed(sample)))
assert not any(t in out for t in ("__KB_SEED__", "__SAMPLE_DOC__", "__SAMPLE_DOC_2__"))
(HERE / "index.html").write_text(out, encoding="utf-8")
print(f"built {(HERE / 'index.html').stat().st_size / 1024:.1f} KB"
      f" from {len(slim['entries'])} bank entries")
