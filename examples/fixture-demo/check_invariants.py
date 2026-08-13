#!/usr/bin/env python3
"""Break the clean fixture one invariant at a time; every mutation must fail QA.

    python check_invariants.py

A fixture that passes proves very little on its own — a QA script that always returned zero
would pass it too. This mutates the known-good fixture thirteen ways, once per rule the
pipeline claims to enforce, and asserts each one is caught. The control case asserts the
untouched fixture still passes, so a script that failed everything would not pass either.

Run this after changing anything in qa_video.py or fit_narration.py. Stdlib only; no ffmpeg,
no video, no Synthesia account.
"""

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
QA = HERE.parent.parent / "skills" / "training-video-generator" / "scripts" / "qa_video.py"


def scene(doc, scene_id):
    return next(s for s in doc["scenes"] if s["scene_id"] == scene_id)


# Each mutation takes (capture_map, video_script) and breaks exactly one rule.

def unread_frame(cm, vs):
    scene(cm, "S02")["read_status"] = "unread"


def no_frame_ref(cm, vs):
    del scene(vs, "S04")["capture"]["frame_ref"]


def tiling_hole(cm, vs):
    scene(cm, "S04")["in"] = 33.0


def cut_without_reason(cm, vs):
    del scene(cm, "S03")["disposition_note"]


def kept_scene_missing(cm, vs):
    vs["scenes"] = [s for s in vs["scenes"] if s["scene_id"] != "S04"]


def accelerate_scene_missing(cm, vs):
    vs["scenes"] = [s for s in vs["scenes"] if s["scene_id"] != "S05"]


def word_budget_blown(cm, vs):
    scene(vs, "S04")["narration"] = " ".join(["word"] * 80)


def gap_without_note(cm, vs):
    del scene(vs, "S06")["gap_note"]


def silent_scene_with_narration(cm, vs):
    scene(vs, "S05")["narration"] = "This scene claims to be silent."


def annotation_under_avatar(cm, vs):
    scene(vs, "S01")["annotations"].append(
        {"type": "highlight", "target": "x", "rect": [0.75, 0.65, 0.15, 0.2]}
    )


def annotation_off_canvas(cm, vs):
    scene(vs, "S02")["annotations"].append(
        {"type": "highlight", "target": "x", "rect": [0.9, 0.9, 0.3, 0.3]}
    )


def glossary_violation(cm, vs):
    scene(vs, "S04")["narration"] = "Now assign the cost center for this line item please."


def orphan_objective(cm, vs):
    vs["objectives"].append({"id": "O3", "text": "never taught anywhere"})


CASES = [
    ("provenance: narration over a frame nobody read", unread_frame),
    ("provenance: narrated scene with no frame_ref", no_frame_ref),
    ("coverage: hole in the scene tiling", tiling_hole),
    ("coverage: footage cut without a reason", cut_without_reason),
    ("coverage: kept scene absent from the script", kept_scene_missing),
    ("coverage: accelerated scene absent from the script", accelerate_scene_missing),
    ("fit: narration over its word budget", word_budget_blown),
    ("fit: gap flagged without a note", gap_without_note),
    ("fit: silent scene carrying narration", silent_scene_with_narration),
    ("consistency: annotation parked under the avatar", annotation_under_avatar),
    ("consistency: annotation off-canvas", annotation_off_canvas),
    ("consistency: banned glossary term used", glossary_violation),
    ("consistency: objective no scene teaches", orphan_objective),
]


def run_qa(capture_map, script, workdir):
    cm_path = workdir / "capture_map.json"
    vs_path = workdir / "video_script.json"
    cm_path.write_text(json.dumps(capture_map))
    vs_path.write_text(json.dumps(script))
    return subprocess.run(
        [sys.executable, str(QA), str(cm_path), str(vs_path)],
        capture_output=True,
        text=True,
    ).returncode


def main():
    base_cm = json.loads((HERE / "capture_map.json").read_text())
    base_vs = json.loads((HERE / "video_script.json").read_text())
    failures = []

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)

        if run_qa(base_cm, base_vs, workdir) != 0:
            failures.append("control: the clean fixture should pass, but QA failed it")
            print("  FAIL  control (clean fixture passes)")
        else:
            print("  ok    control (clean fixture passes)")

        for name, mutate in CASES:
            cm, vs = copy.deepcopy(base_cm), copy.deepcopy(base_vs)
            mutate(cm, vs)
            caught = run_qa(cm, vs, workdir) != 0
            if not caught:
                failures.append(f"{name}: mutation was NOT caught")
            print(f"  {'ok  ' if caught else 'FAIL'}  {name}")

    print()
    if failures:
        for failure in failures:
            print(f"FAILED: {failure}", file=sys.stderr)
        return 1
    print(f"all {len(CASES)} invariant breaches caught")
    return 0


if __name__ == "__main__":
    sys.exit(main())
