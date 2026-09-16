#!/usr/bin/env python3
"""Orchestrate deck-builder's intake stage: ingest documents, profile the template,
resolve brand, and index everything for retrieval (Stage 1).

    python intake.py sources_dir/ --template client.potx --deck-type steerco-update \
        -o decks/<run>/intake/
    python intake.py sources_dir/ --template client.potx --deck-type steerco-update \
        --brand brand_profile.json -o decks/<run>/intake/

This is a thin orchestrator over existing, already-tested tools — it does not reimplement
document parsing, template profiling, or chunking. Same posture as service/runner.py:
subprocess calls over the real scripts, a clear error naming which stage failed, never a
silent partial run.

Pipeline within this one stage:

  1. `ingest_sources.py` (change-impact-assessment) — mixed client files -> text +
     source manifest. Handles .docx/.pptx/.xlsx/.csv/.vtt/.srt/BPMN; PDFs and images are
     listed for the vision pass rather than text-extracted (see reference/vision-reading.md).
  2. `map_source.py` (training-material-generator) — the same folder -> source_map.json,
     the complete-coverage outline retrieval is checked against later. Two different
     documents of what the same folder contains, kept deliberately separate — see that
     script's own docstring for why coverage and retrieval must not share one index.
  3. `lib/deck/cli/profile.mjs` — the template -> template_profile.json (JS profiler; see
     that script's docstring for why the Python profiler is not used here).
  4. `lib/brand_profile.py` — resolves the brand: reads --brand if given, else extracts
     one from the template via --from-template (stamped with no approval — Stage 2 stops
     if it's used unapproved).
  5. `lib/deck_index.py index` — source_map.json (+ vision_notes.json, if present from a
     prior vision pass) -> chunk_index.json for Stage 3's retrieval.

Vision reading (PDF/image pages -> vision_notes.json) is NOT run here — it is a step the
model performs by hand: rasterise with `node lib/deck/cli/rasterise.mjs`, then Read each
page and write vision_notes.json per reference/vision-reading.md. This script prints the
list of pages to read when ingest_sources.py flags any `read_natively` sources.

Stdlib only, except shelling out to Python scripts (openpyxl where ingest_sources.py needs
it) and to `node` for the template profile.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LIB = REPO_ROOT / "lib"
CIA_SCRIPTS = REPO_ROOT / "skills" / "change-impact-assessment" / "scripts"
TMG_SCRIPTS = REPO_ROOT / "skills" / "training-material-generator" / "scripts"


def run(cmd, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, **kw)
    if result.returncode != 0:
        sys.exit(f"stage failed (exit {result.returncode}): {' '.join(str(c) for c in cmd)}")
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", type=Path, help="Folder of client documents")
    ap.add_argument("--template", type=Path, required=True)
    ap.add_argument("--deck-type", required=True)
    ap.add_argument("--brand", type=Path, default=None, help="Existing brand_profile.json; extracted from the template if omitted")
    ap.add_argument("--client", default="", help="Client name, used only when extracting brand from the template")
    ap.add_argument("-o", "--out", type=Path, default=Path("intake"))
    args = ap.parse_args()

    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    registry = json.loads((LIB / "schemas" / "deck_registry.json").read_text(encoding="utf-8"))["deck_types"]
    if args.deck_type not in registry:
        sys.exit(f"unknown deck type '{args.deck_type}' — valid types: {', '.join(sorted(registry))}")

    print("[1/5] ingest_sources.py")
    run(["python3", str(CIA_SCRIPTS / "ingest_sources.py"), str(args.sources), "-o", str(out / "ingested")])

    print("[2/5] map_source.py")
    run(["python3", str(TMG_SCRIPTS / "map_source.py"), str(args.sources), "-o", str(out / "source_map.json")])

    print("[3/5] template profile")
    run(["node", str(LIB / "deck" / "cli" / "profile.mjs"), str(args.template), "-o", str(out / "template_profile.json")])
    profile = json.loads((out / "template_profile.json").read_text(encoding="utf-8"))

    print("[4/5] layout assignment")
    assignment_result = subprocess.run(
        ["node", "-e",
         "import('%s').then(async m => { const fs=await import('node:fs'); "
         "const p=JSON.parse(fs.readFileSync('%s')); "
         "fs.writeFileSync('%s', JSON.stringify(m.resolveLayoutRoles(p).assignment, null, 2)); "
         "fs.writeFileSync('%s', JSON.stringify(m.resolveLayoutRoles(p).notes, null, 2)); })"
         % (LIB / "deck" / "map-layouts.js", out / "template_profile.json", out / "assignment.json", out / "layout_notes.json")],
        capture_output=True, text=True,
    )
    if assignment_result.returncode != 0:
        sys.exit(f"layout assignment failed:\n{assignment_result.stderr}")

    print("[5/5] brand + retrieval index")
    if args.brand and args.brand.is_file():
        brand_cmd = ["python3", str(LIB / "brand_profile.py"), str(args.brand), "-o", str(out / "brand_profile.json")]
    else:
        brand_cmd = ["python3", str(LIB / "brand_profile.py"), "--from-template", str(out / "template_profile.json"),
                     "--client", args.client, "-o", str(out / "brand_profile.json")]
    subprocess.run(brand_cmd, capture_output=True, text=True)  # non-fatal: missing approval is expected here

    run(["python3", str(LIB / "deck_index.py"), "index", str(out / "source_map.json"), "-o", str(out / "chunk_index.json")])

    # ingest_sources.py's sources.json/INGEST_REPORT.md don't carry a stable machine-
    # readable per-file status field for this, so the vision-needed list is derived the
    # same way ingest_sources.py itself classifies these extensions (see its READ_NATIVELY
    # table): any PDF or image sitting in the sources folder needs the vision pass.
    vision_exts = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
    vision_sources = sorted(p for p in args.sources.rglob("*") if p.suffix.lower() in vision_exts)
    if vision_sources:
        print(f"\n{len(vision_sources)} source(s) need the vision pass (PDF/image — read natively, not text-extracted):")
        for s in vision_sources:
            print(f"  - {s}")
        print("Rasterise with `node lib/deck/cli/rasterise.mjs`, then Read each page and write "
              f"vision_notes.json into {out} per reference/vision-reading.md before indexing again "
              "with --vision-notes.")

    print(f"\nIntake complete -> {out}")
    print(f"  template_profile.json, assignment.json, source_map.json, chunk_index.json, brand_profile.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
