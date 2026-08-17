#!/usr/bin/env python3
"""Check that every scene's narration fits the footage it plays over.

    python fit_narration.py video_script.json
    python fit_narration.py video_script.json --update      # write budgets back into the file
    python fit_narration.py video_script.json --json        # machine-readable
    python fit_narration.py --self-test

Synthesia gives coarse control over timing inside a scene, so voice and screen are kept in
step by writing narration to a word budget derived from the scene's measured duration rather
than by nudging clips afterwards. That makes overrun a mechanical defect, not a matter of
taste, and this is where it gets caught — before anyone opens the editor and starts spending
render credits.

Hard failures (exit 1):
  * narration longer than the scene can carry at the slow end of the band
  * an annotation nobody can read in the time the scene is on screen

Warnings (exit 0): narration well under budget, and a module over its target runtime. Both
are judgement calls for the practitioner, not defects.
"""

import argparse
import json
import sys
from pathlib import Path

DEFAULT_WPM_BAND = (130.0, 165.0)
DEFAULT_MODE = "cleaned-verbatim"
# Reading speed for on-screen text, plus a floor so a two-word callout still registers.
SECONDS_PER_ANNOTATION_WORD = 0.4
MIN_ANNOTATION_SECONDS = 1.5
# Below this fraction of the minimum budget, a scene is carrying conspicuous dead air.
# Cleaned-verbatim narration is expected to come in short — stripping fillers removes real
# words — so it is held to a looser floor than freshly composed narration.
UNDERRUN_FRACTION = {"cleaned-verbatim": 0.35, "rewritten": 0.5}
# Fidelity bounds for cleaned-verbatim: below the floor the "clean" has become a rewrite,
# above the ceiling words have been added that the consultant never said.
RETENTION_FLOOR = 0.55
RETENTION_CEILING = 1.15


def word_count(text):
    return len(str(text or "").split())


def speech_seconds(words, wpm):
    """How long the avatar will take to say this many words at a given pace."""
    return round(words * 60.0 / wpm, 2) if wpm else 0.0


def budget_for(duration, wpm_band=DEFAULT_WPM_BAND):
    """Words a scene of this duration can carry, slowest and fastest acceptable pace.

    Slower speech fits fewer words, so the low end of the wpm band gives the *minimum*
    of the range and the high end gives the maximum a scene can take before it rushes.
    """
    low, high = wpm_band
    return (int(duration * low / 60), int(duration * high / 60))


def check_scene(scene, wpm_band=DEFAULT_WPM_BAND, mode=DEFAULT_MODE):
    """Return (findings, words, budget) for one scene. Findings are (severity, message)."""
    findings = []
    capture = scene.get("capture", {})
    duration = round(float(capture.get("out", 0)) - float(capture.get("in", 0)), 3)
    scene_id = scene.get("scene_id", "?")

    if duration <= 0:
        return [("fail", f"{scene_id}: scene has no duration (in >= out)")], 0, (0, 0)

    budget = budget_for(duration, wpm_band)
    words = word_count(scene.get("narration"))

    if scene.get("silent"):
        if words:
            findings.append(
                ("fail", f"{scene_id}: marked silent but carries {words} words of narration")
            )
        return findings, words, budget

    if scene.get("gap"):
        # A gap is an open question for the consultant, so its narration is a placeholder
        # and is not expected to fit anything yet.
        if not scene.get("gap_note"):
            findings.append(("fail", f"{scene_id}: gap is set but gap_note is missing"))
        return findings, words, budget

    if words == 0:
        findings.append(
            ("fail", f"{scene_id}: no narration, and not marked silent or gap")
        )
        return findings, words, budget

    if words > budget[1]:
        over = words - budget[1]
        extension = round(speech_seconds(words, wpm_band[1]) - duration, 1)

        if mode == "cleaned-verbatim":
            # Expected, not a defect. Casual speech runs near 190 wpm; the avatar delivers
            # at a training pace, so faithfully kept words routinely need more time than the
            # footage. Synthesia's scene length follows the script, so the fix is to hold the
            # last frame — the consultant's words are the fixed side of the equation.
            # It only becomes a failure when the shortfall is large enough that holding a
            # still would be conspicuous, which means the scene boundary is in the wrong place.
            if extension <= duration * 0.5:
                findings.append(
                    (
                        "warn",
                        f"{scene_id}: {words} words needs ~{extension}s more than the "
                        f"{duration}s of footage — hold the last frame",
                    )
                )
            else:
                findings.append(
                    (
                        "fail",
                        f"{scene_id}: {words} words needs ~{extension}s more than the "
                        f"{duration}s of footage — too much to hold a still for; re-cut the "
                        f"scene boundary or split the scene",
                    )
                )
        else:
            findings.append(
                (
                    "fail",
                    f"{scene_id}: {words} words needs longer than the {duration}s of footage "
                    f"(budget {budget[0]}-{budget[1]}); cut {over} "
                    f"word{'s' if over != 1 else ''}",
                )
            )
    elif words < budget[0] * UNDERRUN_FRACTION.get(mode, 0.5):
        findings.append(
            (
                "warn",
                f"{scene_id}: {words} words over {duration}s leaves dead air — "
                f"budget is {budget[0]}-{budget[1]}; trim the clip or let the scene breathe",
            )
        )

    if mode == "cleaned-verbatim":
        source = scene.get("source_excerpt")
        if source is None:
            findings.append(
                (
                    "fail",
                    f"{scene_id}: cleaned-verbatim mode needs source_excerpt — without the "
                    f"consultant's actual words there is nothing to verify the clean against",
                )
            )
        else:
            source_words = word_count(source)
            if source_words:
                retention = words / source_words
                if retention < RETENTION_FLOOR:
                    findings.append(
                        (
                            "warn",
                            f"{scene_id}: only {retention:.0%} of the consultant's "
                            f"{source_words} words survive — that is a rewrite, not a clean",
                        )
                    )
                elif retention > RETENTION_CEILING:
                    findings.append(
                        (
                            "warn",
                            f"{scene_id}: narration is {retention:.0%} of what was said — "
                            f"words have been added that the consultant did not say",
                        )
                    )

    for i, annotation in enumerate(scene.get("annotations") or []):
        text = annotation.get("text")
        if not text:
            continue
        needed = max(
            MIN_ANNOTATION_SECONDS, word_count(text) * SECONDS_PER_ANNOTATION_WORD
        )
        if needed > duration:
            findings.append(
                (
                    "fail",
                    f"{scene_id}: annotation {i} ({text!r}) needs {needed:.1f}s to read "
                    f"but the scene is only {duration}s",
                )
            )

    return findings, words, budget


def check(script):
    wpm_band = tuple(script.get("wpm_band") or DEFAULT_WPM_BAND)
    mode = script.get("fidelity_mode") or DEFAULT_MODE
    rows, findings = [], []
    total_duration = 0.0

    if mode == "cleaned-verbatim" and not script.get("guide_transcript"):
        findings.append(
            (
                "warn",
                "cleaned-verbatim mode without a guide_transcript — fidelity is being "
                "asserted rather than checked",
            )
        )

    footage_total = 0.0
    midpoint_wpm = sum(wpm_band) / 2

    for scene in script.get("scenes", []):
        scene_findings, words, budget = check_scene(scene, wpm_band, mode)
        findings.extend(scene_findings)
        capture = scene.get("capture", {})
        duration = max(
            round(float(capture.get("out", 0)) - float(capture.get("in", 0)), 3), 0
        )
        # Synthesia's scene length follows the script, so a scene runs for however long the
        # narration takes if that is longer than the clip. Budgeting credits against the raw
        # footage would understate the bill on every scene that holds a frame.
        speech = 0.0 if scene.get("silent") or scene.get("gap") else speech_seconds(
            words, midpoint_wpm
        )
        built = round(max(duration, speech), 2)

        footage_total += duration
        total_duration += built
        rows.append(
            {
                "scene_id": scene.get("scene_id", "?"),
                "duration": duration,
                "speech": speech,
                "built": built,
                "words": words,
                "budget": list(budget),
                "role": scene.get("role"),
            }
        )

    target = script.get("module", {}).get("target_runtime")
    if target and total_duration > target:
        findings.append(
            (
                "warn",
                f"module runtime {total_duration:.1f}s exceeds target {target}s — "
                f"split it before building, not after the credits are spent",
            )
        )

    return {
        "scenes": rows,
        "findings": findings,
        "total_duration": round(total_duration, 3),
        "footage_duration": round(footage_total, 3),
        "wpm_band": list(wpm_band),
        "fidelity_mode": mode,
        "target_runtime": target,
    }


def render(result):
    lines = [
        f"{'scene':6} {'role':10} {'clip':>6} {'speech':>7} {'built':>7} "
        f"{'words':>6} {'budget':>9}",
        "-" * 56,
    ]
    for row in result["scenes"]:
        budget = f"{row['budget'][0]}-{row['budget'][1]}"
        held = "+" if row["built"] > row["duration"] + 0.05 else " "
        lines.append(
            f"{row['scene_id']:6} {str(row['role'] or ''):10} "
            f"{row['duration']:>6.1f} {row['speech']:>7.1f} {row['built']:>6.1f}{held} "
            f"{row['words']:>6} {budget:>9}"
        )

    minutes, seconds = divmod(result["total_duration"], 60)
    footage_m, footage_s = divmod(result.get("footage_duration", 0), 60)
    lines.append("")
    lines.append(
        f"{len(result['scenes'])} scenes at "
        f"{result['wpm_band'][0]:g}-{result['wpm_band'][1]:g} wpm "
        f"({result.get('fidelity_mode', DEFAULT_MODE)})"
    )
    lines.append(
        f"footage {int(footage_m)}m {footage_s:04.1f}s  →  "
        f"built video {int(minutes)}m {seconds:04.1f}s "
        f"({result['total_duration'] * 2:.0f} Synthesia credits)"
    )
    if result["total_duration"] > result.get("footage_duration", 0) + 0.5:
        lines.append(
            "  '+' marks scenes that hold the last frame while narration finishes."
        )

    fails = [m for sev, m in result["findings"] if sev == "fail"]
    warns = [m for sev, m in result["findings"] if sev == "warn"]

    if warns:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"  - {m}" for m in warns)
    if fails:
        lines.append("")
        lines.append("Failures:")
        lines.extend(f"  - {m}" for m in fails)
    if not fails:
        lines.append("")
        lines.append("Fit check passed." if not warns else "Fit check passed with warnings.")

    return "\n".join(lines)


def self_test():
    failures = []

    def check_eq(name, got, want):
        if got != want:
            failures.append(f"{name}: got {got!r}, want {want!r}")

    check_eq("budget 60s", budget_for(60.0), (130, 165))
    check_eq("budget 7.7s", budget_for(7.7), (16, 21))

    R = "rewritten"  # mode where narration is composed, so no source_excerpt is expected

    over = {
        "scene_id": "S01",
        "capture": {"in": 0, "out": 5},
        "narration": " ".join(["word"] * 40),
    }
    findings, words, _ = check_scene(over, mode=R)
    check_eq("overrun words", words, 40)
    check_eq("overrun fails", [s for s, _ in findings], ["fail"])
    assert "cut 27 words" in findings[0][1], findings[0][1]

    # Cleaned-verbatim, modest overrun: expected, so warn and hold the frame — the footage
    # moves, never the consultant's words.
    mild = {
        "scene_id": "S01b",
        "capture": {"in": 0, "out": 20},
        "narration": " ".join(["word"] * 60),
        "source_excerpt": " ".join(["word"] * 66),
    }
    mild_findings = check_scene(mild)[0]
    check_eq("mild verbatim overrun warns", [s for s, _ in mild_findings], ["warn"])
    assert "hold the last frame" in mild_findings[0][1], mild_findings
    assert not any("cut " in m for _, m in mild_findings)

    # Cleaned-verbatim, extreme overrun: holding a still that long would be conspicuous,
    # so the scene boundary is wrong, not the narration.
    extreme = dict(over, source_excerpt=" ".join(["word"] * 44))
    extreme_findings = check_scene(extreme)[0]
    check_eq("extreme verbatim overrun fails", [s for s, _ in extreme_findings], ["fail"])
    assert "re-cut the scene boundary" in extreme_findings[0][1], extreme_findings

    ok = {
        "scene_id": "S02",
        "capture": {"in": 0, "out": 8},
        "narration": " ".join(["word"] * 18),
    }
    check_eq("in-budget clean", check_scene(ok, mode=R)[0], [])

    silent = {"scene_id": "S03", "capture": {"in": 0, "out": 3}, "silent": True}
    check_eq("silent clean", check_scene(silent)[0], [])

    silent_but_talking = dict(silent, narration="oops")
    check_eq(
        "silent with narration fails",
        [s for s, _ in check_scene(silent_but_talking)[0]],
        ["fail"],
    )

    missing = {"scene_id": "S04", "capture": {"in": 0, "out": 4}}
    check_eq("no narration fails", [s for s, _ in check_scene(missing)[0]], ["fail"])

    gap_no_note = {"scene_id": "S05", "capture": {"in": 0, "out": 4}, "gap": True}
    check_eq("gap without note fails", [s for s, _ in check_scene(gap_no_note)[0]], ["fail"])

    gap_ok = dict(gap_no_note, gap_note="consultant to confirm approver role")
    check_eq("gap with note clean", check_scene(gap_ok)[0], [])

    unreadable = {
        "scene_id": "S06",
        "capture": {"in": 0, "out": 1.2},
        "narration": "Two words",
        "annotations": [{"type": "callout", "text": "a much longer callout than fits"}],
    }
    assert any("needs" in m for _, m in check_scene(unreadable, mode=R)[0])

    underrun = {
        "scene_id": "S07",
        "capture": {"in": 0, "out": 20},
        "narration": "Barely anything.",
    }
    check_eq("underrun warns", [s for s, _ in check_scene(underrun, mode=R)[0]], ["warn"])

    # --- cleaned-verbatim fidelity -------------------------------------------------
    no_source = {
        "scene_id": "S08",
        "capture": {"in": 0, "out": 8},
        "narration": " ".join(["word"] * 18),
    }
    assert any("source_excerpt" in m for _, m in check_scene(no_source)[0])

    faithful = dict(no_source, source_excerpt=" ".join(["word"] * 22))
    check_eq("faithful clean passes", check_scene(faithful)[0], [])

    gutted = dict(no_source, source_excerpt=" ".join(["word"] * 60))
    assert any("rewrite, not a clean" in m for _, m in check_scene(gutted)[0])

    padded = dict(no_source, source_excerpt=" ".join(["word"] * 12))
    assert any("words have been added" in m for _, m in check_scene(padded)[0])

    # A cleaned-verbatim script with no transcript at all warns at the script level.
    no_transcript = check({"scenes": [], "fidelity_mode": "cleaned-verbatim"})
    assert any("guide_transcript" in m for _, m in no_transcript["findings"])

    for f in failures:
        print(f"FAIL  {f}", file=sys.stderr)
    print(f"{'FAILED' if failures else 'passed'}: fit self-test")
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("script", nargs="?", help="video_script.json")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    parser.add_argument(
        "--update",
        action="store_true",
        help="write the computed word_budget back into each scene",
    )
    parser.add_argument("--self-test", action="store_true", help="run tests and exit")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if not args.script:
        parser.error("a video_script.json path is required (or pass --self-test)")

    path = Path(args.script)
    if not path.exists():
        print(f"not found: {path}", file=sys.stderr)
        return 1

    script = json.loads(path.read_text())
    result = check(script)

    if args.update:
        by_id = {row["scene_id"]: row for row in result["scenes"]}
        for scene in script.get("scenes", []):
            row = by_id.get(scene.get("scene_id"))
            if row:
                scene["word_budget"] = {"min": row["budget"][0], "max": row["budget"][1]}
        path.write_text(json.dumps(script, indent=2) + "\n")
        print(f"budgets written into {path}")

    print(json.dumps(result, indent=2) if args.json else render(result))

    return 1 if any(sev == "fail" for sev, _ in result["findings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
