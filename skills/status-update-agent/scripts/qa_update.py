#!/usr/bin/env python3
"""Stage 5 audit: does the written update match what actually changed?

    python qa_update.py change_brief.json status_update.md -o qa_report.md

Three mechanical checks, none of which should be done by eye:

1. **Attribution** — every claim carries a `[C#]` tag or an explicit `[JUDGEMENT]` marker.
   There is no third state, so an invented movement cannot hide among real ones.
2. **Valid citations** — every `[C#]` cited exists in the brief.
3. **Coverage** — every high-materiality change is either mentioned or explicitly waived
   with `<!-- omit: C7 reason -->`. Medium changes are reported as warnings.

Exits non-zero on an unattributed claim, an unknown citation, or an uncovered high change.
Tone, framing and whether the update is any good to listen to are the consultant's call —
this only checks it is true to the documents.
"""

import argparse
import re
import sys
from pathlib import Path
import json

CITATION = re.compile(r"\[(C\d+)\]")
OMIT = re.compile(r"<!--\s*omit:\s*(C\d+)\s*(.*?)-->", re.S)
JUDGEMENT = "[JUDGEMENT]"
# Structural lines assert nothing: headings, quotes, rules, HTML comments, table pipes,
# and an italic-only metadata line under a heading.
SKIP = re.compile(r"^\s*(#|>|---|\*\*\*|<!--|\||```|$)")
META = re.compile(r"^\s*_[^_].*_\s*$")
BULLET = re.compile(r"^\s*(?:[-*+]|\d+\.)\s")


def claim_blocks(markdown):
    """A claim is a whole bullet or paragraph, not a line. Markdown wraps, and a citation
    on the second line of a bullet still attributes the whole bullet."""
    blocks, current, in_code = [], None, False

    def flush():
        nonlocal current
        if current and len(re.sub(r"[^A-Za-z]", "", current[1])) >= 12:
            blocks.append((current[0], " ".join(current[1].split())))
        current = None

    for n, line in enumerate(markdown.splitlines(), start=1):
        if line.strip().startswith("```"):
            in_code = not in_code
            flush()
            continue
        if in_code or SKIP.match(line) or META.match(line):
            flush()
            continue
        if BULLET.match(line) or current is None:
            flush()
            current = [n, line.strip()]
        else:
            current[1] += " " + line.strip()
    flush()
    return blocks


def audit(brief, markdown):
    known = {c["change_id"]: c for c in brief["changes"]}
    cited, unattributed = set(), []

    for n, line in claim_blocks(markdown):
        tags = CITATION.findall(line)
        cited.update(tags)
        if not tags and JUDGEMENT not in line:
            unattributed.append((n, line))

    unknown = sorted(t for t in cited if t not in known)
    omitted = {m.group(1): m.group(2).strip() for m in OMIT.finditer(markdown)}

    def uncovered(level):
        return [
            c for c in brief["changes"]
            if c["materiality"] == level
            and c["change_id"] not in cited
            and c["change_id"] not in omitted
            and not c.get("subsumed_by")
        ]

    return {
        "cited": sorted(cited, key=lambda t: int(t[1:])),
        "unknown": unknown,
        "unattributed": unattributed,
        "omitted": omitted,
        "bad_omits": sorted(t for t in omitted if t not in known),
        "uncovered_high": uncovered("high"),
        "uncovered_medium": uncovered("medium"),
        "known": known,
    }


def render(result, brief):
    def line_of(change):
        return (
            f"- `[{change['change_id']}]` {change['change_type']} — "
            f"{change['item_label']} ({change['document']})"
        )

    failures = (
        len(result["unknown"])
        + len(result["unattributed"])
        + len(result["uncovered_high"])
        + len(result["bad_omits"])
    )
    out = [
        "# Status update QA",
        "",
        f"**{'FAIL' if failures else 'PASS'}** — {failures} blocking issue(s).",
        "",
        f"- Changes in brief: {brief['totals']['changes']} "
        f"({brief['totals']['by_materiality']['high']} high)",
        f"- Changes cited in the update: {len(result['cited'])}",
        f"- Explicit omissions: {len(result['omitted'])}",
        "",
        "## 1. Attribution",
        "",
    ]
    if result["unattributed"]:
        out.append("Claims with neither a `[C#]` citation nor `[JUDGEMENT]`:")
        out.append("")
        out += [f"- line {n}: {line[:120]}" for n, line in result["unattributed"]]
    else:
        out.append("✅ Every claim is attributed.")

    out += ["", "## 2. Citations", ""]
    if result["unknown"]:
        out.append("Cited but not in the change brief — these are inventions:")
        out += [f"- `[{t}]`" for t in result["unknown"]]
    else:
        out.append("✅ All citations resolve to a change in the brief.")
    if result["bad_omits"]:
        out += ["", "Omission markers for unknown change IDs:"]
        out += [f"- `[{t}]`" for t in result["bad_omits"]]

    out += ["", "## 3. Coverage", ""]
    if result["uncovered_high"]:
        out.append("High-materiality changes neither mentioned nor waived — **blocking**:")
        out.append("")
        out += [line_of(c) for c in result["uncovered_high"]]
    else:
        out.append("✅ Every high-materiality change is mentioned or explicitly waived.")
    if result["uncovered_medium"]:
        out += [
            "",
            f"Medium-materiality changes not mentioned ({len(result['uncovered_medium'])}) "
            "— not blocking, but check none of these is the thing the meeting cares about:",
            "",
        ]
        out += [line_of(c) for c in result["uncovered_medium"]]

    if result["omitted"]:
        out += ["", "## Deliberate omissions", ""]
        for tag, reason in sorted(result["omitted"].items(), key=lambda kv: int(kv[0][1:])):
            change = result["known"].get(tag)
            what = f"{change['change_type']} on {change['item_label']}" if change else "unknown change"
            out.append(f"- `[{tag}]` {what} — {reason or '(no reason recorded)'}")

    out += [
        "",
        "## Not checked here",
        "",
        "- Whether the framing is right for this audience, and whether the ask is the "
        "right ask — the consultant's call.",
        "- Whether the source documents are themselves accurate or up to date. A tracker "
        "nobody updated produces a truthful 'nothing changed' update.",
        "",
    ]
    return "\n".join(out), failures


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("brief", help="change_brief.json from write_update.py")
    ap.add_argument("update", help="the written status_update.md")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()

    brief = json.loads(Path(args.brief).read_text(encoding="utf-8"))
    markdown = Path(args.update).read_text(encoding="utf-8")
    report, failures = render(audit(brief, markdown), brief)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(report + "\n", encoding="utf-8")
        print(f"{args.out}: {'FAIL' if failures else 'PASS'} ({failures} blocking)")
    else:
        print(report)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
