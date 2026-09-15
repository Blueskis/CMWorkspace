#!/usr/bin/env python3
"""Stage 5 mechanical audit of a training deck plan (Stage 5).

    python qa_training.py training_brief.json deck_plan.json source_map.json \\
        asset_index.json --questions question_bank.json -o qa_report.md

Five checks, the first three of which are hard failures (non-zero exit):

  1. Objective coverage — every learning objective reaches at least one content slide
     AND at least one knowledge-check question.
  2. Source coverage — every 'procedure' section in source_map.json is cited by some
     block's `sources`, or explicitly listed in training_brief.json's `out_of_scope`
     with a reason. This is the check that keeps retrieval from silently deciding what
     the course covers — see map_source.py's docstring for why that matters.
  3. Provenance — every content block has sources or `gap: true` + `gap_note`. No third
     state.

Then two more, reported but not fatal on their own (a screenshot practitioners choose to
leave out, or a question the model is unsure about, are real decisions — but ones the
report must surface, not bury):

  4. Asset hygiene — every screenshot-role asset in asset_index.json is placed on some
     slide, or listed in deck_plan.json's `unused_assets` with a reason.
  5. Question sanity — every question's key references a real option; mcq/true-false
     questions have exactly one key; multi-select questions have at least one; an mcq
     has at least 4 options (1 correct + >=3 distractors, per reference/knowledge-checks.md);
     every question's objective_id exists in the brief.

`--questions` is optional — if question_bank.json doesn't exist yet (Stage 3 not
finished), check 1's question-half and check 5 are skipped with a note in the report
rather than treated as a failure of this script.

This covers the mechanical half of Stage 5. The instructional-integrity half —
objective/content/assessment alignment by eye, terminology drift, sequencing — runs
through the training-qa-agent skill afterward; this script does not attempt it. Deck
health (file validity, visual QA, template fidelity) runs through the pptx skill's own
tooling against the built .pptx; see SKILL.md's Stage 5 for the full checklist this
script prints at the end.
"""

import argparse
import json
import sys
from pathlib import Path


def audit(brief, plan, source_map, asset_index, questions):
    objectives = {o["lo_id"]: o for o in brief.get("learning_objectives", [])}
    out_of_scope = {e["section_id"] for e in brief.get("out_of_scope", [])}
    sections = {s["section_id"]: s for s in source_map.get("sections", [])}
    assets = {a["asset_id"]: a for a in asset_index.get("assets", [])}
    unused_declared = {e["asset_id"]: e["reason"] for e in plan.get("unused_assets", [])}

    lo_to_slides, sourced_sections, placed_assets = {}, set(), set()
    missing_provenance, gap_missing_note = [], []

    for module in plan.get("modules", []):
        for lo_id in module.get("objective_ids", []):
            lo_to_slides.setdefault(lo_id, [])
        for slide in module.get("slides", []):
            slide_los = module.get("objective_ids", [])
            for i, block in enumerate(slide.get("blocks", [])):
                where = f"{module['module_id']} / {slide['slide_id']} / block {i}"
                is_gap = bool(block.get("gap"))
                if is_gap:
                    if not block.get("gap_note"):
                        gap_missing_note.append(where)
                elif not block.get("sources"):
                    missing_provenance.append(where)
                else:
                    for lo_id in slide_los:
                        lo_to_slides[lo_id].append(slide["slide_id"])
                    for sid in block.get("sources", []):
                        sourced_sections.add(sid)

                if block.get("kind") == "image" and not is_gap:
                    asset_id = (block.get("content") or {}).get("asset_id")
                    if asset_id:
                        placed_assets.add(asset_id)

    # 1. objective coverage — content half
    lo_no_slide = [lo for lo in objectives if not lo_to_slides.get(lo)]

    # 1. objective coverage — question half, and 5. question sanity
    lo_no_question, question_errors = [], []
    if questions is not None:
        q_by_lo = {}
        for q in questions.get("questions", []):
            q_by_lo.setdefault(q["objective_id"], []).append(q)
            option_ids = {o["option_id"] for o in q.get("options", [])}
            bad_keys = [k for k in q.get("key", []) if k not in option_ids]
            if bad_keys:
                question_errors.append(f"{q['question_id']}: key references unknown option(s) {bad_keys}")
            if q["type"] in ("mcq", "true-false") and len(q.get("key", [])) != 1:
                question_errors.append(f"{q['question_id']}: type '{q['type']}' must have exactly one key")
            if q["type"] == "multi" and len(q.get("key", [])) < 1:
                question_errors.append(f"{q['question_id']}: type 'multi' needs at least one key")
            if q["type"] == "mcq" and len(q.get("options", [])) < 4:
                question_errors.append(
                    f"{q['question_id']}: mcq has only {len(q.get('options', []))} option(s) — "
                    f"needs >=4 (1 correct + >=3 distractors)"
                )
            if q["objective_id"] not in objectives:
                question_errors.append(f"{q['question_id']}: objective_id '{q['objective_id']}' not in training_brief.json")
            for sid in q.get("sources", []):
                if sid not in sections:
                    question_errors.append(f"{q['question_id']}: source '{sid}' not in source_map.json")
        lo_no_question = [lo for lo in objectives if not q_by_lo.get(lo)]

    # 2. source coverage
    uncovered_procedures = [
        sid for sid, s in sections.items()
        if s.get("classifier") == "procedure" and sid not in sourced_sections and sid not in out_of_scope
    ]

    # 4. asset hygiene
    screenshot_ids = {a["asset_id"] for a in asset_index.get("assets", []) if a.get("role") == "screenshot"}
    unplaced_screenshots = [
        aid for aid in screenshot_ids
        if aid not in placed_assets and aid not in unused_declared
    ]
    low_res_placed_unacked = []
    for module in plan.get("modules", []):
        for slide in module.get("slides", []):
            for block in slide.get("blocks", []):
                if block.get("kind") != "image" or block.get("gap"):
                    continue
                content = block.get("content") or {}
                asset = assets.get(content.get("asset_id"))
                if asset and "low_res" in asset.get("quality", []) and not content.get("ack_low_res"):
                    low_res_placed_unacked.append(f"{slide['slide_id']}: {content.get('asset_id')}")

    return {
        "objectives": objectives,
        "lo_no_slide": lo_no_slide,
        "lo_no_question": lo_no_question,
        "questions_checked": questions is not None,
        "question_errors": question_errors,
        "missing_provenance": missing_provenance,
        "gap_missing_note": gap_missing_note,
        "uncovered_procedures": uncovered_procedures,
        "sections": sections,
        "unplaced_screenshots": unplaced_screenshots,
        "unused_declared": unused_declared,
        "low_res_placed_unacked": low_res_placed_unacked,
    }


def render(result, plan, brief):
    hard_fail = bool(
        result["lo_no_slide"] or result["missing_provenance"] or result["gap_missing_note"]
        or result["uncovered_procedures"]
        or (result["questions_checked"] and result["lo_no_question"])
    )

    lines = [
        f"# Training QA Report — {plan.get('run_id', 'unnamed run')}",
        "",
        f"**Status:** {'FAIL — must fix before handover' if hard_fail else 'PASS (mechanical checks)'}",
        "",
        "## 1. Objective coverage",
        "",
        f"{len(result['objectives']) - len(result['lo_no_slide'])} of {len(result['objectives'])} "
        f"objective(s) reach a content slide.",
    ]
    if result["lo_no_slide"]:
        lines += ["", "### Objectives with no content slide"] + [
            f"- `{lo}` — {result['objectives'][lo]['text']}" for lo in sorted(result["lo_no_slide"])
        ]
    if not result["questions_checked"]:
        lines += ["", "> Question bank not supplied (`--questions`) — the question half of this "
                       "check and check 5 were skipped."]
    else:
        lines += [
            "",
            f"{len(result['objectives']) - len(result['lo_no_question'])} of {len(result['objectives'])} "
            f"objective(s) reach a knowledge-check question.",
        ]
        if result["lo_no_question"]:
            lines += ["", "### Objectives with no question"] + [
                f"- `{lo}` — {result['objectives'][lo]['text']}" for lo in sorted(result["lo_no_question"])
            ]

    lines += ["", "## 2. Source coverage", ""]
    if result["uncovered_procedures"]:
        lines += [
            "### FAIL — 'procedure' sections neither taught nor declared out of scope", "",
        ] + [
            f"- `{sid}` — {result['sections'][sid]['section_path']}"
            for sid in sorted(result["uncovered_procedures"])
        ]
    else:
        lines += ["Every 'procedure' section is either taught or listed in `out_of_scope`."]

    lines += ["", "## 3. Provenance", ""]
    if result["missing_provenance"]:
        lines += ["### FAIL — blocks with neither sources nor gap: true", ""] + [
            f"- {w}" for w in result["missing_provenance"]
        ]
    else:
        lines.append("Every content block carries sources or `gap: true`.")
    if result["gap_missing_note"]:
        lines += ["", "### FAIL — gap: true blocks missing gap_note", ""] + [
            f"- {w}" for w in result["gap_missing_note"]
        ]

    lines += ["", "## 4. Asset hygiene", ""]
    if result["unplaced_screenshots"]:
        lines += [
            "### Screenshot assets not placed and not declared in `unused_assets`", "",
            "Not a hard failure, but each needs a decision — place it or declare it unused with a reason:", "",
        ] + [f"- `{aid}`" for aid in sorted(result["unplaced_screenshots"])]
    else:
        lines.append("Every screenshot-role asset is placed or explicitly declared unused.")
    if result["low_res_placed_unacked"]:
        lines += ["", "### Low-res assets placed without acknowledgement", "",
                   "build_training_deck.py should have already refused these — if this report "
                   "still shows them, the deck was built from a different plan than this one:", ""] + [
            f"- {w}" for w in result["low_res_placed_unacked"]
        ]
    if result["unused_declared"]:
        lines += ["", "### Declared unused", ""] + [
            f"- `{aid}` — {reason}" for aid, reason in sorted(result["unused_declared"].items())
        ]

    if result["questions_checked"]:
        lines += ["", "## 5. Question sanity", ""]
        if result["question_errors"]:
            lines += ["Not a hard failure of this script, but each is a real defect to fix:", ""] + [
                f"- {e}" for e in result["question_errors"]
            ]
        else:
            lines.append("No structural defects found in the question bank.")
        lines += ["", "> Mechanical checks only — whether a question actually tests the objective, "
                       "and whether its key is truly the FSD's stated answer, still needs a read."]

    lines += [
        "",
        "## Remaining checks (run against the built .pptx via the pptx skill and training-qa-agent)",
        "",
        "- [ ] `markitdown training.pptx` — content order, typos, missing content",
        "- [ ] placeholder grep for leftover template text (`lorem`, `[insert`, `xxx`, `TODO`)",
        "- [ ] `validate.py training.pptx --original <approved-template>` — always pass `--original`",
        "- [ ] visual QA on rendered slides — screenshot overflow/aspect first, diagram label clipping second",
        "- [ ] template fidelity — fonts, colours and layouts still the approved template's",
        "- [ ] run the training-qa-agent skill for instructional integrity (objective alignment, "
        "sequencing, terminology drift, assessment quality) — findings land in the deck's speaker notes",
        "",
        "## Handover",
        "",
        "This is a **first draft for practitioner review**, not finished training material.",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("brief", type=Path)
    ap.add_argument("plan", type=Path)
    ap.add_argument("source_map", type=Path)
    ap.add_argument("assets", type=Path, help="asset_index.json")
    ap.add_argument("--questions", type=Path, default=None, help="question_bank.json (optional)")
    ap.add_argument("-o", "--out", type=Path, default=Path("qa_report.md"))
    args = ap.parse_args()

    brief = json.loads(args.brief.read_text(encoding="utf-8"))
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    source_map = json.loads(args.source_map.read_text(encoding="utf-8"))
    asset_index = json.loads(args.assets.read_text(encoding="utf-8"))
    questions = json.loads(args.questions.read_text(encoding="utf-8")) if args.questions else None

    result = audit(brief, plan, source_map, asset_index, questions)
    report = render(result, plan, brief)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")

    hard_fail = bool(
        result["lo_no_slide"] or result["missing_provenance"] or result["gap_missing_note"]
        or result["uncovered_procedures"]
        or (result["questions_checked"] and result["lo_no_question"])
    )

    print(f"Objectives: {len(result['objectives']) - len(result['lo_no_slide'])}/{len(result['objectives'])} "
          f"reach a slide")
    if result["questions_checked"]:
        print(f"Objectives: {len(result['objectives']) - len(result['lo_no_question'])}/{len(result['objectives'])} "
              f"reach a question")
    print(f"Uncovered procedure sections: {len(result['uncovered_procedures'])}")
    print(f"Provenance failures: {len(result['missing_provenance']) + len(result['gap_missing_note'])}")
    print(f"Unplaced screenshots: {len(result['unplaced_screenshots'])}")
    print(f"Report -> {args.out}")

    if hard_fail:
        print("FAIL: see report for details", file=sys.stderr)
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
