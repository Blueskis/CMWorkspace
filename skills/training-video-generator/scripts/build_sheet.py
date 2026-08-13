#!/usr/bin/env python3
"""Stage 3: turn the script into instructions for the Synthesia editor session.

    python build_sheet.py capture_map.json video_script.json \\
        -o build_sheet.md --scenes scenes/ --trim-list trim_list.csv
    python build_sheet.py --self-test

Emits three things:

  * build_sheet.md   what the practitioner works through, scene by scene
  * scenes/S01.txt   paste-ready narration, one file per scene, nothing else in the file
  * trim_list.csv    every cut and acceleration with timecodes and a reason

The aim is to make the editor session mechanical rather than creative. Nothing should need
rewriting in Synthesia, and narration should never be retyped — retyping is where a
reviewed script quietly becomes an unreviewed one.

Takes both artifacts because it needs dispositions (what to cut, what to speed up) from the
capture map and everything else from the script.
"""

import argparse
import csv
import json
import sys
from pathlib import Path


def timecode(seconds):
    """mm:ss.s — the form Synthesia's timeline shows."""
    minutes, secs = divmod(float(seconds), 60)
    return f"{int(minutes):02d}:{secs:04.1f}"


def build_trim_rows(capture_map):
    rows = []
    for scene in capture_map.get("scenes", []):
        disposition = scene.get("disposition", "keep")
        rows.append(
            {
                "scene_id": scene.get("scene_id", ""),
                "disposition": disposition,
                "in": scene.get("in", 0),
                "out": scene.get("out", 0),
                "duration": scene.get("duration", 0),
                "in_tc": timecode(scene.get("in", 0)),
                "out_tc": timecode(scene.get("out", 0)),
                "reason": scene.get("disposition_note", ""),
            }
        )
    return rows


def _scene_block(scene, capture_scene):
    scene_id = scene.get("scene_id", "?")
    capture = scene.get("capture", {})
    start, end = capture.get("in", 0), capture.get("out", 0)
    duration = round(float(end) - float(start), 1)
    role = scene.get("role", "step")

    lines = [
        f"### {scene_id} — {role}  ({timecode(start)} → {timecode(end)}, {duration}s)",
        "",
    ]

    if capture_scene and capture_scene.get("screen"):
        lines.append(f"**On screen:** {capture_scene['screen']}")
        lines.append("")

    avatar = scene.get("avatar", {})
    if avatar.get("visible"):
        lines.append(
            f"**Avatar:** visible — {avatar.get('position', 'bottom-right')}, "
            f"{avatar.get('framing', 'box')} framing"
        )
    else:
        lines.append("**Avatar:** hidden for this scene")
    lines.append("")

    if scene.get("gap"):
        lines.append(
            f"> **[GAP] — do not build this scene yet.** {scene.get('gap_note', '')}"
        )
        lines.append(
            "> The consultant must confirm this before narration can be written."
        )
        lines.append("")
    elif scene.get("silent"):
        lines.append("**Narration:** none — deliberate silent beat.")
        lines.append("")
    else:
        narration = scene.get("narration", "")
        words = len(narration.split())
        budget = scene.get("word_budget") or {}
        budget_note = (
            f" (budget {budget['min']}-{budget['max']})"
            if budget.get("min") is not None
            else ""
        )
        lines.append(f"**Narration** — {words} words{budget_note}, paste from `{scene_id}.txt`:")
        lines.append("")
        lines.append(f"> {narration}")
        lines.append("")

    annotations = scene.get("annotations") or []
    if annotations:
        lines.append("**Annotations:**")
        for annotation in annotations:
            kind = annotation.get("type", "?")
            text = annotation.get("text")
            target = annotation.get("target")
            where = ""
            if annotation.get("rect"):
                x, y, w, h = annotation["rect"]
                where = f" — box at {x:.0%},{y:.0%} size {w:.0%}×{h:.0%}"
            elif annotation.get("anchor"):
                x, y = annotation["anchor"]
                where = f" — pointing at {x:.0%},{y:.0%}"
            label = f'"{text}"' if text else f"on {target}" if target else ""
            lines.append(f"- `{kind}` {label}{where}")
        lines.append("")

    return lines


def render_sheet(capture_map, script):
    module = script.get("module", {})
    scenes = script.get("scenes", [])
    capture_by_id = {s.get("scene_id"): s for s in capture_map.get("scenes", [])}

    total = sum(
        float(s.get("capture", {}).get("out", 0)) - float(s.get("capture", {}).get("in", 0))
        for s in scenes
    )
    minutes, seconds = divmod(total, 60)
    gaps = [s for s in scenes if s.get("gap")]
    avatar_scenes = [s for s in scenes if s.get("avatar", {}).get("visible")]

    lines = [
        f"# Build sheet — {module.get('title', 'untitled module')}",
        "",
        f"**System:** {module.get('system', 'not stated')}  ",
        f"**Audience:** {module.get('audience', 'not stated')}  ",
        f"**Runtime:** {int(minutes)}m {seconds:04.1f}s across {len(scenes)} scenes  ",
        f"**Avatar appears in:** {len(avatar_scenes)} of {len(scenes)} scenes",
        "",
        "Work through this in the Synthesia editor. Do not rewrite narration here — if a "
        "line is wrong, fix `video_script.json`, re-run the fit check and regenerate this "
        "sheet, so the reviewed script and the built video stay the same thing.",
        "",
        "See `reference/synthesia-build.md` for the editor workflow and template setup.",
        "",
    ]

    if gaps:
        lines += [
            "## Open items — resolve before building",
            "",
            "Each of these needs the consultant to confirm something the recording does not "
            "show. Building around a gap means guessing on camera.",
            "",
        ]
        for scene in gaps:
            lines.append(f"- **{scene.get('scene_id')}** — {scene.get('gap_note', '')}")
        lines.append("")

    lines += ["## Scenes", ""]
    for scene in scenes:
        lines += _scene_block(scene, capture_by_id.get(scene.get("scene_id")))

    cuts = [
        r for r in build_trim_rows(capture_map) if r["disposition"] != "keep"
    ]
    if cuts:
        lines += ["## Cuts and accelerations", "", "From `trim_list.csv`:", ""]
        for row in cuts:
            lines.append(
                f"- **{row['scene_id']}** {row['disposition']} "
                f"{row['in_tc']} → {row['out_tc']} — {row['reason'] or 'no reason recorded'}"
            )
        lines.append("")

    lines += [
        "## Before you export",
        "",
        "- Every scene's narration matches its `.txt` file exactly.",
        "- The avatar is in the same corner in every scene it appears in.",
        "- No annotation sits under the avatar, and none is clipped at a frame edge.",
        "- Captions are enabled.",
        "- Nothing on screen shows production data, personal data or a real client name.",
        "",
        "Then export, and run `qa_video.py` before sending it to anyone.",
        "",
    ]
    return "\n".join(lines)


def write_scene_files(script, scenes_dir):
    scenes_dir = Path(scenes_dir)
    scenes_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for scene in script.get("scenes", []):
        if scene.get("silent") or scene.get("gap"):
            continue
        narration = scene.get("narration")
        if not narration:
            continue
        dest = scenes_dir / f"{scene['scene_id']}.txt"
        dest.write_text(narration.strip() + "\n")
        written.append(dest)
    return written


def write_trim_list(capture_map, dest):
    rows = build_trim_rows(capture_map)
    with open(dest, "w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "scene_id",
                "disposition",
                "in",
                "out",
                "duration",
                "in_tc",
                "out_tc",
                "reason",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return rows


def self_test():
    failures = []

    def check(name, got, want):
        if got != want:
            failures.append(f"{name}: got {got!r}, want {want!r}")

    check("timecode", timecode(0), "00:00.0")
    check("timecode secs", timecode(12.44), "00:12.4")
    check("timecode mins", timecode(95.2), "01:35.2")

    capture_map = {
        "scenes": [
            {"scene_id": "S01", "in": 0, "out": 10, "duration": 10, "disposition": "keep",
             "screen": "Fiori launchpad"},
            {"scene_id": "S02", "in": 10, "out": 14, "duration": 4, "disposition": "cut",
             "disposition_note": "mis-click, wrong tile"},
        ]
    }
    script = {
        "module": {"title": "Test module", "system": "S/4HANA"},
        "scenes": [
            {
                "scene_id": "S01",
                "role": "intro",
                "capture": {"in": 0, "out": 10},
                "narration": "Welcome to the module.",
                "avatar": {"visible": True, "position": "bottom-right", "framing": "box"},
                "annotations": [{"type": "lower_third", "text": "J. Doe"}],
            }
        ],
    }

    sheet = render_sheet(capture_map, script)
    assert "Build sheet — Test module" in sheet
    assert "Fiori launchpad" in sheet, "capture screen should surface in the sheet"
    assert "mis-click, wrong tile" in sheet, "cut reasons must appear"
    assert "Avatar:** visible" in sheet

    rows = build_trim_rows(capture_map)
    check("trim rows", len(rows), 2)
    check("cut row tc", rows[1]["in_tc"], "00:10.0")

    # A gap scene must never render narration, even if some is present in the file.
    gap_script = {
        "module": {"title": "G"},
        "scenes": [
            {
                "scene_id": "S01",
                "role": "step",
                "capture": {"in": 0, "out": 5},
                "gap": True,
                "gap_note": "approver role not visible",
                "narration": "should not be shown",
                "avatar": {"visible": False},
            }
        ],
    }
    gap_sheet = render_sheet(capture_map, gap_script)
    assert "should not be shown" not in gap_sheet, "gap scenes must not render narration"
    assert "[GAP]" in gap_sheet
    assert "Open items" in gap_sheet

    for f in failures:
        print(f"FAIL  {f}", file=sys.stderr)
    print(f"{'FAILED' if failures else 'passed'}: build sheet self-test")
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("capture_map", nargs="?", help="capture_map.json")
    parser.add_argument("script", nargs="?", help="video_script.json")
    parser.add_argument("-o", "--output", default="build_sheet.md")
    parser.add_argument("--scenes", default="scenes", help="directory for paste-ready narration")
    parser.add_argument("--trim-list", default="trim_list.csv")
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

    Path(args.output).write_text(render_sheet(capture_map, script))
    scene_files = write_scene_files(script, args.scenes)
    rows = write_trim_list(capture_map, args.trim_list)

    cuts = sum(1 for r in rows if r["disposition"] != "keep")
    gaps = sum(1 for s in script.get("scenes", []) if s.get("gap"))

    print(f"  {args.output}")
    print(f"  {len(scene_files)} narration files in {args.scenes}/")
    print(f"  {args.trim_list} — {cuts} cut/accelerate of {len(rows)} scenes")
    if gaps:
        print()
        print(f"  {gaps} open [GAP] item{'s' if gaps != 1 else ''} — resolve before building")
    return 0


if __name__ == "__main__":
    sys.exit(main())
