#!/usr/bin/env python3
"""Audit a comms plan against its change brief and brand profile (Stage 4).

    python qa_comms.py change_brief.json comms_plan.json --brand brand_profile.json \\
        -o comms/<run>/qa_report.md

Six checks. The first five exit non-zero on violation; the sixth reports.

  1. Message coverage    every must-land message in scope for this run's audiences is
                         carried by at least one part
  2. Audience coverage   every targeted audience's required action appears in an action part
  3. Provenance          every block has sources or an explicit [GAP], and every
                         `brief:` reference resolves to a real field of the brief
  4. Brand approval      the profile was approved by a named human
  5. Channel specs       stated character, slide and runtime limits are respected; banned
                         words and prohibited terms are absent; market-sensitive messages
                         are not on an open channel; indicative dates are hedged
  5b. Design provenance  a generated (tool-invented) design is flagged as needing client
                         sign-off, even when the copy itself passes
  6. The six questions   what / why / who / when / what-do-I-do / where-do-I-get-help

Per-channel limits come from schemas/channel_registry.json, so a default is stated in one
place and shared with route_channel.py and render_markdown.py. A limit the brand profile
states is a hard failure; a registry default only warns.

Coverage is computed against `plan.target_audience_ids`, NOT the whole brief. A single-
audience email must not fail for omitting messages aimed at a different segment — those are
reported as out of scope for this run instead.

STATUS (v0.2): this checks what is computable. Whether the draft is *good* — whether the
tone lands, whether the rationale persuades, whether the deck looks like the client's brand
— is not computable, and the human checklist at the end of the report says so rather than
implying the machine has covered it.
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ACTION_PARTS = {"your-action", "cta"}
# Channels whose part vocabulary has no "your-action" kind (a video uses scenes)
# still carry the action in the section the library names for it.
ACTION_SECTIONS = {"your-action", "cta"}
HEX_IN_TEXT_RE = re.compile(r"#[0-9a-fA-F]{6}\b")
HEDGES = ("expect", "around", "approximately", "indicative", "provisional", "planned",
          "currently", "subject to", "aim", "targeting", "estimated", "tbc", "early ",
          "mid ", "late ")

# Channel defaults live in the registry, so a limit is stated in exactly one place.
REGISTRY_PATH = Path(__file__).resolve().parent.parent / "schemas" / "channel_registry.json"


def load_registry(path=None):
    return json.loads(Path(path or REGISTRY_PATH).read_text(encoding="utf-8"))


def registry_specs(channel, registry=None):
    registry = registry or load_registry()
    return dict((registry["channels"].get(channel) or {}).get("default_specs", {}))


def requires_signature(channel, registry=None):
    registry = registry or load_registry()
    return (registry["channels"].get(channel) or {}).get("requires_signature", True)


def coverage_mode(channel, registry=None):
    """'full' = must carry every in-scope must-land message. 'signpost' = a banner or a
    30-second clip: carries one message and points at where the detail lives. Holding a
    signpost to full coverage forces content onto it the channel library says must not
    be there."""
    registry = registry or load_registry()
    return (registry["channels"].get(channel) or {}).get("coverage_mode", "full")


# The six questions, and the part kinds that answer each.
SIX_QUESTIONS = {
    "what's changing": {"whats-changing", "headline", "subject", "standfirst"},
    "why": {"opening", "whats-changing", "content", "standfirst"},
    "who's affected": {"who-is-affected"},
    "when": {"timeline"},
    "what do I do": {"your-action", "cta"},
    "where do I get help": {"help"},
}


# --- traversal -------------------------------------------------------------


def parts_of(plan):
    for section in sorted(plan.get("sections", []), key=lambda s: s.get("order", 0)):
        for part in section.get("slides", []):
            yield section, part


def block_text(block):
    """All human-readable text in a block, flattened for scanning."""
    if block.get("gap"):
        return ""
    content = block.get("content")
    out = []

    def walk(value):
        if isinstance(value, str):
            out.append(value)
        elif isinstance(value, list):
            for v in value:
                walk(v)
        elif isinstance(value, dict):
            for v in value.values():
                walk(v)

    walk(content)
    return " ".join(out)


def part_text(part):
    return " ".join(block_text(b) for b in part.get("blocks", []))


def plan_text(plan):
    return " ".join(part_text(p) for _, p in parts_of(plan))


def word_count(plan, exclude_kinds=()):
    """Words in the draft. Header parts are excluded from an email's body count, since
    `max_words` governs the body a reader scrolls, not the subject line."""
    text = " ".join(part_text(p) for _, p in parts_of(plan)
                    if p.get("part_kind") not in exclude_kinds)
    return len(text.split())


def resolve_brief_ref(brief, ref):
    """Resolve 'brief:audiences.A2.required_action' against the brief. True if it exists.

    Audience, message and milestone arrays are addressed by their ID rather than by index,
    since an index would silently re-point the moment the brief is reordered.
    """
    path = ref[len("brief:"):]
    if not path:
        return False
    node = brief
    for segment in path.split("."):
        if isinstance(node, dict):
            if segment not in node:
                return False
            node = node[segment]
        elif isinstance(node, list):
            match = next((i for i in node
                          if isinstance(i, dict) and i.get("id") == segment), None)
            if match is None:
                if segment.isdigit() and int(segment) < len(node):
                    node = node[int(segment)]
                    continue
                return False
            node = match
        else:
            return False
    return True


# --- the audit -------------------------------------------------------------


def audit(brief, plan, brand):
    r = {"fail": [], "warn": [], "info": []}

    targets = set(plan.get("target_audience_ids", []))
    channel = plan.get("channel")
    audiences = {a["id"]: a for a in brief.get("audiences", [])}
    messages = {m["id"]: m for m in brief.get("key_messages", [])}
    milestones = {t["id"]: t for t in brief.get("milestones", [])}

    planned_messages = {m for s, _ in parts_of(plan) for m in s.get("message_ids", [])}
    # A section's IDs cover every part in it, so collect at section level too.
    planned_messages |= {m for s in plan.get("sections", []) for m in s.get("message_ids", [])}
    planned_audiences = {a for s in plan.get("sections", []) for a in s.get("audience_ids", [])}

    text = plan_text(plan)
    lower = text.lower()

    # --- 1. message coverage
    in_scope, out_of_scope = [], []
    for mid, msg in messages.items():
        (in_scope if targets & set(msg.get("audience_ids", [])) else out_of_scope).append(mid)

    r["coverage"] = {"in_scope": sorted(in_scope), "out_of_scope": sorted(out_of_scope),
                     "planned": sorted(planned_messages)}

    mode = coverage_mode(channel)
    r["coverage"]["mode"] = mode
    must_in_scope = [m for m in in_scope if messages[m].get("priority") == "must-land"]

    for mid in sorted(in_scope):
        if mid in planned_messages:
            continue
        is_must = messages[mid].get("priority") == "must-land"
        if is_must and mode == "full":
            r["fail"].append(f"must-land message {mid} is not carried by any part: "
                             f"\"{messages[mid]['text'][:70]}\"")
        elif is_must:
            r["info"].append(f"must-land message {mid} is not on this signpost — it must be "
                             f"carried by the channel this one points at")
        else:
            r["warn"].append(f"supporting message {mid} is not carried by any part")

    if mode == "signpost":
        # A signpost carrying nothing is just decoration.
        if must_in_scope and not (set(must_in_scope) & planned_messages):
            r["fail"].append("this signpost carries none of the must-land messages in scope "
                             "— it has nothing to say")
        kinds_present = {p.get("part_kind") for _, p in parts_of(plan)}
        if not (kinds_present & {"cta", "placement-spec"}):
            r["fail"].append("a signpost must point somewhere — no cta or placement-spec "
                             "part gives the reader anywhere to go for the full detail")

    for mid in sorted(planned_messages - set(messages)):
        r["fail"].append(f"plan references unknown message {mid} — mapping error")

    if out_of_scope:
        r["info"].append(f"{len(out_of_scope)} message(s) aimed at other audiences and out of "
                         f"scope for this run: {', '.join(sorted(out_of_scope))}")

    # --- 2. audience coverage
    for aid in sorted(targets):
        aud = audiences.get(aid)
        if aud is None:
            r["fail"].append(f"plan targets unknown audience {aid}")
            continue
        if aid not in planned_audiences:
            r["fail"].append(f"audience {aid} ({aud['label']}) is targeted but no section "
                             f"addresses it")
            continue
        action = aud.get("required_action", {})
        if action.get("optional"):
            r["info"].append(f"{aid} has no required action (optional: true)")
            continue
        action_text = " ".join(
            part_text(p) for s, p in parts_of(plan)
            if p.get("part_kind") in ACTION_PARTS
            or s.get("section_id") in ACTION_SECTIONS
        )
        if not action_text.strip():
            r["fail"].append(f"audience {aid} has a required action but the draft has no "
                             f"action part or '{'/'.join(sorted(ACTION_SECTIONS))}' section")
        elif not _mentions_action(action_text, action.get("action", "")):
            r["warn"].append(f"audience {aid}'s required action may not be stated in the "
                             f"action part — check: \"{action.get('action', '')[:60]}\"")
        if (mode == "full" and aud.get("whats_in_it_for_me")
                and not _shares_vocabulary(lower, aud["whats_in_it_for_me"])):
            r["warn"].append(f"audience {aid}'s WIIFM does not appear to be reflected "
                             f"anywhere in the draft")

    # --- 3. provenance
    total_blocks, gaps, unattributed, dangling = 0, [], [], []
    for _, part in parts_of(plan):
        for i, block in enumerate(part.get("blocks", [])):
            total_blocks += 1
            if block.get("gap"):
                if not block.get("gap_note"):
                    r["fail"].append(f"{part['slide_id']} block {i}: gap with no gap_note")
                gaps.append((part["slide_id"], block.get("gap_note", "")))
                continue
            sources = block.get("sources") or []
            if not sources:
                unattributed.append(f"{part['slide_id']} block {i}")
                continue
            for src in sources:
                if src.startswith("brief:") and not resolve_brief_ref(brief, src):
                    dangling.append(f"{part['slide_id']} block {i}: {src}")

    for u in unattributed:
        r["fail"].append(f"{u} has neither sources nor an explicit [GAP]")
    for d in dangling:
        r["fail"].append(f"{d} does not resolve to a field of the brief")

    r["provenance"] = {"blocks": total_blocks, "gaps": gaps,
                       "unattributed": len(unattributed), "dangling": len(dangling)}

    # --- 4. brand approval
    if brand is None:
        r["fail"].append("no brand profile supplied — stop and ask the client for an approved "
                         "template or brand guidelines; do not build a lookalike")
        brand = {}
    else:
        approval = brand.get("approval") or {}
        if not approval.get("approved_by") or not approval.get("approved_date"):
            r["fail"].append("brand profile has no recorded approval — a palette nobody "
                             "approved is a lookalike")
        for field in ("tone", "palette", "typography"):
            if not brand.get(field):
                r["warn"].append(f"brand profile has no {field} block — partial profile, "
                                 f"likely extracted rather than authored")

    # --- 5. channel specs
    specs = registry_specs(channel)
    stated = (brand.get("channel_specs") or {}).get(channel, {})
    specs.update(stated)

    def limit_check(label, value, key, unit="characters"):
        cap = specs.get(key)
        if cap is None:
            return
        if value > cap:
            msg = f"{label} is {value} {unit}, over the limit of {cap}"
            (r["fail"] if key in stated else r["warn"]).append(
                msg + ("" if key in stated else " (channel-library default)"))

    for _, part in parts_of(plan):
        kind = part.get("part_kind")
        body = part_text(part).strip()
        if kind == "subject":
            limit_check("subject line", len(body), "subject_max_chars")
        elif kind == "preheader":
            limit_check("preheader", len(body), "preheader_max_chars")
        elif kind == "headline":
            limit_check("headline", len(body), "headline_max_chars")
        elif kind == "subhead":
            limit_check("banner body line", len(body), "body_max_chars")
        elif kind == "standfirst":
            limit_check("standfirst", len(body), "standfirst_max_chars")
        elif kind == "section-heading":
            limit_check("newsletter section", len(body), "section_max_chars")
        elif kind == "cta":
            limit_check("CTA label", len(body), "cta_max_chars")
        if channel == "briefing_deck":
            for block in part.get("blocks", []):
                if block.get("kind") == "bullets" and isinstance(block.get("content"), list):
                    limit_check(f"{part['slide_id']} bullet count",
                                len(block["content"]), "bullets_per_slide_max", "bullets")

    if channel == "email":
        limit_check("email body", word_count(plan, exclude_kinds=("subject", "preheader")),
                    "max_words", "words")
    if channel == "article":
        # Same scope render_markdown.py reports: a pull quote is lifted FROM the
        # body, so counting it would double-count those words.
        limit_check("article body",
                    word_count(plan, exclude_kinds=("headline", "standfirst",
                                                    "pull-quote")),
                    "max_words", "words")
    if channel == "briefing_deck":
        limit_check("deck", sum(1 for _ in parts_of(plan)), "max_slides", "slides")
    if channel in ("short_form_video", "explainer_video"):
        wpm = specs.get("words_per_minute", 150)
        runtime = round(word_count(plan) / wpm * 60, 1)
        r["info"].append(f"estimated runtime {runtime}s at {wpm} wpm")
        limit_check("estimated runtime", runtime, "max_duration_seconds", "seconds")

    # banned words and prohibited terms
    banned = list((brand.get("tone") or {}).get("banned_words", []))
    banned += list((brief.get("constraints") or {}).get("prohibited_terms", []))
    for word in banned:
        if re.search(rf"\b{re.escape(word.lower())}\b", lower):
            r["fail"].append(f"draft contains the prohibited term \"{word}\"")

    for avoid, use in ((brand.get("tone") or {}).get("preferred_terms") or {}).items():
        if re.search(rf"\b{re.escape(avoid.lower())}\b", lower):
            r["warn"].append(f"draft uses \"{avoid}\" — the client's preferred term is "
                             f"\"{use}\"")

    # sensitivity gate
    if channel in ("banner", "newsletter"):
        for mid in sorted(planned_messages & set(messages)):
            if messages[mid].get("sensitivity") == "market-sensitive":
                r["fail"].append(f"market-sensitive message {mid} is planned onto an open "
                                 f"channel ({channel}) with no audience control")

    # indicative dates must be hedged
    for tid, milestone in milestones.items():
        if milestone.get("date_confidence") != "indicative":
            continue
        if milestone.get("date", "") in text or milestone.get("label", "").lower() in lower:
            if not any(h in lower for h in HEDGES):
                r["fail"].append(
                    f"milestone {tid} is indicative but its date appears in the draft with no "
                    f"hedging language — publishing an indicative date as confirmed burns "
                    f"credibility")

    # stray hex colours (brand fidelity, the computable half)
    palette = {v.get("hex", "").lower()
               for v in (brand.get("palette") or {}).values() if isinstance(v, dict)}
    for found in set(HEX_IN_TEXT_RE.findall(text)):
        if found.lower() not in palette:
            r["warn"].append(f"draft text contains the colour {found}, which is not in the "
                             f"brand palette")

    # sender and help route
    sender = (brief.get("governance") or {}).get("sender") or {}
    if sender.get("name") and sender["name"].lower() not in lower:
        if mode == "full" and requires_signature(channel):
            r["fail"].append(f"the sender ({sender['name']}) is never named in the draft — a "
                             f"comm with no signature reads as unattributed")
        else:
            r["info"].append(f"the sender ({sender['name']}) is not named in the copy — "
                             f"expected on this channel, where the messenger is carried by "
                             f"the presenter or the placement rather than a signature")
    help_route = (brief.get("governance") or {}).get("help_route") or {}
    if help_route.get("detail") and help_route["detail"].lower() not in lower:
        if mode == "full":
            r["fail"].append(f"the help route ({help_route['detail']}) does not appear in the "
                             f"draft — every required action needs a route for when it fails")
        else:
            r["warn"].append(f"the help route ({help_route['detail']}) is not on this signpost "
                             f"— acceptable only if the destination it points at carries it")

    approver = (brief.get("governance") or {}).get("approver") or {}
    if not approver.get("approved"):
        r["warn"].append(f"not yet approved by {approver.get('name', 'the named approver')} — "
                         f"normal at draft stage, but it cannot be sent until it is")

    # --- 5b. design provenance
    provenance = plan.get("design_provenance", "not-applicable")
    if provenance == "generated-unapproved":
        r["warn"].append(
            "design_provenance is 'generated-unapproved' — a tool invented this layout. "
            "The copy has been checked; the DESIGN has not been approved by the client and "
            "must be signed off before publish."
        )
    r["design_provenance"] = provenance

    # --- 6. the six questions
    # Score on part kinds AND section ids: a video answers these in scenes, so the
    # section is what identifies which question a passage is doing.
    present = {p.get("part_kind") for _, p in parts_of(plan)}
    present |= {s.get("section_id") for s, _ in parts_of(plan)}
    missing = [q for q, kinds in SIX_QUESTIONS.items() if not (kinds & present)]
    r["six_questions"] = {"answered": [q for q in SIX_QUESTIONS if q not in missing],
                          "missing": missing}
    for q in missing:
        r["warn"].append(f"the draft may not answer \"{q}\"")

    return r


def _mentions_action(action_text, action):
    """Loose containment: do the action's distinctive words appear in the action part?"""
    return _shares_vocabulary(action_text.lower(), action)


def _shares_vocabulary(haystack, phrase, threshold=0.4):
    words = [w for w in re.findall(r"[a-z]{4,}", (phrase or "").lower())]
    if not words:
        return True
    hits = sum(1 for w in words if w in haystack)
    return hits / len(words) >= threshold


# --- report ----------------------------------------------------------------


def render(brief, plan, result):
    channel = plan.get("channel", "—")
    lines = [
        f"# Comms QA — {plan.get('run_id', '')}",
        "",
        f"- **Change:** {brief.get('change', {}).get('title', '—')}",
        f"- **Channel:** {channel}",
        f"- **Audiences:** {', '.join(plan.get('target_audience_ids', [])) or '—'}",
        f"- **Generated:** {date.today().isoformat()}",
        "",
    ]

    verdict = "FAIL" if result["fail"] else ("PASS with warnings" if result["warn"] else "PASS")
    lines += [f"## Verdict: {verdict}", ""]

    if result["fail"]:
        lines += ["### Must fix before this can be sent", ""]
        lines += [f"{i}. {m}" for i, m in enumerate(result["fail"], 1)] + [""]

    if result["warn"]:
        lines += ["### Worth checking", ""]
        lines += [f"- {m}" for m in result["warn"]] + [""]

    cov = result["coverage"]
    lines += ["### Message coverage", "",
              f"- Mode: **{cov.get('mode', 'full')}**"
              + ("  — a signpost carries one message and points at the detail"
                 if cov.get("mode") == "signpost" else ""),
              f"- In scope for this run: {len(cov['in_scope'])} "
              f"({', '.join(cov['in_scope']) or '—'})",
              f"- Carried by the draft: {', '.join(cov['planned']) or '—'}",
              f"- Out of scope (other audiences): {', '.join(cov['out_of_scope']) or '—'}",
              ""]

    prov = result["provenance"]
    lines += ["### Provenance", "",
              f"- Blocks: {prov['blocks']}",
              f"- Unattributed: {prov['unattributed']}",
              f"- Dangling brief references: {prov['dangling']}",
              f"- Open gaps: {len(prov['gaps'])}",
              ""]
    if prov["gaps"]:
        lines += ["#### Open gaps — the practitioner's action list", ""]
        lines += [f"- **{sid}** — {note}" for sid, note in prov["gaps"]] + [""]

    prov_state = result.get("design_provenance", "not-applicable")
    if prov_state != "not-applicable":
        lines += ["### Design provenance", "",
                  f"- `{prov_state}`" + ("  — **needs client sign-off before publish**"
                                         if prov_state == "generated-unapproved" else ""),
                  ""]

    six = result["six_questions"]
    lines += ["### The six questions", ""]
    for q in SIX_QUESTIONS:
        mark = "x" if q in six["answered"] else " "
        lines.append(f"- [{mark}] {q}")
    lines.append("")

    if result["info"]:
        lines += ["### Notes", ""] + [f"- {m}" for m in result["info"]] + [""]

    lines += [
        "### What this report cannot tell you", "",
        "These need a human, and no check above substitutes for them:", "",
        "- Whether the tone actually lands with this audience",
        "- Whether the rationale would persuade someone who is against the change",
        "- Whether the deck looks like the client's brand — a recoloured generic template",
        "  is a proof of concept, not the client's approved deck",
        "- Whether the logo is placed correctly (apply_brand.py places none)",
        "- Whether the sender is the right messenger for this message",
        "",
        "---",
        "",
        "*This is a first draft for practitioner review, not an approved send.*",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("brief", type=Path)
    ap.add_argument("plan", type=Path)
    ap.add_argument("--brand", type=Path, help="brand_profile.json")
    ap.add_argument("-o", "--out", type=Path, default=Path("qa_report.md"))
    args = ap.parse_args()

    brief = json.loads(args.brief.read_text(encoding="utf-8"))
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    brand = json.loads(args.brand.read_text(encoding="utf-8")) if args.brand else None

    result = audit(brief, plan, brand)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(brief, plan, result) + "\n", encoding="utf-8")

    prov = result["provenance"]
    print(f"QA {plan.get('run_id', '')} [{plan.get('channel')}] -> {args.out}")
    print(f"  {len(result['fail'])} failure(s), {len(result['warn'])} warning(s), "
          f"{len(prov['gaps'])} open gap(s) across {prov['blocks']} block(s)")

    if result["fail"]:
        for m in result["fail"]:
            print(f"  FAIL {m}", file=sys.stderr)
        return 1
    print("  Draft for practitioner review — not an approved send.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
