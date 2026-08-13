#!/usr/bin/env python3
"""Stage 6 audit of a proposal plan: requirement coverage and content provenance.

    python qa_deck.py rfp_brief.json proposal_plan.json -o qa_report.md

This audits the *plan*. `qa_pptx.py` audits the built file — package integrity, template
fidelity, overflow — and both are required before handover; this script prints the command
for the other rather than duplicating its checks.

Coverage is scored by requirement `kind`, because "answered" is not one thing. A
`submission-rule` ("responses must be PDF, named <ref>-CM.pdf") is a real requirement that
no slide can cover — the deck as an artifact complies with it. Counting those against
slide coverage produces a report that can never reach PASS, and a report that can never
pass is a report nobody reads, which is how the genuinely uncovered requirement beside it
gets missed. They are listed separately, as a pre-submission checklist.

Exits non-zero if any mandatory requirement is uncovered or any content block lacks both
sources and a gap marker — those are hard failures, not warnings.
"""

import argparse
import json
import sys
from pathlib import Path


SLIDE_KINDS = ("proposal-content", "delivery-obligation", "commercial-constraint")


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

    # A submission rule ("responses must be PDF, 20 pages, named <ref>-CM.pdf") is a
    # requirement, but no slide answers it — the deck as an artifact does. Holding it to
    # the slide-coverage test produces a permanently failing report that gets ignored,
    # which is how the genuinely uncovered requirement next to it gets missed.
    needs_slide = [rid for rid, r in requirements.items()
                   if r.get("kind", "proposal-content") in SLIDE_KINDS]
    document_rules = [rid for rid in requirements if rid not in needs_slide]

    uncovered = [rid for rid in needs_slide if rid not in covered]
    unknown = [rid for rid in covered if rid not in requirements]

    return {
        "requirements": requirements,
        "covered": covered,
        "needs_slide": needs_slide,
        "document_rules": document_rules,
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
    ]

    needs_slide = set(result["needs_slide"])
    mapped = len(needs_slide & set(result["covered"]))
    rules = len(result["document_rules"])
    tail = "."
    if rules:
        tail = (f"; {rules} further requirement{'s' if rules > 1 else ''} "
                f"govern{'' if rules > 1 else 's'} the response document itself and "
                f"{'are' if rules > 1 else 'is'} checked against the deck instead.")

    lines += [
        "## 1. Requirement coverage",
        "",
        f"{mapped} of {len(needs_slide)} requirements that need a slide are mapped to a "
        f"section{tail}",
        "",
    ]

    if result["uncovered"]:
        lines.append("### Uncovered requirements")
        lines.append("")
        for rid in sorted(result["uncovered"], key=lambda r: int(r[1:])):
            req = reqs[rid]
            mark = "**MANDATORY**" if req.get("priority") == "mandatory" else "desirable"
            kind = req.get("kind", "proposal-content")
            lines += [f"- `{rid}` ({mark}, {kind}) — {req['text']}", ""]
    else:
        lines += ["Every requirement that needs a slide is mapped.", ""]

    if result["document_rules"]:
        lines += [
            "### Rules about the response document itself",
            "",
            "No slide covers these; the deck has to comply with them. Check each before "
            "submission:",
            "",
        ]
        for rid in sorted(result["document_rules"], key=lambda r: int(r[1:])):
            lines.append(f"- [ ] `{rid}` — {reqs[rid]['text']}")
        lines.append("")

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

    # The plan names the template it was built against; a .potx/.pptx path means the
    # pptx path even when the plan predates this field.
    template = plan.get("template", {})
    template_path = str(template.get("path", ""))
    html_path = (template.get("kind") == "html"
                 or not template_path.lower().endswith((".potx", ".pptx")))

    if html_path:
        lines += [
            "## Remaining checks (run against the rendered .html)",
            "",
            "- [ ] open the deck and step through every slide — arrow keys or space",
            "- [ ] **text overflow** — the most common defect; `.slide-body` clips rather than",
            "      spilling, so an overflowing slide loses content silently. Check the bottom",
            "      of every text-heavy slide, case studies first.",
            "- [ ] leftover placeholder text (`lorem`, `[insert`, `xxx`, `TODO`)",
            "- [ ] every `[GAP]` panel is visible and reads as an action, not as content",
            "- [ ] slide count within the RFP's limit",
            "- [ ] before sending to a client: re-render with `--sources hidden`, and confirm",
            "      the RFP's required file format (usually PDF — print the deck with",
            "      `?print-pdf` appended to the URL) and naming convention",
            "",
            "> The HTML path is the PoC renderer. The RFP's format requirement and the firm's",
            "> approved template still govern what can actually be submitted.",
            "",
        ]
    else:
        lines += [
            "## Remaining checks (run against the built .pptx)",
            "",
            "```bash",
            f"python scripts/qa_pptx.py proposal.pptx --original {template_path or '<approved-template>'}",
            "```",
            "",
            "That covers package integrity, template fidelity, text overflow and leftover",
            "scaffolding mechanically. Always pass `--original`: without it nothing can",
            "confirm the template's own master, layouts and theme were left alone.",
            "",
            "Then by eye:",
            "",
            "- [ ] open the deck and step through every slide at full size",
            "- [ ] every `[GAP]` panel reads as an action, not as content",
            "- [ ] slide count within the RFP's limit; file named per its convention",
            "- [ ] before sending to a client: re-render with `--sources hidden`",
            "",
        ]

    lines += [
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

    needs_slide = set(result["needs_slide"])
    print(f"Coverage: {len(needs_slide & set(result['covered']))}/{len(needs_slide)} "
          f"requirements needing a slide are mapped"
          + (f"  ({len(result['document_rules'])} document rule(s) listed separately)"
             if result["document_rules"] else ""))
    print(f"Gaps: {len(result['gaps'])}   Unattributed blocks: {len(result['missing_provenance'])}")
    print(f"Report -> {args.out}")

    if uncovered_mandatory:
        print(f"FAIL: uncovered mandatory requirements: {', '.join(uncovered_mandatory)}", file=sys.stderr)
    if result["missing_provenance"]:
        print(f"FAIL: {len(result['missing_provenance'])} block(s) without sources or [GAP]", file=sys.stderr)
    return 1 if (uncovered_mandatory or result["missing_provenance"]) else 0


if __name__ == "__main__":
    sys.exit(main())
