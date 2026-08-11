# Strategic Change

A Claude Code plugin bundling 12 change-management consulting framework skills plus a multi-framework assessment orchestrator, built for a Strategic Change presentation and consulting workflow.

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
| `cm-effort-estimation` | Pursuit-side effort and pricing estimator — reads an RFP scope (Word/PDF/text), benchmarks it against past project quotes, and outputs a priced schedule of deliverables |

## Pursuit estimating tool

`skills/cm-effort-estimation/assets/cm-effort-estimator.html` is a single self-contained page — open it in any browser, no install, no server, no network calls. It parses .docx and .pdf scope documents in the browser, reads scope drivers out of them (impacted headcount, business units, countries, languages, waves, duration, training modules), and prices a schedule of CM deliverables against an editable table of your past project quotes. Day rates and effort-per-unit are medians of your own history indexed to the current year; anything without history falls back to a standard assumption and is labelled as such. Exports the priced schedule to CSV or Markdown, and prints to PDF.

Each skill's frontmatter `name:` field carries a `-v1.0` suffix (e.g. `dice-framework-v1.0`), marking this as the post-review baseline — all 12 framework skills were live-tested via the Skill tool before this bundle was packaged.

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
