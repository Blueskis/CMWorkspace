"""Stage 3a — brief + brand + retrieved knowledge-bank hits ─▶ comms_plan.json.

The other half the scripts cannot do: writing the actual copy, with every block traced to a
knowledge-bank entry id, a `brief:<dotted.path>` reference, or an explicit gap. See SKILL.md's
"three provenance states" section and reference/channel-library.md for the per-channel anatomy
this prompt is expected to follow — this module does not re-derive that guidance, it hands the
model the same schema and reference material a practitioner would read.
"""

from __future__ import annotations

import json
from pathlib import Path

import anthropic

from .schema_tools import load_tool_schema

MODEL = "claude-opus-5"
REF_DIR = Path(__file__).resolve().parent.parent.parent / "skills" / "cm-comms-generator" / "reference"

SYSTEM = """You are Stage 3a (Plan and draft) of the cm-comms-generator pipeline: you turn a \
change_brief.json, a brand_profile.json and a shortlist of past knowledge-bank collateral into \
one comms_plan.json for exactly one channel.

Rules, non-negotiable — these are the ones qa_comms.py checks mechanically, so violating them \
fails the run before anything is produced:
- Every block's `sources` array is non-empty UNLESS `gap` is true, in which case `gap_note` is \
required and the content stays a visible [GAP] placeholder — never plausible-sounding filler.
- A source is either a knowledge-bank entry id from the shortlist you were given, or \
"brief:<dotted.path>" pointing at a real field of the brief you were given (e.g. \
"brief:audiences.A1.required_action"). A dangling brief: reference fails the run.
- target_audience_ids is the subset of the brief's audiences THIS channel run addresses — not \
necessarily all of them.
- Follow reference/channel-library.md's anatomy for the chosen channel (part_kind sequence, \
coverage_mode — a signpost channel like banner or short_form_video carries ONE must-land \
message and points elsewhere, it does not try to carry the whole story).
- Respect any channel_specs limits in the brand profile (character counts, max_slides, etc).
- Call the submit_comms_plan tool exactly once with the complete object. Do not write prose."""


def build_comms_plan(
    brief: dict,
    brand: dict,
    channel: str,
    run_id: str,
    kb_hits: list[dict],
    client: anthropic.Anthropic,
) -> dict:
    schema = load_tool_schema("comms_plan.schema.json")
    channel_library = (REF_DIR / "channel-library.md").read_text()

    user = (
        f"CHANNEL: {channel}\nrun_id: {run_id}\n\n"
        f"CHANGE BRIEF:\n{json.dumps(brief, indent=2)}\n\n"
        f"BRAND PROFILE:\n{json.dumps(brand, indent=2)}\n\n"
        f"KNOWLEDGE-BANK SHORTLIST (cite these ids in sources, or brief: refs, or gap):\n"
        f"{json.dumps(kb_hits, indent=2)}\n\n"
        f"CHANNEL LIBRARY (anatomy and coverage_mode reference):\n{channel_library}"
    )

    resp = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        thinking={"type": "adaptive"},
        system=SYSTEM,
        tools=[{"name": "submit_comms_plan", "description": "Submit the completed comms plan.", "input_schema": schema}],
        tool_choice={"type": "tool", "name": "submit_comms_plan"},
        messages=[{"role": "user", "content": user}],
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == "submit_comms_plan":
            return block.input
    raise RuntimeError("Stage 3a did not return a comms_plan tool call")


def save(plan: dict, out_path: Path) -> Path:
    out_path.write_text(json.dumps(plan, indent=2))
    return out_path
