#!/usr/bin/env python3
"""Stage 5 audit of a comms plan: coverage, provenance, constraints, cross-channel consistency.

    python qa_comms.py change_brief.json comms_plan.json -o qa_report.md

Five checks, all required:

  1. Message x audience coverage   -- every mandatory message reaches every audience it
                                       targets, through at least one channel run.
  2. Provenance                    -- every block carries sources or a gap + gap_note.
  3. Mandatory-field presence      -- every mandatory message was drafted into at least
                                       one channel run somewhere, not just assigned in
                                       the coverage matrix.
  4. Channel constraint compliance -- subject length, word counts, slide counts, checked
                                       against channel_registry.json's constraints.
  5. Cross-channel consistency     -- every date and figure drafted for this run must
                                       agree everywhere it appears; an unconfirmed date
                                       must read as unconfirmed everywhere it appears.

Checks 1, 2 and 3 mirror cm-proposal-generator's qa_deck.py -- mandatory items uncovered
or unattributed are hard failures, not warnings. Check 5 has no analogue in qa_deck.py:
a proposal deck is one document, so nothing can disagree with itself; a comms pack is
several documents describing the same change, and disagreement between them is exactly
what a practitioner reviewing by eye is likely to miss.

Exits non-zero on any hard failure.
"""

import argparse
import json
import re
import sys
from pathlib import Path

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

DATE_PATTERNS = [
    # "14 September 2026" / "14 Sept 2026"
    re.compile(
        r"\b(?P<d>\d{1,2})(?:st|nd|rd|th)?\s+(?P<m>[A-Za-z]{3,9})\s+(?P<y>\d{4})\b"
    ),
    # "September 14, 2026" / "September 14 2026"
    re.compile(
        r"\b(?P<m>[A-Za-z]{3,9})\s+(?P<d>\d{1,2})(?:st|nd|rd|th)?,?\s+(?P<y>\d{4})\b"
    ),
    # "14/09/2026" or "14-09-2026" (day/month/year, the convention used elsewhere in this repo)
    re.compile(r"\b(?P<d>\d{1,2})[/-](?P<m>\d{1,2})[/-](?P<y>\d{4})\b"),
]

QUALIFYING_LANGUAGE_RE = re.compile(
    r"\b(provisional|subject to change|tbc|to be confirmed|unconfirmed|approx|"
    r"around|expected|likely|proposed|draft date|pending confirmation)\b|\?",
    re.IGNORECASE,
)

NUMBER_RE = re.compile(r"\b\d[\d,]{2,}\b")


def normalize_date(text):
    """Return the first date found in text as (year, month, day), or None."""
    for pat in DATE_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        g = m.groupdict()
        try:
            if g["m"].isdigit():
                month = int(g["m"])
            else:
                month = MONTHS.get(g["m"].lower()[:3]) or MONTHS.get(g["m"].lower())
            if not month:
                continue
            return (int(g["y"]), month, int(g["d"]))
        except (ValueError, KeyError):
            continue
    return None


def block_text(block):
    """Flatten a block's content (string, array, or object) into one string."""
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(str(item) for item in content)
    if isinstance(content, dict):
        return " ".join(str(v) for v in content.values())
    return ""


def source_ids(block, prefix):
    return [s for s in block.get("sources", []) if re.match(rf"^{prefix}[0-9]+$", s)]


def word_count(text):
    return len(text.split())


def audience_ids_for_message(message, all_audience_ids):
    ids = message.get("audience_ids") or []
    return ids if ids else list(all_audience_ids)


def check_coverage(brief, plan):
    audiences = {a["id"]: a for a in brief.get("audiences", [])}
    messages = brief.get("messages", [])
    runs = plan.get("channel_runs", [])

    # audience_id -> set of message_ids actually carried by some channel_run for it
    carried_per_audience = {}
    for run in runs:
        aid = run.get("audience_id")
        carried_per_audience.setdefault(aid, set()).update(run.get("message_ids", []))

    uncovered, informational = [], []
    for msg in messages:
        mandatory = msg.get("mandatory", True)
        targets = audience_ids_for_message(msg, audiences.keys())
        for aid in targets:
            carried = carried_per_audience.get(aid, set())
            if msg["id"] not in carried:
                entry = {"message_id": msg["id"], "audience_id": aid, "kind": msg.get("kind")}
                (uncovered if mandatory else informational).append(entry)

    return uncovered, informational


def check_provenance(plan):
    missing_provenance, missing_gap_note = [], []
    for run in plan.get("channel_runs", []):
        for i, block in enumerate(run.get("blocks", [])):
            where = f"{run.get('run_id', '?')} / block {i} ({block.get('kind', '?')})"
            if block.get("gap"):
                if not block.get("gap_note"):
                    missing_gap_note.append(where)
            elif not block.get("sources"):
                missing_provenance.append(where)
    return missing_provenance, missing_gap_note


def check_drafted_somewhere(brief, plan):
    """Every mandatory message must appear in message_ids of at least one channel_run,
    anywhere -- distinct from per-audience coverage: this catches a message the brief
    extracted that no channel run picked up for ANY audience, not just a specific one."""
    drafted = set()
    for run in plan.get("channel_runs", []):
        drafted.update(run.get("message_ids", []))

    never_drafted = []
    for msg in brief.get("messages", []):
        if msg.get("mandatory", True) and msg["id"] not in drafted:
            never_drafted.append({"message_id": msg["id"], "kind": msg.get("kind")})
    return never_drafted


def check_constraints(plan, registry):
    channels = {c["id"]: c for c in registry.get("channels", [])}
    violations = []

    for run in plan.get("channel_runs", []):
        channel = channels.get(run.get("channel_id"))
        if channel is None:
            continue
        constraints = channel.get("constraints", {})
        blocks = run.get("blocks", [])
        run_id = run.get("run_id", "?")

        if "subject_max_chars" in constraints:
            for b in blocks:
                if b.get("kind") == "subject":
                    length = len(block_text(b))
                    if length > constraints["subject_max_chars"]:
                        violations.append(
                            f"{run_id}: subject is {length} chars, limit "
                            f"{constraints['subject_max_chars']}"
                        )

        if "body_max_words" in constraints:
            prose = " ".join(
                block_text(b) for b in blocks if b.get("kind") in ("paragraph", "heading")
            )
            wc = word_count(prose)
            if wc > constraints["body_max_words"]:
                violations.append(
                    f"{run_id}: body is {wc} words, limit {constraints['body_max_words']}"
                )

        if "max_slides" in constraints:
            slide_count = sum(1 for b in blocks if b.get("kind") == "heading")
            if slide_count > constraints["max_slides"]:
                violations.append(
                    f"{run_id}: {slide_count} slides, limit {constraints['max_slides']}"
                )

        if "max_words" in constraints:
            all_text = " ".join(block_text(b) for b in blocks)
            wc = word_count(all_text)
            if wc > constraints["max_words"]:
                violations.append(
                    f"{run_id}: {wc} words, limit {constraints['max_words']}"
                )

    return violations


def check_cross_channel_consistency(brief, plan):
    timeline = {t["id"]: t for t in brief.get("timeline", [])}
    messages = {m["id"]: m for m in brief.get("messages", [])}

    date_conflicts, figure_conflicts, unmarked_unconfirmed = [], [], []

    # --- dates: group blocks by any T-id present in their sources ---
    by_timeline = {}
    for run in plan.get("channel_runs", []):
        for block in run.get("blocks", []):
            for tid in source_ids(block, "T"):
                text = block_text(block)
                d = normalize_date(text)
                by_timeline.setdefault(tid, []).append(
                    {"run_id": run.get("run_id"), "text": text, "date": d}
                )

    for tid, occurrences in by_timeline.items():
        dated = [o for o in occurrences if o["date"] is not None]
        distinct = {o["date"] for o in dated}
        if len(distinct) > 1:
            date_conflicts.append(
                {
                    "timeline_id": tid,
                    "occurrences": [
                        {"run_id": o["run_id"], "text": o["text"]} for o in dated
                    ],
                }
            )

        # unconfirmed-date-presented-as-settled: only meaningful once >=1 occurrence exists
        t = timeline.get(tid)
        if t and t.get("confirmed") is False:
            for o in occurrences:
                if not QUALIFYING_LANGUAGE_RE.search(o["text"]):
                    unmarked_unconfirmed.append(
                        {"timeline_id": tid, "run_id": o["run_id"], "text": o["text"]}
                    )

    # --- figures: group blocks by any M-id present in their sources, only for messages
    #     whose own brief text carries a number (a genuine "figure" message) ---
    by_message = {}
    for run in plan.get("channel_runs", []):
        for block in run.get("blocks", []):
            for mid in source_ids(block, "M"):
                by_message.setdefault(mid, []).append(
                    {"run_id": run.get("run_id"), "text": block_text(block)}
                )

    for mid, occurrences in by_message.items():
        msg = messages.get(mid)
        if not msg or not NUMBER_RE.search(msg.get("text", "")):
            continue
        seen = {}
        for o in occurrences:
            for raw in NUMBER_RE.findall(o["text"]):
                normalized = raw.replace(",", "")
                seen.setdefault(normalized, []).append({"run_id": o["run_id"], "raw": raw})
        if len(seen) > 1:
            figure_conflicts.append({"message_id": mid, "values": seen})

    return date_conflicts, figure_conflicts, unmarked_unconfirmed


def render(brief, plan, results):
    (
        uncovered,
        informational_uncovered,
        missing_provenance,
        missing_gap_note,
        never_drafted,
        constraint_violations,
        date_conflicts,
        figure_conflicts,
        unmarked_unconfirmed,
    ) = results

    hard_fail = any(
        [
            uncovered,
            missing_provenance,
            missing_gap_note,
            never_drafted,
            constraint_violations,
            date_conflicts,
            figure_conflicts,
            unmarked_unconfirmed,
        ]
    )

    lines = [
        f"# QA Report — {plan.get('run_id', 'unnamed run')}",
        "",
        f"**Status:** {'FAIL — must fix before handover' if hard_fail else 'PASS (mechanical checks)'}",
        "",
        "## 1. Message x audience coverage",
        "",
    ]

    if uncovered:
        lines.append("### Uncovered mandatory message x audience pairs")
        lines.append("")
        for u in uncovered:
            lines.append(f"- `{u['message_id']}` ({u.get('kind', '?')}) not reaching `{u['audience_id']}`")
        lines.append("")
    else:
        lines += ["Every mandatory message reaches every audience it targets.", ""]

    if informational_uncovered:
        lines += ["### Non-mandatory messages not covered (informational only)", ""]
        for u in informational_uncovered:
            lines.append(f"- `{u['message_id']}` ({u.get('kind', '?')}) not reaching `{u['audience_id']}`")
        lines.append("")

    lines += ["## 2. Provenance", ""]
    if missing_provenance:
        lines += [
            "### FAIL — content blocks with neither sources nor a gap marker",
            "",
            "Every block must trace to a message, a knowledge-bank entry, or be flagged as a gap.",
            "",
        ] + [f"- {w}" for w in missing_provenance] + [""]
    else:
        lines += ["Every content block carries sources or a gap marker.", ""]

    if missing_gap_note:
        lines += [
            "### FAIL — gap declared without a gap_note",
            "",
        ] + [f"- {w}" for w in missing_gap_note] + [""]

    lines += ["## 3. Mandatory-field presence per draft", ""]
    if never_drafted:
        lines += [
            "### Mandatory messages extracted at Stage 1 but never drafted into any channel",
            "",
        ] + [f"- `{m['message_id']}` ({m.get('kind', '?')})" for m in never_drafted] + [""]
    else:
        lines += ["Every mandatory message was drafted into at least one channel run.", ""]

    lines += ["## 4. Channel constraint compliance", ""]
    if constraint_violations:
        lines += ["### Violations", ""] + [f"- {v}" for v in constraint_violations] + [""]
    else:
        lines += ["Every channel run is within its registered constraints.", ""]

    lines += ["## 5. Cross-channel consistency", ""]
    if date_conflicts:
        lines += ["### Date conflicts", ""]
        for c in date_conflicts:
            lines.append(f"- `{c['timeline_id']}` stated differently across channels:")
            for o in c["occurrences"]:
                lines.append(f"  - {o['run_id']}: \"{o['text'].strip()}\"")
        lines.append("")
    if figure_conflicts:
        lines += ["### Figure conflicts", ""]
        for c in figure_conflicts:
            lines.append(f"- `{c['message_id']}` stated differently across channels:")
            for val, occs in c["values"].items():
                for o in occs:
                    lines.append(f"  - {o['run_id']}: \"{o['raw']}\"")
        lines.append("")
    if unmarked_unconfirmed:
        lines += ["### Unconfirmed dates presented as settled", ""]
        for u in unmarked_unconfirmed:
            lines.append(
                f"- `{u['timeline_id']}` is unconfirmed in change_brief.json but "
                f"{u['run_id']} states it with no qualifying language: \"{u['text'].strip()}\""
            )
        lines.append("")
    if not (date_conflicts or figure_conflicts or unmarked_unconfirmed):
        lines += ["No conflicts found across drafted channels.", ""]

    lines += [
        "## Handover",
        "",
        "This is a **first draft for practitioner review**, not cleared-for-distribution communications.",
    ]

    return "\n".join(lines), hard_fail


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("brief", type=Path)
    ap.add_argument("plan", type=Path)
    ap.add_argument(
        "-r", "--registry", type=Path,
        default=Path(__file__).parent.parent / "schemas" / "channel_registry.json",
        help="Path to channel_registry.json (default: the registry shipped with this skill)",
    )
    ap.add_argument("-o", "--out", type=Path, default=Path("qa_report.md"))
    args = ap.parse_args()

    brief = json.loads(args.brief.read_text(encoding="utf-8"))
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    registry = json.loads(args.registry.read_text(encoding="utf-8"))

    uncovered, informational_uncovered = check_coverage(brief, plan)
    missing_provenance, missing_gap_note = check_provenance(plan)
    never_drafted = check_drafted_somewhere(brief, plan)
    constraint_violations = check_constraints(plan, registry)
    date_conflicts, figure_conflicts, unmarked_unconfirmed = check_cross_channel_consistency(brief, plan)

    results = (
        uncovered,
        informational_uncovered,
        missing_provenance,
        missing_gap_note,
        never_drafted,
        constraint_violations,
        date_conflicts,
        figure_conflicts,
        unmarked_unconfirmed,
    )
    report, hard_fail = render(brief, plan, results)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")

    print(
        f"Coverage: {len(uncovered)} uncovered mandatory pair(s)   "
        f"Gaps/provenance issues: {len(missing_provenance) + len(missing_gap_note)}   "
        f"Consistency conflicts: {len(date_conflicts) + len(figure_conflicts) + len(unmarked_unconfirmed)}"
    )
    print(f"Report -> {args.out}")

    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
