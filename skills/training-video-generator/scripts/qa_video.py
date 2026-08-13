#!/usr/bin/env python3
"""Stage 4 audit: does the narration actually match the recording?

    python qa_video.py capture_map.json video_script.json -o qa_report.md
    python qa_video.py --self-test

Four checks, all mechanical, none of which should be done by eye:

  1. Screen provenance — every narrated scene traces to a keyframe someone actually read,
     or is flagged [GAP]. There is no third state.
  2. Scene coverage — scenes tile the recording, kept footage is narrated, dropped footage
     has a stated reason.
  3. Fit — narration inside its word budget (delegated to fit_narration.py, not reimplemented).
  4. Consistency — objectives covered, glossary respected, annotations on-canvas and clear
     of the avatar.

Exits non-zero on any hard failure. The instructional-design pass — objective quality,
sequencing, assessment fit — belongs to the training-qa-agent skill and is not duplicated
here; this script only checks what can be checked mechanically.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fit_narration import check as fit_check  # noqa: E402

TILING_TOLERANCE = 0.05  # seconds
# Where a corner avatar sits, as fractions of the frame. Matches the Synthesia template
# described in reference/synthesia-build.md; override if the template changes.
AVATAR_MARGIN = 0.03
AVATAR_WIDTH = 0.25
AVATAR_HEIGHT = 0.35


def avatar_rect(position, width=AVATAR_WIDTH, height=AVATAR_HEIGHT, margin=AVATAR_MARGIN):
    """(x, y, w, h) in frame fractions for a named avatar position."""
    if position == "fullscreen":
        return (0.0, 0.0, 1.0, 1.0)
    right = "right" in (position or "bottom-right")
    bottom = "bottom" in (position or "bottom-right")
    x = 1.0 - margin - width if right else margin
    y = 1.0 - margin - height if bottom else margin
    return (x, y, width, height)


def rects_overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)


def check_provenance(capture_map, script):
    """Invariant 1 — narration only over screens someone looked at."""
    findings = []
    capture_by_id = {s.get("scene_id"): s for s in capture_map.get("scenes", [])}

    for scene in script.get("scenes", []):
        scene_id = scene.get("scene_id", "?")
        if scene.get("gap") or scene.get("silent"):
            continue
        if not (scene.get("narration") or "").strip():
            continue

        frame_ref = scene.get("capture", {}).get("frame_ref")
        if not frame_ref:
            findings.append(
                f"{scene_id}: narrated but has no frame_ref, and is not marked gap"
            )
            continue

        source = capture_by_id.get(scene_id)
        if source is None:
            findings.append(f"{scene_id}: not present in the capture map")
        elif source.get("read_status") != "read":
            findings.append(
                f"{scene_id}: narrated over a keyframe still marked "
                f"'{source.get('read_status', 'unread')}' — the frame was never read"
            )
    return findings


def check_coverage(capture_map, script):
    """Invariant 2 — nothing recorded vanishes silently, nothing kept goes unnarrated."""
    findings = []
    scenes = capture_map.get("scenes", [])
    duration = capture_map.get("source", {}).get("duration")

    ordered = sorted(scenes, key=lambda s: s.get("in", 0))
    cursor = 0.0
    for scene in ordered:
        start, end = float(scene.get("in", 0)), float(scene.get("out", 0))
        if abs(start - cursor) > TILING_TOLERANCE:
            gap = start - cursor
            findings.append(
                f"{scene.get('scene_id')}: {'gap' if gap > 0 else 'overlap'} of "
                f"{abs(gap):.2f}s at {cursor:.2f}s — scenes must tile the recording"
            )
        cursor = end

    if duration and abs(cursor - float(duration)) > TILING_TOLERANCE:
        findings.append(
            f"scenes end at {cursor:.2f}s but the recording is {duration}s — "
            f"{float(duration) - cursor:.2f}s unaccounted for"
        )

    for scene in scenes:
        disposition = scene.get("disposition", "keep")
        if disposition != "keep" and not (scene.get("disposition_note") or "").strip():
            findings.append(
                f"{scene.get('scene_id')}: '{disposition}' without a disposition_note — "
                f"footage is not dropped without a stated reason"
            )

    scripted = {s.get("scene_id") for s in script.get("scenes", [])}
    for scene in scenes:
        # 'accelerate' footage still appears in the finished video, so it needs a scene in
        # the script (usually silent) just as much as 'keep' does. Only 'cut' is exempt.
        disposition = scene.get("disposition", "keep")
        if disposition in ("keep", "accelerate") and scene.get("scene_id") not in scripted:
            findings.append(
                f"{scene.get('scene_id')}: {disposition} in the capture map but absent "
                f"from the script"
            )

    captured = {s.get("scene_id") for s in scenes}
    for scene_id in scripted - captured:
        findings.append(f"{scene_id}: in the script but not in the capture map")

    return findings


def check_consistency(script, frame_width=None):
    """Invariant 4 — objectives, terminology, and annotation geometry."""
    findings, warnings = [], []
    scenes = script.get("scenes", [])

    declared = {o.get("id") for o in script.get("objectives", [])}
    referenced = set()
    for scene in scenes:
        referenced.update(scene.get("objective_ids") or [])

    for objective_id in sorted(declared - referenced):
        findings.append(
            f"objective {objective_id} is declared but no scene teaches it"
        )
    for objective_id in sorted(referenced - declared):
        findings.append(f"scene references undeclared objective {objective_id}")

    for scene in scenes:
        if scene.get("role") == "step" and not (scene.get("objective_ids") or []):
            warnings.append(
                f"{scene.get('scene_id')}: step scene maps to no objective"
            )

    # Terminology: an 'avoid' term anywhere in learner-facing text is a defect, because
    # inconsistent naming is the commonest and least-noticed failure in system training.
    for entry in script.get("glossary", []) or []:
        for avoid in entry.get("avoid", []) or []:
            pattern = re.compile(rf"\b{re.escape(avoid)}\b", re.IGNORECASE)
            for scene in scenes:
                texts = [scene.get("narration") or ""]
                texts += [a.get("text") or "" for a in scene.get("annotations") or []]
                if any(pattern.search(t) for t in texts):
                    findings.append(
                        f"{scene.get('scene_id')}: uses {avoid!r}; the glossary fixes "
                        f"this as {entry.get('use')!r}"
                    )

    for scene in scenes:
        scene_id = scene.get("scene_id", "?")
        avatar = scene.get("avatar", {})
        avatar_box = (
            avatar_rect(avatar.get("position", "bottom-right"))
            if avatar.get("visible")
            else None
        )

        for i, annotation in enumerate(scene.get("annotations") or []):
            rect = annotation.get("rect")
            anchor = annotation.get("anchor")

            if rect:
                x, y, w, h = rect
                if x < 0 or y < 0 or x + w > 1.0001 or y + h > 1.0001:
                    findings.append(
                        f"{scene_id}: annotation {i} extends off-canvas "
                        f"(x={x:.2f} y={y:.2f} w={w:.2f} h={h:.2f})"
                    )
                elif avatar_box and rects_overlap(rect, avatar_box):
                    findings.append(
                        f"{scene_id}: annotation {i} sits under the avatar — "
                        f"move it or hide the avatar for this scene"
                    )

            if anchor:
                x, y = anchor
                if not (0 <= x <= 1 and 0 <= y <= 1):
                    findings.append(
                        f"{scene_id}: annotation {i} anchor is off-canvas ({x:.2f}, {y:.2f})"
                    )
                elif avatar_box and rects_overlap((x, y, 0.001, 0.001), avatar_box):
                    findings.append(
                        f"{scene_id}: annotation {i} points into the avatar"
                    )

            if annotation.get("type") == "highlight" and not rect:
                findings.append(f"{scene_id}: highlight annotation {i} has no rect")
            if annotation.get("type") in ("callout", "step_counter", "lower_third") and not (
                annotation.get("text") or ""
            ).strip():
                findings.append(
                    f"{scene_id}: {annotation.get('type')} annotation {i} has no text"
                )

        highlights = sum(
            1 for a in scene.get("annotations") or [] if a.get("type") == "highlight"
        )
        if highlights > 1:
            warnings.append(
                f"{scene_id}: {highlights} highlights in one scene — the learner will not "
                f"know where to look"
            )

    return findings, warnings


def audit(capture_map, script):
    provenance = check_provenance(capture_map, script)
    coverage = check_coverage(capture_map, script)
    fit = fit_check(script)
    consistency, consistency_warnings = check_consistency(script)

    fit_failures = [m for sev, m in fit["findings"] if sev == "fail"]
    fit_warnings = [m for sev, m in fit["findings"] if sev == "warn"]

    return {
        "provenance": provenance,
        "coverage": coverage,
        "fit": fit_failures,
        "consistency": consistency,
        "warnings": fit_warnings + consistency_warnings,
        "fit_detail": fit,
        "hard_fail": bool(provenance or coverage or fit_failures or consistency),
    }


def render(result, script):
    module = script.get("module", {})
    fit = result["fit_detail"]
    minutes, seconds = divmod(fit["total_duration"], 60)

    lines = [
        f"# QA Report — {module.get('title', 'untitled module')}",
        "",
        f"**Status:** {'FAIL — fix before handover' if result['hard_fail'] else 'PASS (mechanical checks)'}",
        "",
        f"{len(script.get('scenes', []))} scenes, {int(minutes)}m {seconds:04.1f}s runtime.",
        "",
    ]

    sections = [
        (
            "1. Screen provenance",
            result["provenance"],
            "Every narrated scene traces to a keyframe that was actually read, or is "
            "flagged `[GAP]`.",
        ),
        (
            "2. Scene coverage",
            result["coverage"],
            "Scenes tile the recording; kept footage is narrated; dropped footage has a "
            "stated reason.",
        ),
        (
            "3. Fit",
            result["fit"],
            "Narration sits inside the word budget its scene duration allows.",
        ),
        (
            "4. Consistency",
            result["consistency"],
            "Objectives covered, glossary respected, annotations on-canvas and clear of "
            "the avatar.",
        ),
    ]

    for title, findings, blurb in sections:
        lines += [f"## {title}", "", blurb, ""]
        if findings:
            lines.append(f"**{len(findings)} failure(s):**")
            lines.append("")
            lines += [f"- {f}" for f in findings]
        else:
            lines.append("No failures.")
        lines.append("")

    if result["warnings"]:
        lines += ["## Warnings", "", "Judgement calls, not defects:", ""]
        lines += [f"- {w}" for w in result["warnings"]]
        lines.append("")

    gaps = [s for s in script.get("scenes", []) if s.get("gap")]
    if gaps:
        lines += ["## Open [GAP] items", "", "For the consultant to confirm:", ""]
        for scene in gaps:
            lines.append(f"- **{scene.get('scene_id')}** — {scene.get('gap_note', '')}")
        lines.append("")

    lines += [
        "## Not checked here",
        "",
        "Instructional design — objective quality, sequencing, assessment fit — is the "
        "`training-qa-agent` skill's job. Hand it `video_script.json`.",
        "",
        "Factual accuracy about the system is the consultant's. These checks prove the "
        "narration matches the frames; only they can confirm the frames show the right thing.",
        "",
    ]
    return "\n".join(lines)


def self_test():
    failures = []

    def check(name, got, want):
        if got != want:
            failures.append(f"{name}: got {got!r}, want {want!r}")

    br = avatar_rect("bottom-right")
    check("avatar bottom-right", (round(br[0], 2), round(br[1], 2)), (0.72, 0.62))
    check("avatar top-left", (round(avatar_rect("top-left")[0], 2)), 0.03)

    check("overlap yes", rects_overlap((0.7, 0.7, 0.2, 0.2), br), True)
    check("overlap no", rects_overlap((0.1, 0.1, 0.2, 0.2), br), False)

    capture_map = {
        "source": {"duration": 20.0},
        "scenes": [
            {"scene_id": "S01", "in": 0, "out": 10, "duration": 10,
             "disposition": "keep", "read_status": "read", "frame_ref": "frames/S01.png"},
            {"scene_id": "S02", "in": 10, "out": 20, "duration": 10,
             "disposition": "keep", "read_status": "read", "frame_ref": "frames/S02.png"},
        ],
    }
    script = {
        "module": {"title": "T"},
        "objectives": [{"id": "O1", "text": "do the thing"}],
        "scenes": [
            {"scene_id": "S01", "role": "intro", "objective_ids": ["O1"],
             "capture": {"in": 0, "out": 10, "frame_ref": "frames/S01.png"},
             "narration": " ".join(["word"] * 24), "avatar": {"visible": True}},
            {"scene_id": "S02", "role": "step", "objective_ids": ["O1"],
             "capture": {"in": 10, "out": 20, "frame_ref": "frames/S02.png"},
             "narration": " ".join(["word"] * 24), "avatar": {"visible": False}},
        ],
    }

    clean = audit(capture_map, script)
    check("clean run passes", clean["hard_fail"], False)

    # 1. Narration over a frame nobody read.
    unread = json.loads(json.dumps(capture_map))
    unread["scenes"][1]["read_status"] = "unread"
    check("unread frame fails", bool(check_provenance(unread, script)), True)

    # 2a. A hole in the tiling.
    holed = json.loads(json.dumps(capture_map))
    holed["scenes"][1]["in"] = 12
    assert any("gap" in f for f in check_coverage(holed, script))

    # 2b. Dropped footage with no reason.
    unreasoned = json.loads(json.dumps(capture_map))
    unreasoned["scenes"][1]["disposition"] = "cut"
    assert any("disposition_note" in f for f in check_coverage(unreasoned, script))

    # 4a. Annotation parked under a visible avatar.
    collided = json.loads(json.dumps(script))
    collided["scenes"][0]["annotations"] = [
        {"type": "highlight", "rect": [0.75, 0.65, 0.15, 0.2]}
    ]
    assert any("under the avatar" in f for f in check_consistency(collided)[0])

    # ...but the same annotation is fine when the avatar is hidden.
    hidden = json.loads(json.dumps(collided))
    hidden["scenes"][0]["avatar"]["visible"] = False
    check("no collision when hidden", check_consistency(hidden)[0], [])

    # 4b. Off-canvas annotation.
    offscreen = json.loads(json.dumps(script))
    offscreen["scenes"][1]["annotations"] = [
        {"type": "highlight", "rect": [0.9, 0.9, 0.3, 0.3]}
    ]
    assert any("off-canvas" in f for f in check_consistency(offscreen)[0])

    # 4c. Banned terminology.
    drifted = json.loads(json.dumps(script))
    drifted["glossary"] = [{"use": "Purchase Requisition", "avoid": ["PR ticket"]}]
    drifted["scenes"][1]["narration"] = "Open the PR ticket and review it now please today"
    assert any("PR ticket" in f for f in check_consistency(drifted)[0])

    # 4d. An objective nothing teaches.
    orphan = json.loads(json.dumps(script))
    orphan["objectives"].append({"id": "O2", "text": "never taught"})
    assert any("no scene teaches it" in f for f in check_consistency(orphan)[0])

    for f in failures:
        print(f"FAIL  {f}", file=sys.stderr)
    print(f"{'FAILED' if failures else 'passed'}: qa self-test")
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("capture_map", nargs="?", help="capture_map.json")
    parser.add_argument("script", nargs="?", help="video_script.json")
    parser.add_argument("-o", "--output", help="where to write qa_report.md")
    parser.add_argument("--self-test", action="store_true", help="run tests and exit")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if not args.capture_map or not args.script:
        parser.error("capture_map.json and video_script.json are required")

    for path in (args.capture_map, args.script):
        if not Path(path).exists():
            print(f"not found: {path}", file=sys.stderr)
            return 1

    capture_map = json.loads(Path(args.capture_map).read_text())
    script = json.loads(Path(args.script).read_text())

    result = audit(capture_map, script)
    report = render(result, script)

    if args.output:
        Path(args.output).write_text(report)
        print(f"  {args.output}")
    else:
        print(report)

    counts = {k: len(result[k]) for k in ("provenance", "coverage", "fit", "consistency")}
    if result["hard_fail"]:
        print(
            "  FAIL — "
            + ", ".join(f"{k}: {v}" for k, v in counts.items() if v),
            file=sys.stderr,
        )
        return 1
    print(f"  PASS ({len(result['warnings'])} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
