#!/usr/bin/env python3
"""Turn a comms plan into a video production spec (Stage 3b, both video channels).

    python video_spec.py comms_plan.json --brand brand_profile.json \\
        -o comms/<run>/video_spec.json

Writes the scene table, the voiceover script with per-scene timing, the on-screen text,
a WebVTT caption file, and the direction a producer needs — aspect ratio, avatar, and
whether each scene is talking head or screen capture.

Neither video lane has a reachable producer in v0.2:

  short_form_video  ElevenLabs — installed but disabled in chat, and the tools it exposes
                    are voice-agent management rather than TTS or video rendering
  explainer_video   Synthesia — no connector exists in the Claude connector directory

So this spec IS the deliverable today, and it is written to be handed to a person or an
app without further translation. When either connector arrives, the same file is the
adapter's input: scene text becomes the TTS payload, direction becomes scene setup.

The runtime estimate is the check that earns its place. A script written to a 45-second
slot that actually reads at 90 seconds is the single most common defect in a short-form
video brief, and it is invisible until someone records it.

STATUS (v0.2): estimates and formats; renders nothing. Timing is computed from word count
at the brand's words-per-minute, which is a planning figure — a real read varies with
pauses, and a scene near its limit should be treated as over.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_markdown import ordered_parts, spoken_words, body_of  # noqa: E402
from qa_comms import registry_specs, load_registry  # noqa: E402

VIDEO_CHANNELS = ("short_form_video", "explainer_video")


def vtt_timestamp(seconds):
    ms = int(round((seconds - int(seconds)) * 1000))
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}.{ms:03d}"


def scene_text(part, kinds):
    """Text of the blocks whose kind is in `kinds`, flattened."""
    out = []
    for block in part.get("blocks", []):
        if block.get("gap"):
            continue
        if block["kind"] in kinds:
            content = block["content"]
            items = content if isinstance(content, list) else [content]
            out += [str(i) for i in items if str(i).strip()]
    return " ".join(" ".join(o.split()) for o in out)


def build(plan, brand, channel):
    specs = dict(registry_specs(channel))
    specs.update((brand.get("channel_specs") or {}).get(channel, {}))
    wpm = specs.get("words_per_minute") or 150
    limit = specs.get("max_duration_seconds")

    scenes, cursor, total_words = [], 0.0, 0
    for _, part in ordered_parts(plan):
        vo = scene_text(part, ("text", "paragraph"))
        on_screen = scene_text(part, ("bullets", "heading"))
        words = spoken_words(part)
        total_words += words
        est = round(words / wpm * 60, 1) if wpm else 0.0
        declared = part.get("duration_seconds")
        duration = float(declared) if declared else est

        gaps = [b.get("gap_note") for b in part["blocks"] if b.get("gap")]
        scene = {
            "scene_id": part["slide_id"],
            "title": part.get("title", ""),
            "part_kind": part.get("part_kind", "scene"),
            "voiceover": vo or body_of(part).replace("\n", " ").strip(),
            "on_screen_text": on_screen,
            "words": words,
            "planned_seconds": declared,
            "estimated_seconds": est,
            "start_seconds": round(cursor, 1),
            "end_seconds": round(cursor + duration, 1),
            "direction": ("talking head" if channel == "explainer_video"
                          and part.get("part_kind") != "chapter" else "on-screen text"),
            "sources": sorted({s for b in part["blocks"] for s in b.get("sources", [])}),
        }
        if declared and est > declared:
            scene["over_scene_budget"] = (
                f"script reads at ~{est}s against a planned {declared}s")
        if gaps:
            scene["open_gaps"] = gaps
        scenes.append(scene)
        cursor += duration

    est_total = round(total_words / wpm * 60, 1) if wpm else 0.0
    registry = load_registry()
    entry = registry["channels"][channel]

    return {
        "generated": date.today().isoformat(),
        "run_id": plan.get("run_id"),
        "channel": channel,
        "client": plan.get("client"),
        "title": plan.get("engagement_title"),
        "intended_producer": entry["producer"],
        "producer_status": entry["status"],
        "blocked_by": entry.get("blocked_by"),
        "format": {
            "aspect_ratio": specs.get("aspect_ratio"),
            "captions_required": specs.get("captions_required", True),
            "avatar": specs.get("avatar"),
            "chaptered": specs.get("chaptered", channel == "explainer_video"),
            "words_per_minute": wpm,
        },
        "runtime": {
            "estimated_seconds": est_total,
            "planned_seconds": round(cursor, 1),
            "limit_seconds": limit,
            "within_limit": (limit is None or est_total <= limit),
            "note": ("Estimated from word count at the brand's words-per-minute. A real "
                     "read varies with pauses — treat a scene near its limit as over."),
        },
        "scenes": scenes,
        "palette": {k: v.get("hex") for k, v in (brand.get("palette") or {}).items()
                    if isinstance(v, dict) and v.get("hex")},
        "typography": {"heading": ((brand.get("typography") or {}).get("heading") or {}).get("family"),
                       "body": ((brand.get("typography") or {}).get("body") or {}).get("family")},
    }


def to_vtt(spec):
    lines = ["WEBVTT", ""]
    for i, s in enumerate(spec["scenes"], 1):
        if not s["voiceover"]:
            continue
        lines.append(str(i))
        lines.append(f"{vtt_timestamp(s['start_seconds'])} --> "
                     f"{vtt_timestamp(s['end_seconds'])}")
        lines.append(s["voiceover"])
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", type=Path)
    ap.add_argument("--brand", type=Path, required=True)
    ap.add_argument("-o", "--out", type=Path, default=Path("video_spec.json"))
    ap.add_argument("--captions", type=Path,
                    help="Also write a WebVTT file (default: captions.vtt beside --out)")
    args = ap.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    brand = json.loads(args.brand.read_text(encoding="utf-8"))

    channel = plan.get("channel")
    if channel not in VIDEO_CHANNELS:
        sys.exit(f"video_spec.py handles {' and '.join(VIDEO_CHANNELS)}; got '{channel}'")
    if not (brand.get("approval") or {}).get("approved_by"):
        sys.exit("brand profile has no recorded approval — stop and ask before producing")

    spec = build(plan, brand, channel)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    vtt_path = args.captions or args.out.with_name("captions.vtt")
    vtt_path.write_text(to_vtt(spec) + "\n", encoding="utf-8")

    rt = spec["runtime"]
    print(f"Video spec -> {args.out}  [{channel}]")
    print(f"  {len(spec['scenes'])} scene(s); captions -> {vtt_path}")
    print(f"  estimated runtime {rt['estimated_seconds']}s at "
          f"{spec['format']['words_per_minute']} wpm"
          + (f", limit {rt['limit_seconds']}s" if rt["limit_seconds"] else ""))
    if not rt["within_limit"]:
        print(f"  OVER the {rt['limit_seconds']}s limit — cut the script, not the pauses",
              file=sys.stderr)
    for s in spec["scenes"]:
        if s.get("over_scene_budget"):
            print(f"  WARNING {s['scene_id']}: {s['over_scene_budget']}", file=sys.stderr)
    print(f"  intended producer {spec['intended_producer']} ({spec['producer_status']}) — "
          f"the spec and captions are the deliverable until that lane is wired")
    return 0


if __name__ == "__main__":
    sys.exit(main())
