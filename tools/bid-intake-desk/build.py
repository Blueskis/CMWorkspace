#!/usr/bin/env python3
"""Bake the Bid Intake Desk artifact: index.src.html -> index.html.

    python tools/bid-intake-desk/build.py

Inlines what the published page cannot fetch (a strict CSP blocks every external host):
the two sample tenders, the worked example's plan and brief, the in-browser .pptx
renderer, the generic template as base64, that template's profile, and the knowledge bank
itself.

The bank is baked rather than read live because a browser cannot reach a git repository,
so entries are fixed until the next publish — adding one means rebuilding this file. The
register of past bids is still read live from Airtable through the viewer's own connector.

Re-run after editing index.src.html or pptx.js, then republish index.html.
"""
import base64
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BANK = ROOT / "proposal-assets/knowledge-bank"

# The indexer, not a second frontmatter reader. Anything the pipeline would reject must be
# rejected here too, or the page ships entries the rest of the system considers invalid.
sys.path.insert(0, str(ROOT / "skills/cm-proposal-generator/scripts"))
import index_kb  # noqa: E402
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

# The worked example, so Stage 04 can be watched running before a real plan exists.
for token, path in (("__EXAMPLE_PLAN__", ROOT / "examples/acme-erp/proposal_plan.json"),
                    ("__EXAMPLE_BRIEF__", ROOT / "examples/acme-erp/rfp_brief.json")):
    out = out.replace(token, embed(json.loads(path.read_text(encoding="utf-8"))))

# The knowledge bank, with bodies: the page puts an entry's own prose on a slide, so an
# excerpt is not enough. A malformed entry fails the build rather than shipping.
entries, errors = [], []
for path in sorted(BANK.rglob("*.md")):
    if path.name.upper() == "README.MD":
        continue
    try:
        entries.append(index_kb.index_entry(path, BANK, with_body=True))
    except (ValueError, KeyError) as exc:
        errors.append(f"{path.relative_to(ROOT)}: {exc}")
assert not errors, "knowledge-bank entries failed to index:\n  " + "\n  ".join(errors)

superseded = {sid for e in entries for sid in e["supersedes"]}
for entry in entries:
    entry["superseded"] = entry["id"] in superseded

out = out.replace("__REPO_BANK__", embed({"entries": entries}))
out = out.replace("__PPTX_JS__", (HERE / "pptx.js").read_text(encoding="utf-8"))
out = out.replace("__TEMPLATE_PROFILE__", embed(json.loads(PROFILE.read_text(encoding="utf-8"))))
out = out.replace("__TEMPLATE_B64__", base64.b64encode(TEMPLATE.read_bytes()).decode("ascii"))

left = [t for t in ("__SAMPLE_DOC__", "__SAMPLE_DOC_2__", "__EXAMPLE_PLAN__",
                    "__EXAMPLE_BRIEF__", "__PPTX_JS__", "__TEMPLATE_PROFILE__",
                    "__TEMPLATE_B64__", "__REPO_BANK__") if t in out]
assert not left, f"unfilled placeholders: {left}"

(HERE / "index.html").write_text(out, encoding="utf-8")
print(f"built {(HERE / 'index.html').stat().st_size / 1024:.0f} KB "
      f"(template {TEMPLATE.stat().st_size / 1024:.0f} KB inlined; "
      f"{len(entries)} bank entries baked in; past bids read live)")
warned = sum(1 for e in entries if e["warnings"])
if warned:
    print(f"  {warned} of {len(entries)} baked entries carry warnings — "
          f"run index_kb.py to read them")
