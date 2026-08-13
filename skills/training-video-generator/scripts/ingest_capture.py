#!/usr/bin/env python3
"""Stage 1: segment a screen recording into scenes and extract a keyframe for each.

    python ingest_capture.py inputs/demo.mp4 -o capture_map.json --frames frames/
    python ingest_capture.py inputs/demo.mp4 -o capture_map.json --threshold 0.4
    python ingest_capture.py --self-test          # parsing logic only, no ffmpeg needed

Produces the measured half of capture_map.json: source metadata from ffprobe, scene
boundaries from ffmpeg scene detection, and one extracted keyframe per scene. Every scene is
written with read_status "unread" and no description — filling those in means opening the
keyframes and looking at them, which is Claude's job, not this script's.

That split is deliberate. Boundaries and durations are measured and must not be hand-edited;
screen/action/observed are read from the frames and cannot be measured. Conflating the two is
how narration ends up describing a screen nobody checked.

Scene detection is a starting point, not an oracle. If steps are being merged, lower
--threshold; if one step is fragmenting into many scenes, raise it or raise --min-scene. The
values used are recorded in the output so re-runs stay comparable.

Stdlib only; ffmpeg and ffprobe are invoked as subprocesses. Run preflight.py first.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PTS_TIME_RE = re.compile(r"pts_time:\s*([0-9]+(?:\.[0-9]+)?)")
DEFAULT_THRESHOLD = 0.3
DEFAULT_MIN_SCENE = 1.5


# ---------------------------------------------------------------- pure parsing helpers
# Split out from the subprocess calls so they can be exercised by --self-test on a machine
# without ffmpeg, and so a change in ffmpeg's output format fails somewhere obvious.


def parse_probe(json_text):
    """Pull duration, dimensions and frame rate out of `ffprobe -print_format json` output."""
    data = json.loads(json_text)

    video = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"), None
    )
    if video is None:
        raise ValueError("no video stream found — is this actually a screen recording?")

    duration = data.get("format", {}).get("duration") or video.get("duration")
    if duration is None:
        raise ValueError("could not determine duration from ffprobe output")

    fps = None
    rate = video.get("avg_frame_rate") or video.get("r_frame_rate") or ""
    if "/" in rate:
        num, den = rate.split("/", 1)
        try:
            if float(den) != 0:
                fps = round(float(num) / float(den), 3)
        except ValueError:
            fps = None

    return {
        "duration": float(duration),
        "width": int(video["width"]),
        "height": int(video["height"]),
        "fps": fps,
    }


def parse_scene_times(ffmpeg_stderr):
    """Extract scene-change timestamps from the showinfo filter's stderr output."""
    times = [float(m) for m in PTS_TIME_RE.findall(ffmpeg_stderr)]
    return sorted(set(times))


def build_scenes(boundaries, duration, min_scene=DEFAULT_MIN_SCENE):
    """Turn boundary timestamps into contiguous, non-overlapping scenes covering [0, duration].

    Boundaries closer together than min_scene are dropped — a UI that repaints in stages
    otherwise fragments a single step into a dozen unusable slivers. A recording with no
    detected boundaries yields one scene, which is correct rather than an error.
    """
    if duration <= 0:
        raise ValueError("duration must be positive")

    cuts = [0.0]
    for t in boundaries:
        if t <= 0 or t >= duration:
            continue
        if t - cuts[-1] >= min_scene:
            cuts.append(round(t, 3))

    # A trailing sliver gets absorbed into the scene before it rather than standing alone.
    if duration - cuts[-1] < min_scene and len(cuts) > 1:
        cuts.pop()

    scenes = []
    for i, start in enumerate(cuts):
        end = cuts[i + 1] if i + 1 < len(cuts) else duration
        scenes.append(
            {
                "scene_id": f"S{i + 1:02d}",
                "in": round(start, 3),
                "out": round(end, 3),
                "duration": round(end - start, 3),
                "disposition": "keep",
                "read_status": "unread",
            }
        )
    return scenes


def frame_seek_time(scene):
    """When to grab a scene's keyframe.

    Not the first frame: a scene boundary usually lands mid-transition, so frame zero is
    often a half-painted screen. A beat in is more representative of what the learner sees.
    """
    return round(scene["in"] + min(1.0, scene["duration"] * 0.3), 3)


# ---------------------------------------------------------------- subprocess wrappers


def _run(cmd, **kwargs):
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def probe_source(path):
    out = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
    )
    if out.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {out.stderr.strip()}")
    return parse_probe(out.stdout)


def detect_boundaries(path, threshold):
    out = _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(path),
            "-filter:v",
            f"select='gt(scene,{threshold})',showinfo",
            "-f",
            "null",
            "-",
        ]
    )
    # ffmpeg writes showinfo to stderr and exits 0 even when nothing matched.
    if out.returncode != 0:
        raise RuntimeError(f"ffmpeg scene detection failed: {out.stderr.strip()[-500:]}")
    return parse_scene_times(out.stderr)


def extract_frame(path, at, dest):
    out = _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-ss",
            str(at),
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(dest),
        ]
    )
    if out.returncode != 0 or not Path(dest).exists():
        raise RuntimeError(f"frame extraction failed at {at}s: {out.stderr.strip()[-300:]}")


def build_contact_sheet(frames_dir, dest, columns=3):
    """One image showing every scene, for eyeballing the split before reading frames in detail.

    Convenience only — a failure here is reported and ignored, because the individual frames
    are what the next step actually needs.
    """
    out = _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-pattern_type",
            "glob",
            "-i",
            str(Path(frames_dir) / "S*.png"),
            "-filter_complex",
            f"scale=480:-1,tile={columns}x0:margin=8:padding=8",
            str(dest),
        ]
    )
    return out.returncode == 0 and Path(dest).exists()


# ---------------------------------------------------------------- driver


def ingest(source, frames_dir, threshold, min_scene, module_slug, module_title):
    meta = probe_source(source)
    boundaries = detect_boundaries(source, threshold)
    scenes = build_scenes(boundaries, meta["duration"], min_scene)

    frames_dir = Path(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    for scene in scenes:
        dest = frames_dir / f"{scene['scene_id']}.png"
        extract_frame(source, frame_seek_time(scene), dest)
        scene["frame_ref"] = str(dest)

    sheet = frames_dir / "contact_sheet.png"
    if not build_contact_sheet(frames_dir, sheet):
        print(
            "  note: contact sheet could not be built (individual frames are fine)",
            file=sys.stderr,
        )

    return {
        "module": {"slug": module_slug, "title": module_title},
        "source": {
            "path": str(source),
            "duration": round(meta["duration"], 3),
            "width": meta["width"],
            "height": meta["height"],
            "fps": meta["fps"],
            "probed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "detection": {
            "threshold": threshold,
            "min_scene": min_scene,
            "boundaries_found": len(boundaries),
        },
        "scenes": scenes,
    }


def self_test():
    """Exercise the parsing logic without ffmpeg present."""
    failures = []

    def check(name, got, want):
        if got != want:
            failures.append(f"{name}: got {got!r}, want {want!r}")

    probe = parse_probe(
        json.dumps(
            {
                "streams": [
                    {"codec_type": "audio"},
                    {
                        "codec_type": "video",
                        "width": 1920,
                        "height": 1080,
                        "avg_frame_rate": "30000/1001",
                    },
                ],
                "format": {"duration": "132.533000"},
            }
        )
    )
    check("probe duration", probe["duration"], 132.533)
    check("probe width", probe["width"], 1920)
    check("probe fps", probe["fps"], 29.97)

    stderr = (
        "[Parsed_showinfo_1 @ 0x55] n:0 pts:368640 pts_time:12.4 duration:1\n"
        "[Parsed_showinfo_1 @ 0x55] n:1 pts:1228800 pts_time:41.2 duration:1\n"
        "frame= 100 fps=0.0 q=-0.0 Lsize=N/A time=00:00:04.00\n"
    )
    check("scene times", parse_scene_times(stderr), [12.4, 41.2])

    scenes = build_scenes([12.4, 41.2], 60.0)
    check("scene count", len(scenes), 3)
    check("first scene", (scenes[0]["in"], scenes[0]["out"]), (0.0, 12.4))
    check("last scene end", scenes[-1]["out"], 60.0)
    check("ids", [s["scene_id"] for s in scenes], ["S01", "S02", "S03"])

    # Boundaries closer than min_scene collapse rather than making slivers.
    check("min-scene merge", len(build_scenes([1.0, 1.2, 1.4, 30.0], 60.0)), 2)

    # A recording with no detected cuts is one scene, not an error.
    check("no boundaries", len(build_scenes([], 20.0)), 1)

    # Scenes tile the source exactly — the property qa_video.py depends on.
    tiled = build_scenes([10.0, 25.0, 40.0], 55.0)
    check("tiling", [(s["in"], s["out"]) for s in tiled],
          [(0.0, 10.0), (10.0, 25.0), (25.0, 40.0), (40.0, 55.0)])

    check("seek offset", frame_seek_time({"in": 10.0, "duration": 8.0}), 11.0)
    check("seek offset short scene", frame_seek_time({"in": 4.0, "duration": 2.0}), 4.6)

    for f in failures:
        print(f"FAIL  {f}", file=sys.stderr)
    print(f"{'FAILED' if failures else 'passed'}: parsing self-test")
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", nargs="?", help="the screen recording (mp4)")
    parser.add_argument("-o", "--output", help="where to write capture_map.json")
    parser.add_argument(
        "--frames", default="frames", help="directory for extracted keyframes"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"scene-change sensitivity, 0-1 (default {DEFAULT_THRESHOLD}); lower finds more cuts",
    )
    parser.add_argument(
        "--min-scene",
        type=float,
        default=DEFAULT_MIN_SCENE,
        help=f"merge boundaries closer than this many seconds (default {DEFAULT_MIN_SCENE})",
    )
    parser.add_argument("--slug", help="module slug (default: derived from filename)")
    parser.add_argument("--title", help="module title (default: derived from filename)")
    parser.add_argument(
        "--self-test", action="store_true", help="run parsing tests and exit"
    )
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    if not args.source or not args.output:
        parser.error("source and -o/--output are required (or pass --self-test)")

    source = Path(args.source)
    if not source.exists():
        print(f"not found: {source}", file=sys.stderr)
        return 1

    for binary in ("ffmpeg", "ffprobe"):
        if shutil.which(binary) is None:
            print(
                f"{binary} not found on PATH — run preflight.py for install instructions",
                file=sys.stderr,
            )
            return 1

    stem = source.stem.lower()
    slug = args.slug or re.sub(r"[^a-z0-9]+", "-", stem).strip("-") or "module"
    title = args.title or source.stem.replace("_", " ").replace("-", " ").title()

    try:
        capture_map = ingest(
            source, args.frames, args.threshold, args.min_scene, slug, title
        )
    except (RuntimeError, ValueError) as exc:
        print(f"ingest failed: {exc}", file=sys.stderr)
        return 1

    Path(args.output).write_text(json.dumps(capture_map, indent=2) + "\n")

    scenes = capture_map["scenes"]
    print(f"  {len(scenes)} scenes over {capture_map['source']['duration']}s")
    print(f"  frames in {args.frames}/, map in {args.output}")
    print()
    print("Next: open every keyframe, fill in screen/action/observed, and set")
    print('read_status to "read". Scenes left unread cannot carry narration.')
    return 0


if __name__ == "__main__":
    sys.exit(main())
