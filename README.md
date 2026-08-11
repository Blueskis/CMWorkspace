# Strategic Change

A Claude Code plugin bundling 12 change-management consulting framework skills, a multi-framework assessment orchestrator, and a change impact assessment generator — built for a Strategic Change presentation and consulting workflow.

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
| `change-impact-assessment` | Deliverable generator — builds a baseline change impact assessment workbook from a programme's own documents |

Each skill's frontmatter `name:` field carries a `-v1.0` suffix (e.g. `dice-framework-v1.0`), marking this as the post-review baseline — all 12 framework skills were live-tested via the Skill tool before this bundle was packaged.

## Change impact assessment

`change-impact-assessment` is the odd one out: the 13 skills above are diagnostic, and this one produces a client deliverable. It reads a system implementation's own source material — interview and workshop notes, Signavio/BPMN process design, functional specifications, org design — and generates a multi-sheet Excel workbook:

- **Impact Register** — one row per process change × stakeholder group, carrying as-is → to-be, five weighted impact dimensions, a Low/Medium/High/Critical rating, anticipated resistance, and the training and communication response derived from that rating
- **Impact Heatmap** — where the change lands, by stakeholder group and by workstream
- **Training Plan** — delivery method, duration and effort roll-up in person-hours and days
- **Comms Plan** — key messages by audience and wave, with named senders
- **Traceability** — the source documents behind each row, and the open questions for business validation

Ratings, effort and roll-ups are live Excel formulas, so re-scoring an impact in a validation workshop updates the whole pack. `skills/change-impact-assessment/examples/` holds a complete worked example for an SAP S/4HANA and Ariba implementation — six source documents and the 20-impact assessment they produce.

Requires `openpyxl` (`pip install openpyxl`).

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
