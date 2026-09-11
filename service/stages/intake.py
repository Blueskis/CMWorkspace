"""Stage 1 — free text ─▶ change_brief.json, via a forced tool call against the real schema.

This is the half of the pipeline no script can do: turning a practitioner's prose into stable
A/M/T ids, deciding what is a must-land message versus supporting, and — the part that matters
most — routing anything the text did not actually say into open_questions rather than inventing
it. reference/change-intake.md (read alongside this) is the question set and the "never invent"
rule this prompt is built from.
"""

from __future__ import annotations

import json
from pathlib import Path

import anthropic

from .schema_tools import load_tool_schema

MODEL = "claude-opus-5"

SYSTEM = """You are Stage 1 (Intake) of the cm-comms-generator pipeline: you turn a change \
practitioner's free-text description of a change into a structured change_brief.json.

Rules, non-negotiable:
- Never invent an audience, a date, a required action, or a rationale the text does not \
support. Anything the practitioner did not say goes into open_questions, not into a confident \
field.
- Give every audience, key_message and milestone a stable id (A1, A2..., M1, M2..., T1, T2...).
- rationale_confidence is "inferred" whenever you are reading between the lines rather than \
quoting something stated.
- milestones.date_confidence is "indicative" unless the text clearly commits to the date.
- Call the submit_change_brief tool exactly once with the complete object. Do not write prose."""


def build_change_brief(free_text: str, org: str, sender: str | None, client: anthropic.Anthropic) -> dict:
    schema = load_tool_schema("change_brief.schema.json")
    user = f"Organisation: {org}\n"
    if sender:
        user += f"Sending on behalf of: {sender}\n"
    user += f"\nThe change, in the practitioner's own words:\n\n{free_text}"

    resp = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=SYSTEM,
        tools=[{"name": "submit_change_brief", "description": "Submit the completed change brief.", "input_schema": schema}],
        tool_choice={"type": "tool", "name": "submit_change_brief"},
        messages=[{"role": "user", "content": user}],
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == "submit_change_brief":
            return block.input
    raise RuntimeError("Stage 1 did not return a change_brief tool call")


def save(brief: dict, out_path: Path) -> Path:
    out_path.write_text(json.dumps(brief, indent=2))
    return out_path
