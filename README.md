# Strategic Change

A Claude Code plugin bundling 12 change-management consulting framework skills, a multi-framework assessment orchestrator, and a cutover communications planning tool, built for a Strategic Change presentation and consulting workflow.

## What's included

| Skill | Framework |
|---|---|
| `dice-framework` | BCG DICE |
| `technical-adaptive-change` | Heifetz Technical vs. Adaptive |
| `theory-e-o-change` | Beer & Nohria Theory E/O |
| `kotter-8-step` | Kotter's 8-Step Change Model |
| `persuasion-case-for-change` | Garvin & Roberto Four-Stage Persuasion |
| `tipping-point` | Gladwell's Tipping Point |
| `immunity-to-change` | Kegan & Lahey Immunity to Change |
| `six-steps-change` | Beer, Eisenstat & Spector Six Steps |
| `productive-distress` | Heifetz's Productive Zone of Disequilibrium |
| `critical-few-behaviours` | McKinsey Influence Model |
| `dual-operating-system` | Kotter's Dual Operating System (Accelerate) |
| `network-position` | Organizational network analysis / stakeholder mapping |
| `strategic-change-assessment` | Orchestrator — runs a project narrative through whichever of the above are suitable and synthesizes findings across them |
| `cutover-comms-plan` | Delivery tool — builds a cutover communications plan workbook from complexity-based cadence rules |

Each skill's frontmatter `name:` field carries a `-v1.0` suffix (e.g. `dice-framework-v1.0`), marking this as the post-review baseline — all 12 framework skills were live-tested via the Skill tool before this bundle was packaged.

## Cutover comms plan

`cutover-comms-plan` is the one non-diagnostic skill in the bundle. It takes a
description of a cutover and produces an Excel communications plan — one row per
comms, with Purpose, Audience, Channel, Sender, Owner, Approver and Dependencies,
plus a deliberately blank `Comms Content Link` column for later linkage to the
drafted content.

How many comms a cutover gets is rule-driven rather than guessed:

- **Brand-new system → 2** (pre go-live awareness, go-live)
- **Upgrade or change to an existing system → 5** (T-14, T-7, T-1, cutover begins, go-live)
- Decommission → 4; silent migration → 2
- Plus modifiers for downtime, required user action, external audiences, hypercare,
  multi-wave rollouts, long cutover windows, go/no-go gates, regulated contexts and
  training prerequisites — with a floor of 2 and a ceiling of 6 push comms per audience.

Two ways to build it:

- **`assets/cutover-comms-plan.html`** — an editable artifact. Applies the rules live,
  runs nine validation checks as you type, and exports to `.xlsx` in the browser with
  no library or server involved. Edits persist locally between sessions.
- **`scripts/build_comms_plan.py`** (requires `openpyxl`) — generates the same workbook
  from a JSON spec, or populates the member's own existing template, matching their
  column names by synonym and preserving their formatting.

The artifact's "Export spec JSON" produces exactly the spec the script consumes, so the
two compose: draft and edit in the browser, then push the result into a client template.

## Installing on another machine

**Option A — direct install (simplest):**
1. Copy this entire `strategic-change-plugin/` folder to the other machine.
2. Point Claude Code at it as a plugin source (e.g. a local path or a git remote once this folder is pushed to a repo) using whatever plugin-install command your Claude Code version provides.

**Option B — via the marketplace listing:**
This folder also includes `.claude-plugin/marketplace.json`, so once it's pushed to a git repository, others should be able to run something like:
```
/plugin marketplace add <your-repo-url>
```
then install the `strategic-change` plugin from that marketplace.

⚠️ **Caveat on `marketplace.json`**: this was built from general Claude Code plugin conventions and one real `plugin.json` example found locally — I did not have a verified `marketplace.json` reference to check the exact schema against in this environment. Before relying on this for distribution, test the install on a second machine (or a fresh Claude Code profile) and adjust the schema if it doesn't load as expected.

## Source project

Built in the "Strategic Change Project" working directory alongside reference PDFs (Kotter's *Leading Change*, *HBR's 10 Must Reads on Change Management*, Cameron & Green's *Making Sense of Change Management*, and *The Theory and Practice of Change Management*) used to ground each skill's framework background.
