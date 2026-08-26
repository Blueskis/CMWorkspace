# cm-comms MCP server

Turns the comms console artifact's submit button (and any other MCP client — Claude Desktop,
Claude Code) into a real run of the `cm-comms-generator` pipeline, without anyone copying a
prompt back into a chat window.

This is a thin wrapper. It does not reimplement the pipeline — `runner.py` shells out to the
same scripts under `skills/cm-comms-generator/scripts/` that already carry the QA gate, the
registry lookups and the producer footguns. `stages/intake.py` and `stages/draft.py` are the
two things a script cannot do: turning free text into a structured brief, and drafting the
actual copy with per-block provenance.

## Why this has to be a server, not more artifact JavaScript

A published Claude artifact runs in a sandboxed browser page. Its capability roster on this
account is `artifact`, `downloads`, `mcp`, `self` — none of them can execute Python, and two of
the pipeline's five stages (turning prose into a structured brief, drafting copy against the
knowledge bank) need a model call, not just logic. `mcp` is the one capability that reaches
outward at all: a page can call tools on **the viewer's own** connected MCP servers. So the
artifact's job is to call this server; this server does the actual work.

**Consequence:** a page that declares `mcp` cannot be shared publicly, and each viewer must add
this server as their own claude.ai connector before the artifact's submit button does anything.
Until you deploy this and a viewer connects it, the artifact's copy/paste fallback is what runs.

## Setup

```bash
cd service
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...
export BRAND_PROFILE_PATH=/path/to/real-client.brand_profile.json   # see below
export COMMS_WORKSPACE_ROOT=/var/lib/cm-comms/runs                  # persistent volume
export ARTIFACT_BASE_URL=https://your-cdn/cm-comms                  # see storage.py
python server.py
```

`server.py`'s `__main__` block reads `CM_COMMS_TRANSPORT` (default `http`) and serves
Streamable HTTP on `PORT` (default 8000) — the transport a **remote** claude.ai custom
connector requires. Set `CM_COMMS_TRANSPORT=stdio` instead for a local Claude Desktop/Code MCP
config, where stdio is what's expected. Don't run `fastmcp run server.py` for a remote
deployment — that CLI defaults to stdio regardless of this env var; run `python server.py`
directly so the `__main__` block's transport selection actually takes effect.

**`BRAND_PROFILE_PATH` is the one thing you must set per real deployment.** It defaults to the
Northwind example so the server runs out of the box, but that is fictional client demo data —
point it at a real, human-approved brand profile (`approval.approved_by` populated) before
running this against a real change. A profile with no recorded approval — like
`deloitte.brand_profile.EXAMPLE.json` — is refused by every producer, by design.

**`ARTIFACT_BASE_URL` needs real object storage behind it** — an S3 bucket, an Azure Blob
container, whatever the deployment already has. `storage.py` copies finished artifacts into
`COMMS_WORKSPACE_ROOT/artifacts/` and expects something else to serve that directory publicly.
Left unset, `produce` still runs correctly but hands back a local path instead of a URL — fine
for exercising the pipeline, not for handing a link to someone else.

## Deploying to Render

`render.yaml` in this directory is a Render Blueprint; `Dockerfile` builds from the **repo
root** (it needs `skills/` and `proposal-assets/` alongside `service/`, not just this
directory).

1. Push this repo somewhere Render can see it (a GitHub/GitLab repo Render has access to).
2. Render dashboard → **New** → **Blueprint** → point at the repo. Render finds
   `service/render.yaml` and reads it — the Dockerfile path inside it is already relative to
   the repo root, so no extra configuration is needed there.
3. Render will prompt for the `sync: false` env vars the blueprint declares:
   `ANTHROPIC_API_KEY`, `BRAND_PROFILE_PATH` (a real path baked into the image, or one you
   mount — see the note above about demo data), `ARTIFACT_BASE_URL` (leave blank until you have
   real object storage; `produce` still works, just without public download links).
4. Deploy. Render assigns a `https://cm-comms-<hash>.onrender.com` URL (or attach a custom
   domain). That's the remote MCP endpoint — Streamable HTTP, courtesy of
   `CM_COMMS_TRANSPORT=http` in the blueprint.
5. The blueprint also provisions a 1GB persistent disk mounted at `/var/data` — needed because
   `COMMS_WORKSPACE_ROOT` holds in-flight run state between the five tool calls of one
   generation (`intake_change` → `plan_channel` → `audit_comm` → `produce`, once per channel).
   Without it, a restart mid-run loses that state.

## Adding it as a connector

In claude.ai: **Settings → Connectors → Add custom connector**, paste the Render URL from step
4, and name the connector **exactly `cm-comms`** — the artifact's manifest and `MCP_SERVER` in
its script hardcode that display name, so a different name won't be found by
`listTools()`. (Claude Desktop/Code instead take an MCP server entry in their own config,
pointed at this same URL for `http`/`streamable-http` transport, or a local `stdio` command if
you're running the server locally with `CM_COMMS_TRANSPORT=stdio`.)

Once added, the artifact's `window.claude.mcp.listTools()` call finds it and the submit button
drives the five tools below instead of falling back to copy/paste.

## Tools

| Tool | Stage | Does |
|---|---|---|
| `list_channels` | — | The registry: status, format, producer per channel — so a caller never hardcodes what this deployment can build |
| `intake_change` | 1 | Free text → `change_brief.json`, returns a `run_id` |
| `plan_channel` | 3a | Retrieves knowledge-bank collateral, drafts `comms_plan.json`, renders the Markdown draft |
| `audit_comm` | 4 | Runs the QA gate; returns `passed: false` with findings rather than raising — a real QA failure is an expected result to show the caller |
| `produce` | 3b | Routes to the producer and builds what can be built. `outcome` is one of `route` (artifact URL), `handoff_only` (Canva brief / video spec — still a successful run), `blocked` (QA or a hard precondition failed, nothing produced) |

Call order per channel: `intake_change` once per change, then `plan_channel` → `audit_comm` →
`produce` per selected channel. A caller should stop and surface `audit_comm`'s findings to the
practitioner before calling `produce` — `produce` re-runs QA itself and will refuse anyway, but
showing the findings first is the point of having a QA stage at all.

## What this does not solve

- **Distribution.** Each viewer adds this connector under their own claude.ai account and runs
  on their own credentials — there is no "send someone the artifact link and it just works."
  See the repo README's Self-serve section for the alternative that needs no server at all:
  installing the `cm-workspace` plugin and running the pipeline in chat.
- **Multi-tenant brand/knowledge-bank selection.** This server is wired to one
  `BRAND_PROFILE_PATH` and one knowledge bank per deployment. Serving several clients from one
  server means extending `intake_change`/`plan_channel` to take a client identifier and resolve
  paths per call — not done here, since no second client profile exists yet to build it against.
- **Canva, ElevenLabs, Synthesia execution.** Those still go through the caller's own connector
  tools, called with the brief/spec this server hands back — see `route_channel.py`'s
  `blocked_by` reporting for why that stays a human-in-the-loop step in v0.3.
