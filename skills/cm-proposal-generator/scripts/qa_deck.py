#!/usr/bin/env python3
"""Stage 5 audit of a proposal plan: requirement coverage and content provenance.

    python qa_deck.py rfp_brief.json proposal_plan.json -o qa_report.md

This covers checks 1 and 2 of Stage 5 — the ones that are mechanical and must not be
done by eye. Check 3 (template fidelity, file validity, visual QA) runs through the pptx
skill's own QA tooling against the built .pptx; this script prints that checklist rather
than duplicating it.

Exits non-zero if any mandatory requirement is uncovered or any content block lacks both
sources and a gap marker — those are hard failures, not warnings.
"""

import argparse
import json
import sys
from pathlib import Path


def audit(brief, plan):
    requirements = {r["id"]: r for r in brief.get("requirements", [])}
    covered, blocks_missing_provenance, gaps = {}, [], []

    for section in plan.get("sections", []):
        for rid in section.get("requirement_ids", []):
            covered.setdefault(rid, []).append(section["section_id"])

        for slide in section.get("slides", []):
            for i, block in enumerate(slide.get("blocks", [])):
                where = f"{section['section_id']} / {slide['slide_id']} / block {i}"
                if block.get("gap"):
                    gaps.append(
                        {
                            "where": where,
                            "note": block.get("gap_note", "(no gap_note recorded)"),
                            "requirement_ids": section.get("requirement_ids", []),
                        }
                    )
                elif not block.get("sources"):
                    blocks_missing_provenance.append(where)

    uncovered = [rid for rid in requirements if rid not in covered]
    unknown = [rid for rid in covered if rid not in requirements]

    return {
        "requirements": requirements,
        "covered": covered,
        "uncovered": uncovered,
        "unknown": unknown,
        "gaps": gaps,
        "missing_provenance": blocks_missing_provenance,
    }


def render(result, plan):
    reqs = result["requirements"]
    uncovered_mandatory = [
        rid for rid in result["uncovered"] if reqs[rid].get("priority") == "mandatory"
    ]
    hard_fail = bool(uncovered_mandatory or result["missing_provenance"])

    lines = [
        f"# QA Report — {plan.get('run_id', 'unnamed run')}",
        "",
        f"**Status:** {'FAIL — must fix before handover' if hard_fail else 'PASS (mechanical checks)'}",
        "",
        "## 1. Requirement coverage",
        "",
        f"{len(result['covered'])} of {len(reqs)} requirements mapped to a section.",
        "",
    ]

    if result["uncovered"]:
        lines.append("### Uncovered requirements")
        lines.append("")
        for rid in sorted(result["uncovered"], key=lambda r: int(r[1:])):
            req = reqs[rid]
            mark = "**MANDATORY**" if req.get("priority") == "mandatory" else "desirable"
            lines += [f"- `{rid}` ({mark}) — {req['text']}", ""]
    else:
        lines += ["Every requirement is mapped.", ""]

    if result["unknown"]:
        lines += [
            "### Unknown requirement IDs referenced by the plan",
            "",
            "These appear in the plan but not in the brief — a mapping error:",
            "",
        ] + [f"- `{rid}`" for rid in result["unknown"]] + [""]

    lines += [
        "> Mapping is necessary but not sufficient: confirm each mapped slide's content",
        "> actually answers the requirement, rather than merely mentioning the topic.",
        "",
        "## 2. Provenance",
        "",
    ]

    if result["missing_provenance"]:
        lines += [
            "### FAIL — content blocks with neither sources nor a [GAP] marker",
            "",
            "Every block must trace to a knowledge-bank entry or be flagged as a gap.",
            "Unattributed content cannot be distinguished from fabrication once it's in a deck.",
            "",
        ] + [f"- {w}" for w in result["missing_provenance"]] + [""]
    else:
        lines += ["Every content block carries sources or a `[GAP]` marker.", ""]

    lines += [f"### Open gaps ({len(result['gaps'])})", ""]
    if result["gaps"]:
        lines += ["Action items for the practitioner before submission:", ""]
        for gap in result["gaps"]:
            exposed = ", ".join(gap["requirement_ids"]) or "none mapped"
            lines += [f"- **{gap['where']}** — {gap['note']}", f"  - Leaves exposed: {exposed}", ""]
    else:
        lines += ["None. Every planned block drew on the knowledge bank.", ""]

    budget = plan.get("slide_budget", {})
    if budget.get("cut_for_length"):
        lines += [
            "## 3. Cut for length",
            "",
            f"Slide limit {budget.get('limit')}; planned {budget.get('planned')}. Sections dropped:",
            "",
        ] + [f"- {s}" for s in budget["cut_for_length"]] + [""]

    lines += [
        "## Remaining checks (run against the built .pptx via the pptx skill)",
        "",
        "- [ ] `markitdown proposal.pptx` — content order, typos, missing content",
        "- [ ] placeholder grep for leftover template text (`lorem`, `[insert`, `xxx`, `TODO`)",
        "- [ ] `validate.py proposal.pptx --original <approved-template>` — always pass `--original`",
        "- [ ] visual QA on rendered slides — overflow, overlap, margins",
        "- [ ] template fidelity — fonts, colours and layouts still the approved template's",
        "- [ ] slide count within the RFP's limit; file named per its convention",
        "",
        "## Handover",
        "",
        "This is a **first draft for practitioner review**, not a submission-ready document.",
    ]
    deadline = plan.get("submission_deadline")
    if deadline:
        lines += ["", f"**Submission deadline: {deadline}**"]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("brief", type=Path)
    ap.add_argument("plan", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("qa_report.md"))
    args = ap.parse_args()

    brief = json.loads(args.brief.read_text(encoding="utf-8"))
    plan = json.loads(args.plan.read_text(encoding="utf-8"))

    result = audit(brief, plan)
    report = render(result, plan)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")

    reqs = result["requirements"]
    uncovered_mandatory = [
        rid for rid in result["uncovered"] if reqs[rid].get("priority") == "mandatory"
    ]

    print(f"Coverage: {len(result['covered'])}/{len(reqs)} requirements mapped")
    print(f"Gaps: {len(result['gaps'])}   Unattributed blocks: {len(result['missing_provenance'])}")
    print(f"Report -> {args.out}")

    if uncovered_mandatory:
        print(f"FAIL: uncovered mandatory requirements: {', '.join(uncovered_mandatory)}", file=sys.stderr)
    if result["missing_provenance"]:
        print(f"FAIL: {len(result['missing_provenance'])} block(s) without sources or [GAP]", file=sys.stderr)
    return 1 if (uncovered_mandatory or result["missing_provenance"]) else 0


if __name__ == "__main__":
    sys.exit(main())
