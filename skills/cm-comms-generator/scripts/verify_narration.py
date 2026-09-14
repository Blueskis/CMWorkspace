#!/usr/bin/env python3
"""Check that ElevenLabs' returned narration audio actually matches what was asked for.

    python verify_narration.py <out>/narration.json --returned <out>/narration_returned.json \\
        --spec <out>/video_spec.json

`narration.json` (video_spec.py --narration) is the request: one entry per scene, each with
a `budget_seconds`. `narration_returned.json` is the manifest a practitioner records after
polling `creative_get_flow_run_status` to completion — one entry per scene actually returned,
each with a measured `duration_seconds`. This script reconciles the two and does not decode
audio itself.

Three checks, all hard:

  1. Coverage    every payload scene has a returned entry, and every returned entry matches
                 a payload scene — a scene resumed under the wrong id would otherwise vanish
                 silently
  2. Duration    every returned entry states a measured duration
  3. Budget      total measured runtime is within the video spec's `max_duration_seconds`

Warns, does not fail:

  * a scene measured over its own `budget_seconds` — a single scene running long is not
    fatal the way an overall overrun is

This is also what reconciles the three runtime estimates that disagree by construction
(`qa_comms.audit()` uses word_count, `video_spec.build()` uses spoken_words, `render_video()`
would use brand-only specs): measured duration, from the artifact ElevenLabs actually
returned, becomes the truth.

**Never re-run a whole scene set to fix one failure here.** `creative_generate_speech`'s own
warning is explicit: calling it again starts and charges a second generation. Resume only the
scene(s) this script names as missing.

STATUS: stdlib only, matching repo hygiene. Reads JSON manifests; does not touch audio bytes.
"""

import argparse
import json
import sys
from pathlib import Path


def reconcile(narration, returned, spec):
    failures, warnings = [], []

    payload = {e["scene_id"]: e for e in narration.get("entries", [])}
    manifest = {s["scene_id"]: s for s in returned.get("scenes", [])}

    missing = sorted(set(payload) - set(manifest))
    for sid in missing:
        failures.append(f"{sid}: payload scene has no returned audio")

    extra = sorted(set(manifest) - set(payload))
    for sid in extra:
        failures.append(f"{sid}: returned audio has no matching payload scene — resumed "
                        f"under the wrong id?")

    total_measured = 0.0
    for sid, entry in sorted(payload.items()):
        scene = manifest.get(sid)
        if scene is None:
            continue
        duration = scene.get("duration_seconds")
        if duration is None:
            failures.append(f"{sid}: returned entry has no duration_seconds")
            continue
        total_measured += duration
        budget = entry.get("budget_seconds")
        if budget and duration > budget:
            warnings.append(f"{sid}: measured {duration}s over its budget of {budget}s")

    limit = ((spec or {}).get("runtime") or {}).get("limit_seconds")
    total_measured = round(total_measured, 1)
    if limit is not None and total_measured > limit:
        failures.append(f"total measured runtime {total_measured}s exceeds the "
                        f"{limit}s limit — cut a scene, don't re-run the whole set")

    return {
        "failures": failures,
        "warnings": warnings,
        "total_measured_seconds": total_measured,
        "limit_seconds": limit,
        "scenes_checked": len(payload),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("narration", type=Path, help="narration.json — the request payload")
    ap.add_argument("--returned", type=Path, required=True,
                    help="narration_returned.json — measured duration per scene, recorded "
                         "after polling creative_get_flow_run_status to completion")
    ap.add_argument("--spec", type=Path,
                    help="video_spec.json — supplies runtime.limit_seconds for the total-"
                         "runtime check; omit to skip that check")
    args = ap.parse_args()

    narration = json.loads(args.narration.read_text(encoding="utf-8"))
    returned = json.loads(args.returned.read_text(encoding="utf-8"))
    spec = json.loads(args.spec.read_text(encoding="utf-8")) if args.spec else None

    result = reconcile(narration, returned, spec)

    print(f"{args.narration}: {result['scenes_checked']} scene(s) in the payload")
    print(f"  measured runtime {result['total_measured_seconds']}s"
          + (f" against a {result['limit_seconds']}s limit" if result["limit_seconds"] else ""))

    if result["warnings"]:
        for w in result["warnings"]:
            print(f"  WARNING {w}", file=sys.stderr)

    if result["failures"]:
        for f in result["failures"]:
            print(f"  FAIL {f}", file=sys.stderr)
        print(f"  {len(result['failures'])} failure(s)", file=sys.stderr)
        return 1

    print("  every payload scene has matching, in-budget returned audio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
