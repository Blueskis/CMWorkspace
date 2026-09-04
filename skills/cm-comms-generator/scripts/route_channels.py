#!/usr/bin/env python3
"""Validate a comms plan against the channel registry and emit a build manifest.

    python route_channels.py comms_plan.json channel_registry.json -o build_manifest.json

STATUS (v0.1): this script does the checking and sequencing, not the file assembly.

It confirms every channel_run in the plan references a channel the registry actually
carries, that the plan was built against the registry version currently on disk, and
then emits one build step per channel_run naming the producer to hand it to (the docx
skill, the pptx skill's template route, Canva with the right design_type and verbatim
setting, or a narration_spec for the two planned video channels).

Automating the actual builds is Stage 4 of SKILL.md, executed by hand through the named
producer skill/tool. A half-working assembler that quietly mis-routes a banner through
the wrong Canva call is worse than a manifest a human follows — see channel_registry.json
for why banner and newsletter cannot be routed identically despite both being Canva.
"""

import argparse
import json
import sys
from pathlib import Path

PRODUCER_BY_CHANNEL = {
    "email": "docx",
    "article": "docx",
    "briefing_deck": "pptx",
    "newsletter": "canva-doc",
    "banner": "canva-poster",
    "short_form_video": "narration-spec",
    "explainer_video": "narration-spec",
}

REQUIRED_RUN_FIELDS = ("run_id", "channel_id", "audience_id", "message_ids", "blocks")


def registry_lookup(registry):
    return {c["id"]: c for c in registry.get("channels", [])}


def build(plan, registry):
    errors = []
    channels = registry_lookup(registry)

    plan_version = plan.get("registry_version")
    reg_version = registry.get("version")
    if plan_version and reg_version and plan_version != reg_version:
        errors.append(
            f"registry version mismatch: plan was built against '{plan_version}', "
            f"channel_registry.json on disk is '{reg_version}'. Re-run Stage 2 against "
            f"the current registry before building."
        )
        return None, errors

    steps = []
    for run in plan.get("channel_runs", []):
        run_id = run.get("run_id", "(missing run_id)")

        missing = [f for f in REQUIRED_RUN_FIELDS if f not in run]
        if missing:
            errors.append(
                f"{run_id}: channel_run is missing required field(s) {missing}"
            )
            continue

        channel_id = run["channel_id"]
        channel = channels.get(channel_id)
        if channel is None:
            errors.append(
                f"{run_id}: channel_id '{channel_id}' is not in the registry. "
                f"Available: {', '.join(sorted(channels))}"
            )
            continue

        producer = PRODUCER_BY_CHANNEL.get(channel_id, channel.get("producer", "unknown"))
        step = {
            "run_id": run_id,
            "channel_id": channel_id,
            "audience_id": run.get("audience_id"),
            "producer": producer,
            "status": channel.get("status"),
        }

        if channel_id == "newsletter":
            step["params"] = {"design_type": "doc", "verbatim": True}
        elif channel_id == "banner":
            step["params"] = {"design_type": "poster", "verbatim": False}
            step["note"] = channel.get("constraints", {}).get(
                "note", "verbatim is ignored for posters — paste QA'd copy in by hand."
            )
        elif producer == "narration-spec":
            step["note"] = (
                "planned channel: this step produces a script, captions, and "
                "narration_spec.json — no rendered video exists until a narration "
                "engine is wired."
            )

        steps.append(step)

    return {"steps": steps}, errors


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("plan", type=Path)
    ap.add_argument("registry", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("build_manifest.json"))
    args = ap.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    registry = json.loads(args.registry.read_text(encoding="utf-8"))

    manifest, errors = build(plan, registry)

    if manifest is None:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        return 1

    if not manifest["steps"]:
        print("WARNING: comms_plan.json has no channel_runs — nothing will be built.", file=sys.stderr)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Routed {len(manifest['steps'])} channel run(s) -> {args.out}")
    for e in errors:
        print(f"FAIL: {e}", file=sys.stderr)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
