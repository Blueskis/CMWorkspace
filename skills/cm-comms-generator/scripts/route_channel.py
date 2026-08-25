#!/usr/bin/env python3
"""Route a comms plan to the tool that builds its artifact (Stage 3b).

    python route_channel.py comms_plan.json --brief change_brief.json \\
        --brand brand_profile.json -o comms/<run>/production_brief.md
    python route_channel.py --list

Reads schemas/channel_registry.json — the routing table as data — and works out what has
to happen next for this plan's channel: which skill or MCP server produces the artifact,
which preconditions are satisfied, and the exact commands to run.

THE GATE: nothing gets a production route while QA has a hard failure. Production is
expensive and externally visible; the plan is where defects are cheap to fix. This script
runs qa_comms.audit() itself rather than trusting that someone ran it earlier.

Three outcomes, and the exit code distinguishes them:

  exit 0, status live      preconditions met — the route prints runnable commands
  exit 0, status blocked   the producer exists but is unreachable (a connector needing
                           authorization). The handoff artifact IS the deliverable for
                           this run; a human finishes it. This is a successful run.
  exit 1                   QA failed, or a hard precondition is unmet. No route is emitted.

STATUS (v0.2): this routes and reports; it does not itself call MCP tools or invoke
skills. That is deliberate — the model reads the route and drives the producer, so a
half-finished external call can never be left behind by a script that died mid-run.
"""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qa_comms  # noqa: E402  (same-directory sibling module)

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "schemas" / "channel_registry.json"


def load_registry(path=None):
    return json.loads(Path(path or REGISTRY_PATH).read_text(encoding="utf-8"))


# --- preconditions ---------------------------------------------------------
#
# Each returns (ok, detail). A precondition is "hard" when an unmet one makes the
# producer genuinely unable to run; connector reachability is deliberately NOT hard,
# because the handoff artifact still ships and a human can finish the job.

HARD_PRECONDITIONS = {"brand_approved"}


def check_brand_approved(ctx):
    brand = ctx.get("brand")
    if not brand:
        return False, "no brand profile supplied"
    approval = brand.get("approval") or {}
    if not approval.get("approved_by") or not approval.get("approved_date"):
        return False, "brand profile has no recorded approval"
    return True, f"approved by {approval['approved_by']} on {approval['approved_date']}"


def check_node_docx(ctx):
    if not shutil.which("node"):
        return False, "node is not on PATH"
    try:
        root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True,
                              timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        root = ""
    probe = subprocess.run(
        ["node", "-e", "require.resolve('docx')"],
        capture_output=True, text=True, timeout=30,
        env={**ctx["env"], "NODE_PATH": root} if root else ctx["env"],
    )
    if probe.returncode != 0:
        return False, "the docx package is not resolvable — run: npm install -g docx"
    return True, f"docx resolvable (NODE_PATH={root})"


def check_potx(ctx):
    template = (ctx["plan"].get("template") or {}).get("path")
    if not template:
        return False, "no client .potx — the from-scratch route applies, labelled unapproved"
    if not Path(template).exists():
        return False, f"template path does not exist: {template}"
    return True, f"client template at {template}"


def check_connector(server):
    def _check(ctx):
        # A session cannot introspect its own MCP tool list from inside a script, so the
        # caller passes what it can see. Absent that, report unknown rather than guessing
        # — claiming a connector is up and being wrong wastes an external call.
        available = ctx.get("available_servers")
        if available is None:
            return False, (f"{server} reachability unknown from inside this script — "
                           f"the caller must confirm the connector is authorized")
        if server in available:
            return True, f"{server} connector available"
        return False, f"{server} connector not available in this session"
    return _check


PRECONDITION_CHECKS = {
    "brand_approved": check_brand_approved,
    "node_docx_available": check_node_docx,
    "potx_available": check_potx,
    "canva_connected": check_connector("Canva"),
    "elevenlabs_connected": check_connector("ElevenLabs"),
    "synthesia_connected": check_connector("Synthesia"),
}


# --- route construction ----------------------------------------------------


def commands_for(channel, entry, ctx):
    """The runnable next steps for a live lane, as (label, command) pairs."""
    plan_path = ctx["plan_path"]
    brand_path = ctx["brand_path"]
    out = ctx["out_dir"]
    producer = entry["producer"]

    if producer == "skill:docx":
        return [
            ("Generate the build script",
             f"python skills/cm-comms-generator/scripts/build_docx.py {plan_path} "
             f"--brand {brand_path} -o {out}"),
            ("Build the .docx",
             f'NODE_PATH="$(npm root -g)" node {out}/build.js'),
            ("Render to PDF for visual check",
             f"python /root/.claude/skills/synced/docx/scripts/office/soffice.py "
             f"--headless --convert-to pdf --outdir {out} {out}/draft.docx"),
            ("Rasterise and read the pages",
             f"pdftoppm -jpeg -r 100 {out}/draft.pdf {out}/page"),
        ]

    if producer == "skill:pptx":
        has_potx = check_potx(ctx)[0]
        if has_potx:
            template = ctx["plan"]["template"]["path"]
            return [
                ("Profile the client template",
                 f"python skills/cm-proposal-generator/scripts/profile_template.py "
                 f"{template} -o {out}/template_profile.json"),
                ("Validate the plan against it",
                 f"python skills/cm-proposal-generator/scripts/build_deck.py "
                 f"{plan_path} {out}/template_profile.json -o {out}/build_manifest.json"),
                ("Assemble",
                 "invoke the `pptx` skill's TEMPLATE workflow: unzip -> edit "
                 "ppt/slides/slideN.xml -> rezip. Never pptxgenjs on a client template."),
                ("Visual check",
                 f"python /root/.claude/skills/synced/pptx/scripts/thumbnail.py "
                 f"{out}/deck.pptx {out}/thumbs"),
            ]
        return [
            ("Emit the deck theme from the brand profile",
             f"python skills/cm-comms-generator/scripts/apply_brand.py {brand_path} "
             f"-o {out}/deck_theme.json"),
            ("Assemble",
             "invoke the `pptx` skill to build from scratch against deck_theme.json. "
             "Label the result UNAPPROVED TEMPLATE at handover — it is not the client's deck."),
            ("Visual check",
             f"python /root/.claude/skills/synced/pptx/scripts/thumbnail.py "
             f"{out}/deck.pptx {out}/thumbs"),
        ]

    if producer == "mcp:Canva":
        return [
            ("Write the design brief",
             f"python skills/cm-comms-generator/scripts/canva_brief.py {plan_path} "
             f"--brand {brand_path} -o {out}/canva_brief.json"),
            ("Generate", "call Canva `generate-design` with the brief's prompt and copy fields"),
            ("Export", "call Canva `export-design` to retrieve the asset"),
            ("Stamp provenance",
             "record design_provenance: \"generated-unapproved\" — Canva invented this "
             "layout, so the DESIGN needs client sign-off before publish even though the "
             "copy has passed QA."),
        ]

    if producer in ("mcp:ElevenLabs", "mcp:Synthesia"):
        return [
            ("Write the production spec",
             f"python skills/cm-comms-generator/scripts/video_spec.py {plan_path} "
             f"--brand {brand_path} -o {out}/video_spec.json"),
            ("Produce",
             f"{entry['producer'].split(':')[1]} lane is not wired — see blocked_by. "
             f"The spec and captions are the deliverable; a producer picks them up by hand."),
        ]

    return []


def route(plan, brief, brand, registry, ctx):
    channel = plan.get("channel")
    entry = registry["channels"].get(channel)
    if entry is None:
        known = ", ".join(sorted(registry["channels"]))
        sys.exit(f"unknown channel '{channel}' — the registry knows: {known}")

    result = {"channel": channel, "entry": entry,
              "producer_meta": registry["producers"].get(entry["producer"], {})}

    # The gate.
    audit = qa_comms.audit(brief, plan, brand)
    result["qa"] = {"failures": audit["fail"], "warnings": audit["warn"]}

    # Preconditions.
    checks = []
    for name in entry.get("preconditions", []):
        fn = PRECONDITION_CHECKS.get(name)
        if fn is None:
            checks.append((name, False, "no check implemented for this precondition"))
            continue
        ok, detail = fn(ctx)
        checks.append((name, ok, detail))
    result["preconditions"] = checks

    unmet_hard = [n for n, ok, _ in checks if not ok and n in HARD_PRECONDITIONS]
    result["unmet_hard"] = unmet_hard

    if audit["fail"]:
        result["outcome"] = "qa_failed"
    elif unmet_hard:
        result["outcome"] = "precondition_failed"
    elif entry["status"] == "live":
        result["outcome"] = "route"
    else:
        result["outcome"] = "handoff_only"

    result["commands"] = commands_for(channel, entry, ctx) if result["outcome"] in (
        "route", "handoff_only") else []
    return result


# --- report ----------------------------------------------------------------


def render(plan, result):
    entry, ctx_channel = result["entry"], result["channel"]
    lines = [
        f"# Production route — {plan.get('run_id', '')}",
        "",
        f"- **Channel:** {entry['label']} (`{ctx_channel}`)",
        f"- **Format:** {entry['format']}",
        f"- **Producer:** `{entry['producer']}`",
        f"- **Lane status:** {entry['status']}",
        f"- **Generated:** {date.today().isoformat()}",
        "",
    ]

    outcome = result["outcome"]
    verdict = {
        "route": "READY TO PRODUCE",
        "handoff_only": "HANDOFF ONLY — producer unreachable",
        "qa_failed": "BLOCKED — QA must pass first",
        "precondition_failed": "BLOCKED — precondition unmet",
    }[outcome]
    lines += [f"## {verdict}", ""]

    if outcome == "qa_failed":
        lines += ["Production is gated on QA. Fix these in the plan, then re-route:", ""]
        lines += [f"{i}. {m}" for i, m in enumerate(result["qa"]["failures"], 1)] + [""]

    if result["unmet_hard"]:
        lines += ["Unmet hard preconditions:", ""]
        lines += [f"- `{n}`" for n in result["unmet_hard"]] + [""]

    lines += ["## Preconditions", ""]
    for name, ok, detail in result["preconditions"]:
        lines.append(f"- [{'x' if ok else ' '}] `{name}` — {detail}")
    lines.append("")

    if entry.get("blocked_by"):
        lines += ["## What is blocking this lane", "", entry["blocked_by"], ""]
        if entry.get("planned_for"):
            lines += [f"Planned for **{entry['planned_for']}**. The handoff artifact "
                      f"(`{entry['handoff']}`) is the deliverable until then.", ""]

    if result["commands"]:
        lines += ["## Next steps", ""]
        for i, (label, cmd) in enumerate(result["commands"], 1):
            lines.append(f"{i}. **{label}**")
            lines.append("")
            if cmd.startswith(("python", "node", "NODE_PATH", "pdftoppm")):
                lines += ["   ```bash", f"   {cmd}", "   ```", ""]
            else:
                lines += [f"   {cmd}", ""]

    note = result["producer_meta"].get("note")
    if note:
        lines += ["## Producer notes", "", note, ""]

    if result["qa"]["warnings"]:
        lines += ["## QA warnings carried into production", ""]
        lines += [f"- {w}" for w in result["qa"]["warnings"]] + [""]

    lines += ["---", "",
              "*The artifact this route produces is a first draft for practitioner review, "
              "not an approved send.*"]
    return "\n".join(lines)


def list_channels(registry):
    print(f"{'channel':<20} {'status':<9} {'format':<34} producer")
    print("-" * 96)
    for name, e in registry["channels"].items():
        print(f"{name:<20} {e['status']:<9} {e['format']:<34} {e['producer']}")
    print()
    for name, e in registry["channels"].items():
        if e.get("blocked_by"):
            print(f"{name}: {e['blocked_by']}")
    return 0


def main():
    import os

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", type=Path, nargs="?")
    ap.add_argument("--brief", type=Path)
    ap.add_argument("--brand", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("production_brief.md"))
    ap.add_argument("--registry", type=Path)
    ap.add_argument("--available-servers", default=None,
                    help="Comma-separated MCP servers the caller can see (e.g. 'Canva'). "
                         "Omit when unknown — the route reports unknown rather than guessing.")
    ap.add_argument("--list", action="store_true", help="Show the routing table and exit")
    args = ap.parse_args()

    registry = load_registry(args.registry)
    if args.list:
        return list_channels(registry)

    if not (args.plan and args.brief):
        ap.error("plan and --brief are required unless --list is passed")

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    brief = json.loads(args.brief.read_text(encoding="utf-8"))
    brand = json.loads(args.brand.read_text(encoding="utf-8")) if args.brand else None

    ctx = {
        "plan": plan, "brand": brand,
        "plan_path": args.plan, "brand_path": args.brand or "<brand_profile.json>",
        "out_dir": args.out.parent if args.out.parent != Path("") else Path("."),
        "env": dict(os.environ),
        "available_servers": (
            {s.strip() for s in args.available_servers.split(",") if s.strip()}
            if args.available_servers is not None else None
        ),
    }

    result = route(plan, brief, brand, registry, ctx)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(plan, result) + "\n", encoding="utf-8")

    entry = result["entry"]
    print(f"Route {plan.get('run_id', '')} [{result['channel']} -> {entry['producer']}] "
          f"-> {args.out}")

    if result["outcome"] == "qa_failed":
        n = len(result["qa"]["failures"])
        print(f"  BLOCKED: QA has {n} failure(s) — nothing is produced until they are fixed",
              file=sys.stderr)
        for m in result["qa"]["failures"]:
            print(f"  FAIL {m}", file=sys.stderr)
        return 1

    if result["outcome"] == "precondition_failed":
        print(f"  BLOCKED: unmet hard precondition(s): "
              f"{', '.join(result['unmet_hard'])}", file=sys.stderr)
        return 1

    if result["outcome"] == "handoff_only":
        print(f"  {entry['producer']} unreachable — {entry['handoff']} is the deliverable "
              f"for this run")
        print(f"  {entry['blocked_by']}")
        return 0

    print(f"  ready: {len(result['commands'])} step(s) — see {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
