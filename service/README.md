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
Streamable HTTP on `PORT` (default 8000) at the path **`/mcp`** — the transport a **remote**
claude.ai custom connector requires. Set `CM_COMMS_TRANSPORT=stdio` instead for a local Claude
desktop MCP config, where stdio is what's expected. Don't run `fastmcp run server.py` for a
remote deployment — that CLI defaults to stdio regardless of this env var; run
`python server.py` directly so the `__main__` block's transport selection takes effect.

Verified on fastmcp 3.4.7: the server boots, registers all five tools, binds
`http://0.0.0.0:$PORT/mcp`, and completes an MCP `initialize` handshake there.

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

## Two ways to run it — and only one of them reaches the artifact

| | Local (stdio) | Deployed (HTTP) |
|---|---|---|
| Needs | Claude desktop app, server on your machine | A deployed HTTPS URL |
| Costs | Nothing | Render free tier, or $7/mo always-on |
| **Drives the console artifact** | **No** — see below | **Yes** |
| Good for | Talking to Claude directly with the tools available | The artifact's submit button; sharing with others |

**Why local does not drive the artifact.** The `mcp` capability defines `host:<name>` servers —
an MCP server on the viewer's own machine, bridged by the desktop app, needing no hosting at
all. That would have been the zero-cost path. It is **not granted on this account**: publishing
a page that declares `host:cm-comms` is refused outright with `capabilities.mcp: unavailable`,
while the same page declaring only `cm-comms` publishes fine. Verified by isolating the two.
So the artifact needs a deployed URL; there is no free local shortcut for it.

Local stdio is still worth setting up for the *other* front door — using the pipeline by
talking to Claude in the desktop app, no artifact involved:

```json
{
  "mcpServers": {
    "cm-comms": {
      "command": "python",
      "args": ["/absolute/path/to/CMWorkspace/service/server.py"],
      "env": { "ANTHROPIC_API_KEY": "sk-ant-...", "CM_COMMS_TRANSPORT": "stdio" }
    }
  }
}
```

### Deploy to Render — the route that makes the artifact work

`render.yaml` is at the **repo root** (Render's Blueprint discovery and the one-click link both
look there); `service/Dockerfile` builds from the repo root because `runner.py` shells out to
`skills/` and `proposal-assets/`.

1. One-click: **https://render.com/deploy?repo=https://github.com/Blueskis/CMWorkspace**
   — or Render dashboard → **New** → **Blueprint** → point at the repo.
2. Render prompts for the `sync: false` vars: `ANTHROPIC_API_KEY`, `BRAND_PROFILE_PATH` (see
   the demo-data note above), and `ARTIFACT_BASE_URL` (leave blank until you have real object
   storage — `produce` still works, just without public download links).
3. Deploy, then take the assigned URL and **append `/mcp`**:

   ```
   https://cm-comms-<hash>.onrender.com/mcp
   ```

   That path is the MCP endpoint. A connector pointed at the bare host will not work.
4. claude.ai → **Settings → Connectors → Add custom connector** → paste that URL → name it
   **exactly `cm-comms`**, since the artifact matches on the connector's display name.

The blueprint deploys on Render's **free** plan, which spins down after 15 minutes without
traffic and loses its filesystem when it does. Within one generation that's harmless — the four
calls run seconds apart and keep it awake — but a run abandoned for 15+ minutes loses its
`run_id` state, and the first request after a spin-down takes ~50s. `render.yaml` carries the
commented `plan: starter` + disk block that removes both limits.

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
- **Canva and ElevenLabs execution.** Those still go through the caller's own connector
  tools, called with the brief/spec this server hands back — see `route_channel.py`'s
  `blocked_by` reporting for why that stays a human-in-the-loop step in v0.3.
