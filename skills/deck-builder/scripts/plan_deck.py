#!/usr/bin/env python3
"""Validate a deck_plan.json against its deck type, template, and the fit/variety gates
(deck-builder Stage 3).

    python plan_deck.py deck_plan.json --deck-type status-update \
        --profile decks/<run>/intake/template_profile.json \
        --assignment decks/<run>/intake/assignment.json \
        -o decks/<run>/plan_validation.json

deck_plan.json is already in the shape lib/deck/build-pptx.js's buildPptx() consumes
natively — `{modules:[{module_id, slides:[{slide_id, role, title, blocks:[{slot, kind,
content, sources, gap, gap_note}], speaker_notes}]}]}` — so a plan written here or in the
artifact's browser-side plan.js are interchangeable, and lib/deck/cli/assemble.mjs needs
no adapter step.

Four checks, all hard fails unless noted:

  * **deck type** — the requested --deck-type exists in lib/schemas/deck_registry.json
    (an unknown type is rejected outright, never silently defaulted — deck-builder test
    case #28) and the plan's slide roles, in order, cover every role the registry marks
    required for that type.
  * **provenance** — every text/image/diagram block has a non-empty `sources[]` or
    `gap: true` + `gap_note`. No third state. A block whose ONLY source is a vision note
    (`vision::` prefixed chunk_id) with `confidence: "low"` (checked against
    vision_notes.json when --vision-notes is passed) is also a failure — a shaky read of
    an unclear diagram cannot be a claim's sole support.
  * **fit** — shells out to lib/deck/cli/check-fit.mjs, the same text-fit.js arithmetic
    composeSlide uses at build time, so a "fits" verdict here means what it means at
    build time. Never shrinks below the floor to make something fit; overflow is a hard
    failure naming the slide and placeholder.
  * **variety** — no more than two consecutive slides on one layout; a picture-capable
    layout the plan never uses is a warning, not a failure.

Stdlib only, except that it shells out to `node` for the fit/variety check (see
lib/deck/cli/check-fit.mjs's own docstring for why: reusing the assembler's own sizing
math rather than a second, driftable Python reimplementation).
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

LIB = Path(__file__).resolve().parents[3] / "lib"
REGISTRY_PATH = LIB / "schemas" / "deck_registry.json"


def load_registry():
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))["deck_types"]


def check_deck_type(plan, deck_type, registry):
    errors = []
    if deck_type not in registry:
        return [f"unknown deck type '{deck_type}' — valid types: {', '.join(sorted(registry))}"]
    entry = registry[deck_type]
    roles_in_plan = [
        slide["role"]
        for mod in plan.get("modules", [])
        for slide in mod.get("slides", [])
    ]
    required = entry["required_roles"]
    # subsequence check: every required role must appear, in order (not necessarily adjacent)
    ptr = 0
    for role in roles_in_plan:
        if ptr < len(required) and role == required[ptr]:
            ptr += 1
    if ptr < len(required):
        missing = required[ptr:]
        errors.append(
            f"deck type '{deck_type}' requires these roles, in order, and the plan is "
            f"missing (from position {ptr}): {missing} — plan has roles: {roles_in_plan}"
        )
    return errors


def check_provenance(plan, vision_notes=None):
    errors = []
    vision_confidence = {}
    if vision_notes:
        for note in vision_notes.get("notes", []):
            vision_confidence[f"vision::{note['note_id']}"] = note.get("confidence", "medium")

    for mod in plan.get("modules", []):
        for slide in mod.get("slides", []):
            for i, block in enumerate(slide.get("blocks", [])):
                where = f"{slide['slide_id']} block {i} ({block.get('slot')})"
                is_gap = bool(block.get("gap"))
                if is_gap:
                    if not block.get("gap_note"):
                        errors.append(f"{where}: gap is true but gap_note is missing")
                    continue
                sources = block.get("sources") or []
                if not sources:
                    errors.append(f"{where}: no sources and gap is not true — no third state allowed")
                    continue
                # a block whose ONLY source is a low-confidence vision note fails —
                # deck-builder test case #19
                confidences = [vision_confidence.get(s) for s in sources if s in vision_confidence]
                non_vision_sources = [s for s in sources if s not in vision_confidence]
                if confidences and not non_vision_sources and all(c == "low" for c in confidences):
                    errors.append(
                        f"{where}: sole source is a low-confidence vision note ({sources}) — "
                        f"pair it with a supporting text source, or mark the block gap: true"
                    )
    return errors


def check_fit_and_variety(plan_path, profile_path, assignment_path):
    node_script = LIB / "deck" / "cli" / "check-fit.mjs"
    result = subprocess.run(
        ["node", str(node_script), "--plan", str(plan_path), "--profile", str(profile_path), "--assignment", str(assignment_path)],
        capture_output=True, text=True,
    )
    if result.returncode not in (0, 1):
        sys.exit(f"check-fit.mjs crashed (exit {result.returncode}):\n{result.stderr}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        sys.exit(f"check-fit.mjs produced non-JSON output:\n{result.stdout}\n{result.stderr}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", type=Path)
    ap.add_argument("--deck-type", required=True)
    ap.add_argument("--profile", type=Path, required=True, help="template_profile.json from lib/deck/cli/profile.mjs")
    ap.add_argument("--assignment", type=Path, required=True, help="layout-role assignment.json from resolveLayoutRoles")
    ap.add_argument("--vision-notes", type=Path, default=None)
    ap.add_argument("-o", "--out", type=Path, default=Path("plan_validation.json"))
    args = ap.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    registry = load_registry()
    vision_notes = json.loads(args.vision_notes.read_text(encoding="utf-8")) if args.vision_notes and args.vision_notes.is_file() else None

    deck_type_errors = check_deck_type(plan, args.deck_type, registry)
    provenance_errors = check_provenance(plan, vision_notes)
    fit_variety = check_fit_and_variety(args.plan, args.profile, args.assignment) if not deck_type_errors[:1] or True else {"failures": [], "warnings": []}

    all_failures = (
        [{"type": "deck-type", "message": m} for m in deck_type_errors]
        + [{"type": "provenance", "message": m} for m in provenance_errors]
        + fit_variety.get("failures", [])
    )
    report = {
        "plan": str(args.plan),
        "deck_type": args.deck_type,
        "hard_fail": bool(all_failures),
        "failures": all_failures,
        "warnings": fit_variety.get("warnings", []),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"{'FAILED' if report['hard_fail'] else 'PASSED'}: {len(all_failures)} failure(s), {len(report['warnings'])} warning(s) -> {args.out}")
    for f in all_failures:
        print(f"  ERROR [{f.get('type')}] {f.get('message')}", file=sys.stderr)
    for w in report["warnings"]:
        print(f"  WARNING [{w.get('type')}] {w.get('message')}", file=sys.stderr)
    return 1 if report["hard_fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
