#!/usr/bin/env python3
"""Stage 5 audit of a training plan against the documents it was built from.

    python qa_training.py source_index.json training_plan.json -o qa_report.md

Six checks. The first five are mechanical and must not be done by eye; the sixth is the
checklist for the things only a person looking at the rendered deck can judge.

  1. Objective coverage   every LO reaches a module AND is tested by a question
  2. Topic coverage       every in-scope topic is taught or deliberately deferred
  3. Provenance           every block has sources or an explicit [GAP]
  4. Asset triage         every screenshot is placed or excluded with a reason
  5. Question integrity   5 per check, both types present, per-type option rules
  6. Deck health          the render-target checklist, printed not duplicated

Exits non-zero on a hard failure: an untested objective, an unattributed block, a dropped
screenshot, or a malformed check. Those are not warnings — each one is a way for wrong or
unaccountable material to reach a learner, which is the failure this pipeline exists to
prevent.
"""

import argparse
import json
import re
import sys
from pathlib import Path

PLACEMENT_KINDS = ("screenshot", "diagram", "chart")
BANNED_STEM = ("all of the above", "none of the above", "both a and b")
# "Which of these is NOT mandatory?" and its variants. Matches a capitalised NOT
# anywhere, or an interrogative opening followed by a negation or "except".
NEGATIVE_STEM_RE = re.compile(
    r"\bNOT\b|^\s*(which|what|all)\b[^?]{0,60}?\b(not|never|except|cannot)\b",
    re.IGNORECASE | re.MULTILINE,
)


def iter_blocks(plan):
    for module in plan.get("modules", []):
        for slide in module.get("slides", []):
            for i, block in enumerate(slide.get("blocks", [])):
                yield module, slide, i, block


def audit(index, plan):
    result = {
        "uncovered_objectives": [], "untested_objectives": [], "unknown_objectives": [],
        "uncovered_topics": [], "unknown_topics": [], "deferred": [],
        "missing_provenance": [], "gaps": [], "unknown_anchors": [],
        "unplaced_assets": [], "unusable_assets": [], "unknown_assets": [],
        "question_faults": [], "check_count": 0, "question_count": 0,
    }

    objectives = {lo["id"]: lo for lo in plan.get("learning_objectives", [])}
    anchors = {c["anchor"] for c in index.get("chunks", [])}
    topics = {t["id"]: t for t in index.get("topics", [])}
    assets = {a["asset_id"]: a for a in index.get("assets", [])}

    # 1 + 2 — coverage
    in_modules, in_topics = set(), set()
    for module in plan.get("modules", []):
        in_modules.update(module.get("objective_ids", []))
        in_topics.update(module.get("topic_ids", []))

    deferred = {d["topic_id"]: d["reason"] for d in plan.get("deferred_topics", [])}
    result["deferred"] = [{"topic_id": k, "reason": v} for k, v in deferred.items()]

    result["uncovered_objectives"] = sorted(set(objectives) - in_modules)
    result["unknown_objectives"] = sorted(in_modules - set(objectives))
    for topic_id, topic in topics.items():
        if not topic.get("in_scope", True):
            continue
        if topic_id not in in_topics and topic_id not in deferred:
            result["uncovered_topics"].append(topic)
    result["unknown_topics"] = sorted(in_topics - set(topics))

    # 3 + 5 — provenance and questions, walking every block once
    tested_objectives = set()
    placed_assets = set()

    for module, slide, i, block in iter_blocks(plan):
        where = f"{module['module_id']} / {slide['slide_id']} / block {i}"

        if block.get("gap"):
            result["gaps"].append({
                "where": where,
                "note": block.get("gap_note", "(no gap_note recorded)"),
                "objective_ids": slide.get("objective_ids") or module.get("objective_ids", []),
            })
        elif not block.get("sources"):
            result["missing_provenance"].append(where)

        for anchor in block.get("sources", []):
            if anchor not in anchors:
                result["unknown_anchors"].append({"where": where, "anchor": anchor})

        if block.get("kind") == "image" and block.get("asset_id"):
            placed_assets.add(block["asset_id"])
            if block["asset_id"] not in assets:
                result["unknown_assets"].append({"where": where, "asset_id": block["asset_id"]})

        if block.get("kind") == "questions":
            result["check_count"] += 1
            questions = block.get("questions") or []
            result["question_count"] += len(questions)
            result["question_faults"].extend(
                check_questions(questions, where, anchors, tested_objectives)
            )

    result["untested_objectives"] = sorted(set(objectives) - tested_objectives)

    # 4 — asset triage
    excluded = {e["asset_id"]: e["reason"] for e in plan.get("excluded_assets", [])}
    for asset_id, asset in assets.items():
        if asset["asset_kind"] not in PLACEMENT_KINDS:
            continue
        if asset_id in placed_assets or asset_id in excluded:
            continue
        result["unplaced_assets"].append(asset)

    for asset_id in placed_assets:
        asset = assets.get(asset_id)
        if asset and asset.get("width_px") and asset["width_px"] < 600:
            result["unusable_assets"].append(asset)

    result["objectives"] = objectives
    result["topics"] = topics
    return result


def check_questions(questions, where, anchors, tested_objectives):
    """Every rule a knowledge check has to satisfy. Returns a list of fault strings."""
    faults = []

    if len(questions) != 5:
        remedy = (
            "Add questions, or merge this module into its neighbour if the documents "
            "cannot support 5."
            if len(questions) < 5
            else "Cut to the 5 that best test the objectives."
        )
        faults.append(
            f"{where}: {len(questions)} question(s) — every knowledge check carries "
            f"exactly 5. {remedy}"
        )

    types = {q.get("type") for q in questions}
    if questions and len(types) == 1:
        only = types.pop()
        faults.append(
            f"{where}: all {len(questions)} questions are '{only}' — a check must mix "
            f"multiple-choice and True/False. The default shape is 3 MCQ and 2 True/False."
        )

    tf_answers = []
    for n, q in enumerate(questions, 1):
        tag = f"{where} / Q{n}"
        qtype = q.get("type")
        tested_objectives.update(q.get("objective_ids", []))

        if qtype not in ("mcq", "true_false"):
            faults.append(f"{tag}: type '{qtype}' is not mcq or true_false")
            continue

        stem = (q.get("stem") or "").strip()
        if not stem:
            faults.append(f"{tag}: no stem")
        elif any(b in stem.lower() for b in BANNED_STEM):
            faults.append(f"{tag}: stem uses a banned construction")
        # Only MCQ: a True/False statement negates as a matter of course ("Order Total is
        # not editable"), and flagging that would make half of every check unwritable. What
        # this catches is the multiple-choice stem asking for the exception.
        if qtype == "mcq" and NEGATIVE_STEM_RE.search(stem):
            faults.append(
                f"{tag}: negative stem — asking which option is NOT true tests careful "
                f"reading rather than whether they can do the task. Rewrite it positively."
            )

        if qtype == "mcq":
            options = q.get("options") or []
            if not 3 <= len(options) <= 4:
                faults.append(f"{tag}: {len(options)} option(s) — an MCQ takes 3 or 4")
            idx = q.get("answer_index")
            if not isinstance(idx, int) or not 0 <= idx < len(options):
                faults.append(f"{tag}: answer_index {idx!r} is not one of its options")
            if "answer" in q:
                faults.append(f"{tag}: MCQ carries a boolean 'answer' — use answer_index")
            for option in options:
                if any(b in str(option).lower() for b in BANNED_STEM):
                    faults.append(f"{tag}: option uses a banned construction")
            if len(set(str(o).strip().lower() for o in options)) != len(options):
                faults.append(f"{tag}: duplicate options — a distractor repeats the answer")
        else:
            if not isinstance(q.get("answer"), bool):
                faults.append(f"{tag}: True/False needs a boolean 'answer'")
            else:
                tf_answers.append(q["answer"])
            if q.get("options"):
                faults.append(f"{tag}: True/False carries options — it has exactly two")
            if "answer_index" in q:
                faults.append(f"{tag}: True/False carries answer_index — use 'answer'")

        if not (q.get("rationale") or "").strip():
            faults.append(f"{tag}: no rationale — the trainer needs to be able to explain it")
        if not q.get("sources"):
            faults.append(
                f"{tag}: no source anchor. A question whose answer is not in the documents "
                f"is not asked — there is no [GAP] escape hatch for a question."
            )
        for anchor in q.get("sources", []):
            if anchor not in anchors:
                faults.append(f"{tag}: source '{anchor}' is not an anchor in the index")

    if len(tf_answers) >= 2 and len(set(tf_answers)) == 1:
        faults.append(
            f"{where}: every True/False answer is {str(tf_answers[0]).upper()} — the set is "
            f"guessable. Aim for roughly half false."
        )
    return faults


# --- report ----------------------------------------------------------------


def render(result, plan, index):
    hard_fail = bool(
        result["uncovered_objectives"] or result["untested_objectives"]
        or result["missing_provenance"] or result["unplaced_assets"]
        or result["question_faults"] or result["unknown_anchors"]
        or result["unknown_objectives"] or result["unknown_topics"]
        or result["unknown_assets"]
    )
    objectives = result["objectives"]
    slide_count = sum(len(m.get("slides", [])) for m in plan.get("modules", []))

    lines = [
        f"# Training QA Report — {plan.get('run_id', 'unnamed run')}",
        "",
        f"**Status:** {'FAIL — must fix before handover' if hard_fail else 'PASS (mechanical checks)'}",
        "",
        f"{plan.get('course_title', 'Untitled course')} · {len(plan.get('modules', []))} modules · "
        f"{slide_count} slides · {result['check_count']} knowledge check(s) · "
        f"{result['question_count']} questions",
        "",
        "## 1. Learning-objective coverage",
        "",
        f"{len(objectives) - len(result['uncovered_objectives'])} of {len(objectives)} "
        f"objectives reach a module; "
        f"{len(objectives) - len(result['untested_objectives'])} of {len(objectives)} "
        f"are tested by a question.",
        "",
    ]

    if result["uncovered_objectives"]:
        lines += ["### FAIL — objectives no module covers", ""]
        lines += [f"- `{oid}` — {objectives[oid]['text']}" for oid in result["uncovered_objectives"]]
        lines += [""]
    if result["untested_objectives"]:
        lines += [
            "### FAIL — objectives no question tests",
            "",
            "An objective the deck teaches but never checks is one nobody finds out they "
            "missed.",
            "",
        ]
        lines += [f"- `{oid}` — {objectives[oid]['text']}" for oid in result["untested_objectives"]]
        lines += [""]
    if result["unknown_objectives"]:
        lines += ["### Objective IDs referenced but not defined", ""]
        lines += [f"- `{oid}`" for oid in result["unknown_objectives"]] + [""]
    if not (result["uncovered_objectives"] or result["untested_objectives"]
            or result["unknown_objectives"]):
        lines += ["Every objective is both taught and tested.", ""]

    lines += [
        "> Mapping is necessary but not sufficient: confirm each mapped slide actually",
        "> teaches the objective, rather than mentioning the topic.",
        "",
        "## 2. Topic coverage",
        "",
    ]
    in_scope = [t for t in result["topics"].values() if t.get("in_scope", True)]
    lines += [
        f"{len(in_scope) - len(result['uncovered_topics'])} of {len(in_scope)} in-scope "
        f"topics are taught or deliberately deferred.",
        "",
    ]
    if result["uncovered_topics"]:
        lines += ["### FAIL — in-scope topics neither taught nor deferred", ""]
        for topic in result["uncovered_topics"]:
            lines.append(f"- `{topic['id']}` {topic['title']} — `{topic['anchor']}` "
                         f"({topic['word_count']} words)")
        lines += ["", "Teach each one, or add it to `deferred_topics` with a reason.", ""]
    if result["deferred"]:
        lines += [f"### Deferred ({len(result['deferred'])})", ""]
        lines += [f"- `{d['topic_id']}` — {d['reason']}" for d in result["deferred"]] + [""]
    if result["unknown_topics"]:
        lines += ["### Topic IDs referenced by the plan but absent from the index", ""]
        lines += [f"- `{t}`" for t in result["unknown_topics"]] + [""]

    lines += ["## 3. Provenance", ""]
    if result["missing_provenance"]:
        lines += [
            "### FAIL — blocks with neither sources nor a [GAP] marker",
            "",
            "Every block traces to a document anchor or is flagged as a gap. Unattributed "
            "content cannot be told apart from something we made up, and a made-up business "
            "rule becomes a wrong transaction.",
            "",
        ] + [f"- {w}" for w in result["missing_provenance"]] + [""]
    else:
        lines += ["Every content block carries source anchors or a `[GAP]` marker.", ""]

    if result["unknown_anchors"]:
        lines += [
            "### FAIL — cited anchors that are not in the source index",
            "",
            "A citation that does not resolve is worse than none: it looks checked.",
            "",
        ]
        lines += [f"- {u['where']} cites `{u['anchor']}`" for u in result["unknown_anchors"]]
        lines += [""]

    lines += [f"### Open gaps ({len(result['gaps'])})", ""]
    if result["gaps"]:
        lines += ["Action items before this deck is used:", ""]
        for gap in result["gaps"]:
            exposed = ", ".join(gap["objective_ids"]) or "none mapped"
            lines += [f"- **{gap['where']}** — {gap['note']}",
                      f"  - Leaves exposed: {exposed}", ""]
        lines += [
            "> A `[GAP]` on a business rule means the specification does not say. That is",
            "> a question for the process owner, not a sentence for us to write.",
            "",
        ]
    else:
        lines += ["None. Every planned block drew on the source documents.", ""]

    lines += ["## 4. Screenshot and diagram triage", ""]
    placeable = [a for a in index.get("assets", []) if a["asset_kind"] in PLACEMENT_KINDS]
    excluded = plan.get("excluded_assets", [])
    lines += [
        f"{len(placeable)} placement-class image(s) in the documents; "
        f"{len(placeable) - len(result['unplaced_assets'])} placed or excluded with a reason.",
        "",
    ]
    if result["unplaced_assets"]:
        lines += [
            "### FAIL — images the documents contain that the deck neither uses nor dismisses",
            "",
        ]
        for asset in result["unplaced_assets"]:
            caption = asset.get("caption") or asset.get("alt_text") or "(no caption)"
            lines.append(f"- `{asset['asset_id']}` ({asset['asset_kind']}, "
                         f"{asset.get('width_px')}x{asset.get('height_px')}) — {caption}")
            lines.append(f"  - from `{asset['anchor']}`")
        lines += ["", "Place each one, or add it to `excluded_assets` with a reason.", ""]
    if excluded:
        lines += [f"### Excluded ({len(excluded)})", ""]
        lines += [f"- `{e['asset_id']}` — {e['reason']}" for e in excluded] + [""]
    if result["unknown_assets"]:
        lines += ["### FAIL — slides placing assets the index does not have", ""]
        lines += [f"- {u['where']} places `{u['asset_id']}`" for u in result["unknown_assets"]]
        lines += [""]
    if result["unusable_assets"]:
        lines += [
            "### Warning — placed images that may not be legible at slide size",
            "",
        ]
        for asset in result["unusable_assets"]:
            lines.append(f"- `{asset['asset_id']}` is {asset['width_px']}px wide. Blown up to "
                         f"a slide it will be soft. Recapture it, or use it small with the "
                         f"detail in the steps beside it.")
        lines += [""]
    if not placeable:
        docs_without = [d for d in index.get("documents", []) if not d["images_extracted"]]
        if docs_without:
            lines += [
                "No images were extracted — note that "
                + ", ".join(f"`{d['path']}`" for d in docs_without)
                + " were read text-only, so this is not evidence they contain none.",
                "",
            ]

    lines += ["## 5. Knowledge-check integrity", ""]
    lines += [
        f"{result['check_count']} check(s), {result['question_count']} question(s). "
        f"Every check must carry exactly 5, mixing multiple-choice and True/False.",
        "",
    ]
    if result["question_faults"]:
        lines += ["### FAIL", ""] + [f"- {f}" for f in result["question_faults"]] + [""]
    else:
        lines += ["Every check is well formed and every answer traces to the documents.", ""]

    budget = plan.get("slide_budget", {})
    if budget.get("cut_for_length"):
        lines += [
            "## Cut for length", "",
            f"Slide limit {budget.get('limit')}; planned {budget.get('planned')}. Dropped:",
            "",
        ] + [f"- {s}" for s in budget["cut_for_length"]] + [""]

    kind = plan.get("template", {}).get("kind")
    if kind != "pptx":
        lines += [
            "## 6. Deck health (run against the rendered .html)",
            "",
            "- [ ] open the deck and step through every slide — arrow keys or space",
            "- [ ] **text overflow** — the most common defect; `.slide-body` clips rather than",
            "      spilling, so an overflowing slide loses content silently. Check the bottom of",
            "      every knowledge check and every business-rules table first.",
            "- [ ] **every screenshot is legible at full size** — field labels readable, not soft",
            "- [ ] **screen labels match the system verbatim** — a field renamed between spec",
            "      and deck is a support ticket on day one",
            "- [ ] every diagram rendered (not showing its Mermaid source panel)",
            "- [ ] no answer key visible on any slide — only in the speaker notes",
            "- [ ] leftover placeholder text (`lorem`, `[insert`, `xxx`, `TODO`)",
            "- [ ] every `[GAP]` panel reads as an action, not as content",
            "- [ ] participant copy re-rendered with `--answers hidden --sources hidden`",
            "",
            "> The HTML path is the PoC renderer on a generic template. If the client expects",
            "> material on their own training template, that is the .pptx path and it needs",
            "> their .potx.",
            "",
        ]
    else:
        lines += [
            "## 6. Deck health (run against the built .pptx via the pptx skill)",
            "",
            "- [ ] `markitdown training.pptx` — content order, typos, missing content",
            "- [ ] placeholder grep for leftover template text (`lorem`, `[insert`, `xxx`, `TODO`)",
            "- [ ] `validate.py training.pptx --original <approved-template>` — always pass `--original`",
            "- [ ] visual QA on rendered slides — overflow, overlap, margins",
            "- [ ] every screenshot inserted at its original resolution and legible",
            "- [ ] every diagram present as an image (render_diagram.py ran)",
            "- [ ] answer keys in the notes pane only, never on a slide",
            "- [ ] template fidelity — fonts, colours and layouts still the client's",
            "",
        ]

    lines += [
        "## Handover",
        "",
        "This is a **first draft for the trainer to review**, not material to put in front of "
        "learners. Two things need a human before it is used: every business rule checked "
        "against the specification, and every screenshot checked against the build learners "
        "will actually see.",
    ]
    if plan.get("release"):
        lines += ["", f"**Written against release: {plan['release']}.** Screenshots and rules "
                      f"go stale as the system moves."]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("index", type=Path)
    ap.add_argument("plan", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("qa_report.md"))
    args = ap.parse_args()

    index = json.loads(args.index.read_text(encoding="utf-8"))
    plan = json.loads(args.plan.read_text(encoding="utf-8"))

    result = audit(index, plan)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(result, plan, index), encoding="utf-8")

    objectives = result["objectives"]
    print(f"Objectives: {len(objectives) - len(result['uncovered_objectives'])}"
          f"/{len(objectives)} covered, "
          f"{len(objectives) - len(result['untested_objectives'])}/{len(objectives)} tested")
    print(f"Gaps: {len(result['gaps'])}   Unattributed blocks: {len(result['missing_provenance'])}")
    print(f"Checks: {result['check_count']} ({result['question_count']} questions)   "
          f"Question faults: {len(result['question_faults'])}")
    print(f"Report -> {args.out}")

    failures = [
        (result["uncovered_objectives"], "objective(s) no module covers"),
        (result["untested_objectives"], "objective(s) no question tests"),
        (result["uncovered_topics"], "in-scope topic(s) neither taught nor deferred"),
        (result["missing_provenance"], "block(s) without sources or [GAP]"),
        (result["unknown_anchors"], "citation(s) that do not resolve to the index"),
        (result["unplaced_assets"], "image(s) neither placed nor excluded"),
        (result["unknown_assets"], "slide(s) placing an asset the index lacks"),
        (result["unknown_objectives"], "undefined objective ID(s) referenced"),
        (result["unknown_topics"], "topic ID(s) absent from the index"),
        (result["question_faults"], "knowledge-check fault(s)"),
    ]
    failed = False
    for items, label in failures:
        if items:
            print(f"FAIL: {len(items)} {label}", file=sys.stderr)
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
