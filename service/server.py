"""cm-comms MCP server — the backend the comms console artifact (and Claude Desktop/Code)
calls so a run goes from free text to finished collateral without anyone copying a prompt
back into a chat window.

Five tools, each a thin wrapper: two call the Claude API for the stages that genuinely need a
model (Stage 1 intake, Stage 3a drafting); the rest shell out to the existing, already-tested
scripts under skills/cm-comms-generator/scripts/ via runner.py. This file adds no new pipeline
logic — QA still gates production in route_channel.py, an unreachable producer is still a
successful run, and a brand profile with no recorded approval still refuses everything.

Run: `fastmcp run server.py` (see README.md for connector registration).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import anthropic
from fastmcp import FastMCP

import runner
import storage
from stages import draft, intake

mcp = FastMCP("cm-comms")
_claude = anthropic.Anthropic()

BRAND_PROFILE_PATH = Path(os.environ.get(
    "BRAND_PROFILE_PATH",
    runner.REPO_ROOT / "examples" / "northwind-payroll" / "brand_profile.json",
))
TAGS_BY_CHANNEL = {
    "email": ["email"], "article": ["article"], "briefing_deck": ["briefing-deck", "deck"],
    "newsletter": ["newsletter"], "banner": ["banner"],
    "short_form_video": ["video"], "explainer_video": ["video", "explainer"],
}


def _brief_path(run_id: str) -> Path:
    return storage.workspace_for(run_id) / "change_brief.json"


def _channel_dir(run_id: str, channel: str) -> Path:
    d = storage.workspace_for(run_id) / channel
    d.mkdir(parents=True, exist_ok=True)
    return d


@mcp.tool()
def list_channels() -> str:
    """The channel registry — status (live/blocked/planned), format and producer for each
    of the seven channels. Call this first so a caller never hardcodes what this deployment
    can actually build."""
    return runner.list_channels()


@mcp.tool()
def intake_change(change_text: str, org: str, sender: str | None = None) -> dict:
    """Stage 1. Turn free text describing a change into a change_brief.json with stable
    audience/message/milestone ids. Returns a run_id to pass to every later tool call, plus
    the parsed brief so the caller can show the practitioner what was understood — including
    anything that landed in open_questions because the text did not say it."""
    brief = intake.build_change_brief(change_text, org, sender, _claude)
    run_id = brief.get("brief_id") or f"{org.lower().replace(' ', '-')}-run"
    intake.save(brief, _brief_path(run_id))
    return {
        "run_id": run_id,
        "brief": brief,
        "open_questions": brief.get("open_questions", []),
    }


@mcp.tool()
def plan_channel(run_id: str, channel: str) -> dict:
    """Stage 3a. Retrieve relevant knowledge-bank collateral, draft the comms_plan.json for
    one channel, and render the reviewable Markdown draft. Requires intake_change to have run
    for this run_id first."""
    brief_path = _brief_path(run_id)
    if not brief_path.exists():
        raise ValueError(f"No brief for run_id={run_id!r} — call intake_change first")
    brief = json.loads(brief_path.read_text())
    brand = json.loads(BRAND_PROFILE_PATH.read_text())

    kb_index = runner.index_kb(storage.WORKSPACE_ROOT / "kb_index.json")
    section = {"newsletter": "comms-collateral", "banner": "comms-collateral"}.get(channel, "comms-collateral")
    kb_hits = runner.retrieve(kb_index, section, TAGS_BY_CHANNEL.get(channel, [channel]))

    plan = draft.build_comms_plan(brief, brand, channel, run_id, kb_hits, _claude)
    cdir = _channel_dir(run_id, channel)
    plan_path = draft.save(plan, cdir / "comms_plan.json")
    draft_path = runner.render_markdown(plan_path, BRAND_PROFILE_PATH, cdir / "draft.md")
    return {"run_id": run_id, "channel": channel, "plan_path": str(plan_path), "draft": draft_path.read_text()}


@mcp.tool()
def audit_comm(run_id: str, channel: str) -> dict:
    """Stage 4. Run the QA gate — message coverage, audience coverage, provenance, brand
    approval, channel-spec limits, design provenance. Returns passed=false with the report's
    findings rather than raising, since a real QA failure is an expected outcome to show the
    caller, not a service error."""
    cdir = _channel_dir(run_id, channel)
    return runner.qa_comms(_brief_path(run_id), cdir / "comms_plan.json", BRAND_PROFILE_PATH, cdir / "qa_report.md")


@mcp.tool()
def produce(run_id: str, channel: str) -> dict:
    """Stage 3b. Route the channel to its producer and build what can be built. Re-runs QA
    itself (same as route_channel.py) and refuses to produce anything while a hard failure
    stands. Three outcomes: 'route' with a downloadable artifact URL, 'handoff_only' with a
    brief/spec URL when the producer (Canva, ElevenLabs, Synthesia) is unreachable — this is a
    successful run, not a failure — or 'qa_failed'/'precondition_failed' with no artifact."""
    cdir = _channel_dir(run_id, channel)
    plan_path = cdir / "comms_plan.json"
    route = runner.route_channel(plan_path, _brief_path(run_id), BRAND_PROFILE_PATH, cdir / "production_brief.md")
    if not route["ok"]:
        return {"outcome": "blocked", "run_id": run_id, "channel": channel, "detail": route["route"] or route["stderr"]}

    result = {"outcome": "handoff_only", "run_id": run_id, "channel": channel, "route_notes": route["route"]}

    if channel in ("email", "article"):
        docx = runner.build_docx(plan_path, BRAND_PROFILE_PATH, cdir)
        result.update(outcome="route", artifact_url=storage.publish(docx))
    elif channel == "briefing_deck":
        theme = runner.apply_brand(BRAND_PROFILE_PATH, cdir / "deck_theme.json", fmt="pptx")
        pptx = runner.build_pptx(plan_path, theme, cdir)
        result.update(outcome="route", artifact_url=storage.publish(pptx))
    elif channel in ("newsletter", "banner"):
        brief_json = runner.canva_brief(plan_path, BRAND_PROFILE_PATH, cdir / "canva_brief.json")
        result["canva_brief_url"] = storage.publish(brief_json)
        result["note"] = (
            "Canva design generation happens through the caller's own Canva connector "
            "(see README) — this tool hands back the brief; produce the design with "
            "generate-design / create-design-from-brand-template against it."
        )
    else:  # short_form_video, explainer_video — no reachable producer in v0.3
        spec = runner.video_spec(plan_path, BRAND_PROFILE_PATH, cdir / "video_spec.json")
        result["video_spec_url"] = storage.publish(spec)

    return result


if __name__ == "__main__":
    transport = os.environ.get("CM_COMMS_TRANSPORT", "http")
    if transport == "http":
        # Streamable HTTP — the transport a remote claude.ai custom connector requires.
        # stdio (fastmcp's bare mcp.run() default) only reaches a local Desktop/Code client.
        mcp.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
    else:
        mcp.run(transport=transport)
