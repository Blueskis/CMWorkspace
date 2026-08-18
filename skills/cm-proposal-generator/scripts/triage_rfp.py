#!/usr/bin/env python3
"""Find the change-management sections inside a full RFP (Stage 1a).

    python triage_rfp.py rfp.txt -o proposals/<run>/rfp_triage.json
    python triage_rfp.py part1.txt part2.txt annexes/ --min-words 40

A CM bid team is usually handed the whole tender: two hundred pages of which perhaps
fifteen are theirs. The failure mode is not reading the obvious chapter — it is the
training obligation buried in the service-levels annex, or the stakeholder-engagement
clause inside governance, that nobody answers because nobody expected it there.

This splits the document on its own clause numbering, scores every section for CM
relevance, and reports **both lists** — what it judged CM-relevant and what it set aside.
The second list is the point. A section that appears in neither was never read, and that
is a different problem from one that was read and dismissed.

## What it is not

It is not a decision. Scoring is literal term matching with published weights, the same
deliberately-explainable approach as `retrieve.py`: it produces a shortlist and its
reasons, and Stage 1 reads the shortlisted sections properly before writing requirements.
A `not-cm` verdict on a section whose heading looks interesting is a prompt to open it,
not permission to skip it.

## Input

Plain text, as extracted from the source document — use the `pdf` skill for a PDF, the
`docx` skill for Word, then feed the text here. Page markers in the form `===== PAGE n
=====` are understood and carried through to each section's page reference; without them
sections simply have no page number.

Stdlib only.
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# Weighted CM vocabulary. Weight is about how *specific* a term is to change management,
# not how important it is: "change impact assessment" can only be our work, "training"
# alone might be a hardware-maintenance clause, "user" is barely a signal at all.
LEXICON = {
    4: [
        "change management", "change manager", "change impact", "change readiness",
        "change agent", "change champion", "change network", "change strategy",
        "change sustenance", "organisational change", "organizational change",
        "stakeholder engagement", "stakeholder analysis", "user adoption",
        "training needs analysis", "train-the-trainer", "train the trainer",
        "transition management", "knowledge transfer", "behavioural change",
        "behavioral change", "change intervention", "orientation programme",
        "orientation program", "change plan", "communications plan", "communication plan",
    ],
    3: [
        "super user", "superuser", "power user", "readiness assessment", "hypercare",
        "floorwalking", "floor walking", "adoption rate", "user acceptance",
        "training plan", "training materials", "training strategy", "curriculum",
        "e-learning", "elearning", "instructor-led", "post-implementation review",
        "sustainment", "reinforcement", "capability building", "upskilling",
        "change fatigue", "resistance", "sponsor", "sponsorship",
    ],
    2: [
        "training", "stakeholder", "communication", "engagement", "readiness",
        "workshop", "briefing", "onboarding", "coaching", "mentoring", "learning",
        "user guide", "job aid", "help desk", "helpdesk", "feedback", "survey",
        "awareness", "buy-in", "culture", "adoption",
    ],
    1: ["user", "staff", "employee", "end-user", "end user", "roll-out", "rollout"],
}

# Vocabulary that marks a section as somebody else's. Never cancels a strong CM signal —
# it only breaks ties and flags sections whose CM words are incidental.
OFF_TOPIC = [
    "warranty period", "liquidated damages", "indemnity", "source code escrow",
    "bandwidth", "firewall", "database schema", "encryption", "api", "uptime",
    "disaster recovery", "backup", "penetration test", "hardware", "server",
    "bill of quantities", "insurance", "bond", "arbitration", "jurisdiction",
]

# A deliverable is named the same way whichever modal a tender favours. Some use "shall"
# throughout, some "must", and some — like the transport ERP sample — say "should" 85
# times and "shall" not once. Detecting only "shall" found nothing in that document.
# Note the modal still decides PRIORITY (shall/must mandatory, should desirable); this
# list is only about spotting that a deliverable is being named at all.
DELIVERABLE_VERBS = ("provide", "develop", "submit", "prepare", "produce", "deliver",
                     "propose", "establish", "conduct", "define", "include", "devise",
                     "outline", "describe", "identify", "detail")
DELIVERABLE_CUES = [f"{modal} {verb}" for modal in ("shall", "must", "should")
                    for verb in DELIVERABLE_VERBS] + ["is required to provide"]

# Cross-references to parts of the tender we may not have been given.
# Kept to a single line: across a line break "Commercial Schedule / 5.1." reads as a
# reference to "Schedule 5.1", which does not exist.
CROSS_REF = re.compile(
    r"\b(?:part|chapter|annex|appendix|schedule|section|volume)[ \t]+"
    r"(?:[IVXLC]+|\d+(?:\.\d+)*)\b",
    re.I,
)
FILE_MARKER = re.compile(r"^=+\s*FILE\s+(.+?)\s*=+\s*$", re.M)

PAGE_MARKER = re.compile(r"^=+\s*PAGE\s+(\d+)\s*=+\s*$", re.I | re.M)

# Clause headings, in the shapes tenders actually use.
HEADING_PATTERNS = [
    # 3.1.2  Change Management Plan   /   3.  CHANGE MANAGEMENT SCOPE
    # Up to seven components: real tenders nest further than feels reasonable —
    # 2.3.2.2.2.4 is a genuine clause reference, and at {0,4} it matched nothing.
    re.compile(r"^\s{0,6}(\d{1,2}(?:\.\d{1,3}){0,6})\.?\s+(\S[^\n]{2,110})$"),
    # PART 2, CHAPTER 8   /   ANNEX I — PRICING
    re.compile(r"^\s{0,6}((?:PART|CHAPTER|ANNEX|APPENDIX|SCHEDULE|SECTION|VOLUME)\s+"
               r"(?:[IVXLC]+|\d+))\b[\s,:.–-]*([^\n]{0,110})$", re.I),
]
# A table of contents matches every heading pattern and is not content. Its giveaway is
# the dot leader — but wrapped TOC entries lose theirs, so the whole page goes too.
TOC_LINE = re.compile(r"\.{4,}\s*\d+\s*$")
TOC_PAGE = re.compile(r"table of contents|^[ \t]*contents[ \t]*$", re.I | re.M)

# A heading names a topic. A clause makes a demand of somebody. Both are numbered
# identically in a tender, and only the first should be reported as a heading —
# labelling half a sentence "heading" makes the triage output unreadable.
MODAL = re.compile(r"\b(shall|must|should|may|will)\b", re.I)


def read_inputs(paths):
    """Concatenate the input files, remembering where each one started."""
    chunks, sources = [], []
    for path in paths:
        files = sorted(p for p in path.rglob("*.txt")) if path.is_dir() else [path]
        for f in files:
            if not f.is_file():
                sys.exit(f"not a file: {f}")
            sources.append(str(f))
            chunks.append(f"\n===== FILE {f} =====\n" + f.read_text(encoding="utf-8",
                                                                    errors="replace"))
    return "\n".join(chunks), sources


def marker_index(text, pattern, cast=str):
    """Character offset -> the most recent marker value before it.

    Built over the *same* text the sections are cut from — building it over the original
    and then splitting a filtered copy silently reports every page number wrong.
    """
    marks = [(m.start(), cast(m.group(1))) for m in pattern.finditer(text)]

    def at(offset):
        value = None
        for start, found in marks:
            if start <= offset:
                value = found
            else:
                break
        return value
    return at


DANGLING = re.compile(r"\b(the|a|an|and|or|of|to|in|for|with|that|which|shall)$", re.I)


GLUED = re.compile(r"(?<=[a-z])(?=(?:The|This|These|Tenderers?|A|An)\b)")


def unglue(text):
    """Split a run-in heading from the sentence welded to it.

    Word stores a heading and the paragraph that follows it as one run often enough that
    a real tender arrives as "Change Management StrategyThe Tenderers should provide…".
    Split only where a lowercase letter runs straight into a capitalised sentence opener,
    and only when what comes before it could be a title on its own.
    """
    parts = GLUED.split(text, maxsplit=1)
    if len(parts) == 2 and 3 <= len(parts[0].strip()) <= 70:
        return parts[0].strip()
    return text


def looks_like_heading(text):
    """Distinguish a section title from the first line of a numbered clause."""
    if not text:
        return True
    trimmed = text.rstrip()
    words = trimmed.split()
    # A real heading does not trail off. "Where subcontractors are engaged for change
    # management activities, the" passes every other test and is plainly a fragment.
    if trimmed.endswith((",", ":", ";")) or DANGLING.search(trimmed):
        return False
    return (len(trimmed) <= 70 and len(words) <= 11 and not MODAL.search(trimmed)
            and not trimmed.endswith((".", ";")))


def running_headers(text, threshold=3):
    """Lines repeated across pages — the document's own header and footer furniture.

    Left in, a running header matching a heading pattern becomes a new section on every
    page, and the triage output is mostly the same title over and over.
    """
    counts = Counter()
    for line in text.splitlines():
        stripped = " ".join(line.split())
        if 6 < len(stripped) < 120:
            counts[stripped] += 1
    return {line for line, count in counts.items() if count >= threshold}


def strip_toc_pages(text):
    """Drop pages carrying a table of contents; its entries are not requirements."""
    pages = re.split(r"(^=+\s*PAGE\s+\d+\s*=+\s*$)", text, flags=re.I | re.M)
    if len(pages) == 1:
        return text
    out = [pages[0]]
    for marker, body in zip(pages[1::2], pages[2::2]):
        out.append(marker)
        # A newline, not an empty string: emptied outright, this page's marker would run
        # onto the next one's, and neither would match as a marker any more.
        out.append("\n" if TOC_PAGE.search(body) else body)
    return "".join(out)


def split_sections(text, min_words):
    """Split on clause headings. Returns [{ref, heading, body, offset}]."""
    furniture = running_headers(text)
    lines = text.splitlines(keepends=True)
    marks, offset = [], 0
    for line in lines:
        stripped = line.rstrip("\n")
        normalised = " ".join(stripped.split())
        if not TOC_LINE.search(stripped) and normalised not in furniture:
            for pattern in HEADING_PATTERNS:
                match = pattern.match(stripped)
                if match:
                    ref = match.group(1).rstrip(".")
                    tail = unglue((match.group(2) or "").strip(" .:–-"))
                    marks.append((offset, ref, tail if looks_like_heading(tail) else ""))
                    break
        offset += len(line)

    if not marks:
        return [{"ref": "(whole document)", "heading": "", "body": text, "offset": 0}]

    sections = []
    if marks[0][0] > 0:
        sections.append({"ref": "(preamble)", "heading": "", "offset": 0,
                         "body": text[: marks[0][0]]})
    for i, (start, ref, heading) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        sections.append({"ref": ref, "heading": heading, "offset": start,
                         "body": text[start:end]})

    # A heading with almost nothing under it is a parent of the clauses that follow
    # rather than a section in its own right. Fold it forward — but keep its title as the
    # child's breadcrumb, because "Change Management Plan" is what a bid team recognises
    # and "4.1.1" on its own is not.
    merged, pending = [], []
    for section in sections:
        if len(section["body"].split()) < min_words:
            if section["heading"]:
                pending.append(f"{section['ref']} {section['heading']}".strip())
            if merged:
                merged[-1]["body"] += section["body"]
            continue
        section["parent_headings"] = pending
        if pending and not section["heading"]:
            section["heading"] = pending[-1].split(" ", 1)[-1]
        pending = []
        merged.append(section)
    return merged


def score_section(section):
    body = " ".join(section["body"].split()).lower()
    heading = section["heading"].lower()
    words = max(len(body.split()), 1)

    hits, score, signal_chars = Counter(), 0, 0
    for weight, terms in LEXICON.items():
        for term in terms:
            count = body.count(term)
            if count:
                hits[term] = count
                score += weight * count
                signal_chars += len(term) * count
                # A term in the heading says the section is *about* it, rather than
                # mentioning it in passing.
                if term in heading:
                    score += weight * 3

    off_topic = sum(body.count(term) for term in OFF_TOPIC)
    deliverables = [cue for cue in DELIVERABLE_CUES if cue in body]
    strong = {t: c for t, c in hits.items() if t in LEXICON[4]}
    strong_total = sum(strong.values())

    # Share of the section's text that is CM vocabulary. Bounded and length-independent,
    # unlike a raw score: a long annex with two stray mentions ranks below a short clause
    # that is entirely about training, which is the ordering a bid team needs.
    coverage = signal_chars / max(len(body), 1)

    if strong and (strong_total >= 2 or heading_has_strong(heading) or coverage >= 0.02):
        verdict = "cm-core"
    elif strong or score >= 6 or coverage >= 0.015:
        verdict = "cm-adjacent"
    else:
        verdict = "not-cm"

    return {
        "verdict": verdict,
        "score": score,
        "cm_vocabulary_share": round(coverage, 4),
        "word_count": words,
        "strong_signals": dict(sorted(strong.items(), key=lambda kv: -kv[1])),
        "all_signals": dict(sorted(hits.items(), key=lambda kv: -kv[1])[:12]),
        "off_topic_signals": off_topic,
        "deliverable_cues": deliverables,
    }


def heading_has_strong(heading):
    return any(term in heading for term in LEXICON[4])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", type=Path,
                    help="extracted RFP text file(s), or a directory of .txt")
    ap.add_argument("-o", "--out", type=Path, default=Path("rfp_triage.json"))
    ap.add_argument("--min-words", type=int, default=25,
                    help="sections shorter than this fold into the previous one "
                         "(default: 25)")
    ap.add_argument("--excerpt", type=int, default=240, help="excerpt length per section")
    args = ap.parse_args()

    raw, sources = read_inputs(args.inputs)
    text = strip_toc_pages(raw)
    page_at = marker_index(text, PAGE_MARKER, int)
    file_at = marker_index(text, FILE_MARKER)
    sections = split_sections(text, args.min_words)

    results = []
    for section in sections:
        # Strip the harness's own markers before scoring — they are not the client's text.
        section["body"] = FILE_MARKER.sub("", PAGE_MARKER.sub("", section["body"]))
        body = " ".join(section["body"].split())
        if len(body.split()) < 5:
            continue
        results.append({
            "ref": section["ref"],
            "heading": section["heading"],
            "parent_headings": section.get("parent_headings", []),
            "page": page_at(section["offset"]),
            "source": file_at(section["offset"]) or (sources[0] if sources else None),
            **score_section(section),
            "excerpt": body[: args.excerpt],
        })

    # Deduplicate case-insensitively but keep the tender's own capitalisation — "Annex
    # III" is how the document names it and how a clarification question must too.
    # Skip anything that only appears in the document's own running header: a chapter
    # headed "PART 2 ... CHAPTER 8" would otherwise list itself among the parts to chase,
    # which is noise in a list whose whole job is to be acted on.
    furniture = [line.lower() for line in running_headers(text)]
    seen = {}
    for match in CROSS_REF.finditer(text):
        ref = " ".join(match.group(0).split())
        if any(ref.lower() in line for line in furniture):
            continue
        seen.setdefault(ref.lower(), ref)
    cross_refs = sorted(seen.values(), key=str.lower)

    by_verdict = Counter(r["verdict"] for r in results)
    triage = {
        "sources": sources,
        "section_count": len(results),
        "word_count": len(text.split()),
        "verdict_counts": dict(by_verdict),
        "cross_references": cross_refs,
        "note": "A shortlist and its reasons, not a decision. Read every cm-core and "
                "cm-adjacent section in full before writing requirements, and skim the "
                "not-cm list for anything whose heading suggests otherwise — a training "
                "obligation in a service-levels annex scores low and still belongs to us.",
        "sections": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(triage, indent=2), encoding="utf-8")

    print(f"{len(results)} section(s) across {len(text.split())} words -> {args.out}")
    print(f"  cm-core {by_verdict['cm-core']}   cm-adjacent {by_verdict['cm-adjacent']}"
          f"   not-cm {by_verdict['not-cm']}")
    print()
    for result in sorted(results, key=lambda r: -r["score"]):
        if result["verdict"] == "not-cm":
            continue
        page = f"p{result['page']}" if result["page"] else "—"
        signals = ", ".join(list(result["strong_signals"])[:4]) or "no strong signals"
        label = result["heading"] or f"“{result['excerpt'][:50]}…”"
        print(f"  [{result['verdict']:<11}] {result['ref']:<10} {page:<5} {label[:56]}")
        print(f"      score {result['score']:<4} "
              f"CM vocab {result['cm_vocabulary_share']:.1%}  {signals}")
        if result["deliverable_cues"]:
            print(f"      names deliverables: {', '.join(result['deliverable_cues'][:4])}")

    set_aside = [r for r in results if r["verdict"] == "not-cm"]
    if set_aside:
        print(f"\n  Set aside ({len(set_aside)}) — skim these, do not assume:")
        for result in set_aside:
            label = result["heading"] or f"“{result['excerpt'][:56]}…”"
            print(f"    {result['ref']:<10} {label[:66]}")

    if cross_refs:
        print(f"\n  Cross-references to other parts ({len(cross_refs)}) — confirm we "
              f"have each one:")
        print("    " + "; ".join(cross_refs[:14]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
