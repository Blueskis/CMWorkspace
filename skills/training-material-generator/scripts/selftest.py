#!/usr/bin/env python3
"""Confirm each invariant actually fails a run, rather than being decorative.

    python skills/training-material-generator/scripts/selftest.py

Takes the worked example in examples/po-training/, breaks it one way at a time, and checks
that the pipeline rejects each break with a message naming it. Run it from the repository
root after touching qa_training.py, build_deck.py, the schemas, or the example.

A guarantee nobody tests is a guarantee nobody has. Every case here corresponds to a way
for wrong or unaccountable material to reach a learner:

  * content on a slide that traces to nothing
  * an objective the deck teaches but never checks
  * a screenshot from the specification that quietly never made it in
  * a knowledge check that is malformed, unbalanced, or unanswerable from the documents
  * a citation that looks checkable and is not
  * a slide planned onto a layout the template does not have

The control case matters as much as the rest: if the unmutated example ever stops passing,
the negative results below prove nothing.

Stdlib only. Exits non-zero if any invariant has stopped being enforced.
"""
import copy, json, subprocess, sys
from pathlib import Path

PLAN = json.loads(Path("examples/po-training/training_plan.json").read_text())
INDEX = "examples/po-training/source_index.json"
PROFILE = "training-assets/templates/html-training/template_profile.json"
TMP = Path("/tmp/po/neg"); TMP.mkdir(parents=True, exist_ok=True)


def module(plan, mid):
    return next(m for m in plan["modules"] if m["module_id"] == mid)


def check_block(plan):
    """The questions block of the first knowledge check."""
    slide = next(s for s in module(plan, "system-walkthrough-create")["slides"]
                 if s["slide_id"] == "create-4")
    return next(b for b in slide["blocks"] if b["kind"] == "questions")


def mutate_unattributed(p):
    module(p, "integrations")["slides"][0]["blocks"][0]["sources"] = []

def mutate_untested_objective(p):
    for b in (check_block(p), check_block(p)):
        for q in b["questions"]:
            q["objective_ids"] = [o for o in q.get("objective_ids", []) if o != "LO3"]
    for m in p["modules"]:
        for s in m.get("slides", []):
            for b in s["blocks"]:
                for q in b.get("questions", []):
                    q["objective_ids"] = [o for o in q.get("objective_ids", []) if o != "LO3"]

def mutate_dropped_screenshot(p):
    slide = next(s for s in module(p, "system-walkthrough-approve")["slides"]
                 if s["slide_id"] == "approve-2")
    slide["blocks"] = [b for b in slide["blocks"] if b["kind"] != "image"]

def mutate_four_questions(p):
    check_block(p)["questions"] = check_block(p)["questions"][:4]

def mutate_six_questions(p):
    b = check_block(p)
    extra = copy.deepcopy(b["questions"][0]); extra["question_id"] = "extra"
    b["questions"] = b["questions"] + [extra]

def mutate_all_mcq(p):
    for q in check_block(p)["questions"]:
        if q["type"] == "true_false":
            q["type"] = "mcq"
            q["options"] = ["True", "False", "It depends on the cost centre"]
            q["answer_index"] = 0
            q.pop("answer", None)

def mutate_two_correct_mcq(p):
    q = next(q for q in check_block(p)["questions"] if q["type"] == "mcq")
    q["answer_index"] = 99

def mutate_tf_three_options(p):
    q = next(q for q in check_block(p)["questions"] if q["type"] == "true_false")
    q["options"] = ["True", "False", "Maybe"]

def mutate_unresolvable_anchor(p):
    module(p, "integrations")["slides"][0]["blocks"][0]["sources"] = ["POFSD#99.9"]

def mutate_uncovered_topic(p):
    module(p, "integrations")["topic_ids"] = []

def mutate_no_rationale(p):
    check_block(p)["questions"][0]["rationale"] = ""

def mutate_bad_layout(p):
    module(p, "integrations")["slides"][0]["layout"] = "hero-banner"


QA_CASES = [
    ("block with neither sources nor gap", mutate_unattributed, "without sources or [GAP]"),
    ("objective taught but never tested", mutate_untested_objective, "no question tests"),
    ("screenshot neither placed nor excluded", mutate_dropped_screenshot, "neither placed nor excluded"),
    ("knowledge check with 4 questions", mutate_four_questions, "knowledge-check fault"),
    ("knowledge check with 6 questions", mutate_six_questions, "knowledge-check fault"),
    ("knowledge check that is all MCQ", mutate_all_mcq, "knowledge-check fault"),
    ("MCQ whose answer_index is not an option", mutate_two_correct_mcq, "knowledge-check fault"),
    ("True/False carrying three options", mutate_tf_three_options, "knowledge-check fault"),
    ("citation that does not resolve", mutate_unresolvable_anchor, "do not resolve"),
    ("in-scope topic neither taught nor deferred", mutate_uncovered_topic, "neither taught nor deferred"),
    ("question with no rationale", mutate_no_rationale, "knowledge-check fault"),
]
BUILD_CASES = [
    ("slide on a layout the template lacks", mutate_bad_layout, "is not in the approved template"),
]


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def main():
    failures = 0

    # Control: the unmutated plan must pass, or the negative tests prove nothing.
    r = run([sys.executable, "skills/training-material-generator/scripts/qa_training.py",
             INDEX, "examples/po-training/training_plan.json", "-o", str(TMP / "control.md")])
    ok = r.returncode == 0
    print(f"{'PASS' if ok else 'FAIL'}  control: the real plan passes QA")
    failures += not ok

    for name, mutate, expect in QA_CASES:
        plan = copy.deepcopy(PLAN)
        mutate(plan)
        path = TMP / "plan.json"
        path.write_text(json.dumps(plan))
        r = run([sys.executable, "skills/training-material-generator/scripts/qa_training.py",
                 INDEX, str(path), "-o", str(TMP / "out.md")])
        caught = r.returncode != 0 and expect in (r.stderr + r.stdout + (TMP / "out.md").read_text())
        print(f"{'PASS' if caught else 'FAIL'}  qa rejects: {name}")
        if not caught:
            print(f"      expected {expect!r}; rc={r.returncode}; stderr={r.stderr.strip()[:200]}")
        failures += not caught

    for name, mutate, expect in BUILD_CASES:
        plan = copy.deepcopy(PLAN)
        mutate(plan)
        path = TMP / "plan.json"
        path.write_text(json.dumps(plan))
        r = run([sys.executable, "skills/training-material-generator/scripts/build_deck.py",
                 str(path), PROFILE, "-o", str(TMP / "manifest.json")])
        caught = r.returncode != 0 and expect in (r.stderr + r.stdout)
        print(f"{'PASS' if caught else 'FAIL'}  build rejects: {name}")
        if not caught:
            print(f"      expected {expect!r}; rc={r.returncode}; stderr={r.stderr.strip()[:200]}")
        failures += not caught

        r = run([sys.executable, "skills/training-material-generator/scripts/render_html.py",
                 str(path), "training-assets/templates/html-training", "-o", str(TMP / "x.html")])
        caught = r.returncode != 0
        print(f"{'PASS' if caught else 'FAIL'}  render rejects: {name}")
        failures += not caught

    print(f"\n{failures} failing negative test(s)" if failures else "\nAll negative tests pass.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
