#!/usr/bin/env python3
"""Render a comms plan into a Markdown draft (Stage 3a, every channel).

    python render_markdown.py comms_plan.json -o comms/<run>/draft.md
    python render_markdown.py comms_plan.json --brand brand_profile.json -o draft.md

Shapes the document by channel, dispatching on schemas/channel_registry.json: an email as
subject/preheader headers over body copy; an article as headline, standfirst and sectioned
prose; a briefing deck slide-by-slide with speaker notes; a newsletter as skimmable
sections; a banner as copy plus a placement spec; a video as a scene table with an
estimated runtime.

This is the REVIEWABLE draft, not the deliverable. It is what a practitioner reads and what
qa_comms.py audits. Once QA passes, route_channel.py routes the same plan to the producer
that builds the real artifact — .docx, .pptx or a Canva design.

Two things this renderer will not do quietly:

  * A block flagged `gap: true` renders as a visible blockquoted [GAP]. It is never
    silently dropped and never filled with substitute text.
  * Every part's provenance renders beneath it by default (`--sources footer`) — knowledge
    bank IDs and `brief:` references alike. Use `--sources hidden` only once the
    practitioner has reviewed the provenance.

STATUS (v0.2): this produces a draft for a human to edit, not a sendable asset. It applies
no brand colours — Markdown has none — so when a brand profile is passed its palette,
typography and channel specs are emitted as an explicit spec block for whoever builds the
final artifact. It does not send, schedule, or publish anything, and deliberately has no
code path that could.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "schemas" / "channel_registry.json"


def load_registry(path=None):
    return json.loads(Path(path or REGISTRY_PATH).read_text(encoding="utf-8"))


def channel_label(channel, registry):
    entry = registry["channels"].get(channel) or {}
    return entry.get("label", channel)

# Parts an email renders as a labelled header line rather than a body section.
EMAIL_HEADER_PARTS = ("subject", "preheader")
# Same idea for an article: the furniture above the body copy.
ARTICLE_HEADER_PARTS = ("headline", "standfirst")


# --- block rendering -------------------------------------------------------


def render_block(block):
    """One plan block -> a Markdown fragment. Gaps always render visibly."""
    if block.get("gap"):
        note = block.get("gap_note") or "Not covered by the knowledge bank or the brief."
        return f"> **[GAP]** {note}"

    kind, content = block["kind"], block["content"]

    if kind in ("text", "paragraph"):
        paras = content if isinstance(content, list) else [content]
        return "\n\n".join(str(p) for p in paras)

    if kind == "heading":
        return f"**{content}**"

    if kind == "bullets":
        items = content if isinstance(content, list) else [content]
        return "\n".join(f"- {i}" for i in items)

    if kind == "table":
        headers = content.get("headers", [])
        rows = content.get("rows", [])
        if not headers:
            return ""
        out = ["| " + " | ".join(str(h) for h in headers) + " |",
               "|" + "|".join(["---"] * len(headers)) + "|"]
        out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
        return "\n".join(out)

    if kind == "metric":
        items = content if isinstance(content, list) else [content]
        return "\n".join(
            f"- **{m.get('value', '')}** — {m.get('label', '')}" for m in items
        )

    if kind == "phases":
        items = content if isinstance(content, list) else [content]
        out = []
        for p in items:
            when = p.get("when") or p.get("date") or ""
            name = p.get("name") or p.get("label") or ""
            detail = p.get("detail") or p.get("description") or ""
            line = f"- **{when}** — {name}" if when else f"- **{name}**"
            if detail:
                line += f": {detail}"
            out.append(line)
        return "\n".join(out)

    if kind == "members":
        items = content if isinstance(content, list) else [content]
        return "\n".join(
            f"- **{m.get('name', '')}**, {m.get('role', '')} — {m.get('bio', '')}"
            for m in items
        )

    if kind == "image":
        src = content.get("src") if isinstance(content, dict) else content
        alt = content.get("alt", "") if isinstance(content, dict) else ""
        return f"![{alt}]({src})"

    if kind == "notes":
        return ""

    return str(content)


def part_sources(part):
    ids = sorted({s for b in part.get("blocks", []) for s in b.get("sources", [])})
    gaps = sum(1 for b in part.get("blocks", []) if b.get("gap"))
    return ids, gaps


def sources_line(part, mode):
    if mode == "hidden":
        return ""
    ids, gaps = part_sources(part)
    bits = []
    if ids:
        bits.append("Sources: " + ", ".join(f"`{i}`" for i in ids))
    if gaps:
        bits.append(f"{gaps} open gap{'s' if gaps > 1 else ''}")
    if not bits:
        bits.append("No sources recorded")
    return "*" + " · ".join(bits) + "*"


def body_of(part):
    return "\n\n".join(f for f in (render_block(b) for b in part["blocks"]) if f)


def ordered_parts(plan):
    """Flatten sections into (section, part) pairs in plan order."""
    for section in sorted(plan.get("sections", []), key=lambda s: s.get("order", 0)):
        for part in section.get("slides", []):
            yield section, part


# --- word counting (drives the video runtime estimate) ---------------------


def all_words(part):
    """Every word a reader sees in this part, table scaffolding included."""
    total = 0
    for block in part.get("blocks", []):
        if block.get("gap"):
            continue

        def walk(value):
            nonlocal total
            if isinstance(value, str):
                total += len(value.split())
            elif isinstance(value, list):
                for v in value:
                    walk(v)
            elif isinstance(value, dict):
                for v in value.values():
                    walk(v)

        walk(block["content"])
    return total


def spoken_words(part):
    """Words a presenter would actually say — prose blocks only, not table scaffolding."""
    total = 0
    for block in part.get("blocks", []):
        if block.get("gap"):
            continue
        if block["kind"] not in ("text", "paragraph", "bullets", "heading"):
            continue
        content = block["content"]
        items = content if isinstance(content, list) else [content]
        for item in items:
            total += len(str(item).split())
    return total


# --- per-channel documents -------------------------------------------------


def render_email(plan, mode):
    out = []
    headers, body = [], []
    for _, part in ordered_parts(plan):
        (headers if part.get("part_kind") in EMAIL_HEADER_PARTS else body).append(part)

    for part in headers:
        label = part.get("part_kind", "").capitalize()
        out.append(f"**{label}:** {body_of(part)}")
        line = sources_line(part, mode)
        if line:
            out.append(line)
    if headers:
        out.append("---")

    words = 0
    for part in body:
        if part.get("title"):
            out.append(f"### {part['title']}")
        out.append(body_of(part))
        line = sources_line(part, mode)
        if line:
            out.append(line)
        words += all_words(part)

    out.append("---")
    out.append(f"*Body length: {words} words — excludes the subject and preheader, which is "
               f"the same scope qa_comms.py checks `max_words` against.*")
    return out


def render_article(plan, mode):
    """Headline and standfirst as furniture, then body copy under section headings."""
    out = []
    headers, body = [], []
    for _, part in ordered_parts(plan):
        (headers if part.get("part_kind") in ARTICLE_HEADER_PARTS else body).append(part)

    for part in headers:
        kind = part.get("part_kind")
        text = body_of(part)
        out.append(f"# {text}" if kind == "headline" else f"**{text}**")
        line = sources_line(part, mode)
        if line:
            out.append(line)
    if headers:
        out.append("---")

    words = 0
    for part in body:
        kind = part.get("part_kind")
        if kind == "pull-quote":
            # A pull quote is lifted from the body, not added to it — render it as a
            # block quote and keep it out of the word count so it is not double-counted.
            out.append(f"> {body_of(part)}")
            line = sources_line(part, mode)
            if line:
                out.append(line)
            continue
        if part.get("title"):
            out.append(f"## {part['title']}")
        out.append(body_of(part))
        line = sources_line(part, mode)
        if line:
            out.append(line)
        words += all_words(part)

    out.append("---")
    out.append(f"*Body length: {words} words — excludes the headline, standfirst and any "
               f"pull quote, which is the scope qa_comms.py checks `max_words` against.*")
    return out


def render_newsletter(plan, mode):
    """Sections a reader skims. Each carries its own heading and, where present, a CTA."""
    out = []
    for _, part in ordered_parts(plan):
        kind = part.get("part_kind")
        if kind == "headline":
            out.append(f"# {body_of(part)}")
        elif kind == "standfirst":
            out.append(f"**{body_of(part)}**")
        elif kind == "cta":
            out.append(f"**Call to action:** {body_of(part)}")
        elif kind == "placement-spec":
            out.append("### Placement")
            out.append(body_of(part))
        else:
            if part.get("title"):
                out.append(f"## {part['title']}")
            out.append(body_of(part))
        line = sources_line(part, mode)
        if line:
            out.append(line)
    return out


def render_banner(plan, mode):
    out = []
    for _, part in ordered_parts(plan):
        kind = part.get("part_kind", "content")
        label = {"headline": "Headline", "subhead": "Body line", "cta": "Call to action",
                 "placement-spec": "Placement"}.get(kind, part.get("title", "Content"))
        out.append(f"### {label}")
        out.append(body_of(part))
        line = sources_line(part, mode)
        if line:
            out.append(line)
    return out


def render_deck(plan, mode):
    out = []
    total = sum(1 for _ in ordered_parts(plan))
    for i, (section, part) in enumerate(ordered_parts(plan), 1):
        out.append(f"### Slide {i}/{total} — {part.get('title', '')}")
        meta = [f"section `{section['section_id']}`"]
        if part.get("layout"):
            meta.append(f"layout `{part['layout']}`")
        if section.get("message_ids"):
            meta.append("messages " + ", ".join(f"`{m}`" for m in section["message_ids"]))
        out.append("*" + " · ".join(meta) + "*")
        out.append(body_of(part))
        if part.get("speaker_notes"):
            out.append(f"> **Speaker notes.** {part['speaker_notes']}")
        else:
            out.append("> **Speaker notes.** _None recorded — a cascade deck without notes "
                       "gets improvised._")
        line = sources_line(part, mode)
        if line:
            out.append(line)
    return out


def render_video(plan, brand, mode):
    specs = (brand or {}).get("channel_specs", {}).get(plan["channel"], {})
    wpm = specs.get("words_per_minute", 150)
    limit = specs.get("max_duration_seconds")

    rows, total_words, total_declared = [], 0, 0.0
    parts = list(ordered_parts(plan))
    for i, (_, part) in enumerate(parts, 1):
        words = spoken_words(part)
        total_words += words
        declared = part.get("duration_seconds")
        if declared:
            total_declared += float(declared)
        est = round(words / wpm * 60, 1) if wpm else 0
        rows.append((i, part.get("title", ""), declared, est, words))

    table = ["| # | Scene | Planned | Est. from script | Words |",
             "|---|---|---|---|---|"]
    for i, title, declared, est, words in rows:
        d = f"{declared}s" if declared else "—"
        table.append(f"| {i} | {title or '(untitled)'} | {d} | {est}s | {words} |")
    # One block — the document joins on blank lines, which would split the table apart.
    out = ["### Scene outline", "\n".join(table)]

    est_total = round(total_words / wpm * 60, 1) if wpm else 0
    out.append(f"**Estimated runtime from script: {est_total}s** "
               f"({total_words} words at {wpm} wpm)."
               + (f" Planned total: {total_declared}s." if total_declared else ""))
    if limit:
        verdict = "within" if est_total <= limit else "**OVER**"
        out.append(f"Brand limit is {limit}s — {verdict}.")

    for i, (_, part) in enumerate(parts, 1):
        out.append(f"### Scene {i} — {part.get('title', '')}")
        out.append(body_of(part))
        line = sources_line(part, mode)
        if line:
            out.append(line)
    return out


# --- brand spec block ------------------------------------------------------


def brand_block(brand, channel):
    if not brand:
        return ["### Brand specification", "",
                "_No brand profile supplied._ Whoever builds the final artifact has nothing "
                "to apply — supply a `brand_profile.json` before this goes to design."]
    out = ["### Brand specification", "",
           "For whoever builds the final artifact. Not applied to this Markdown."]
    approval = brand.get("approval", {})
    out.append(f"- **Approved by:** {approval.get('approved_by', '—')} "
               f"({approval.get('role', '—')}), {approval.get('approved_date', '—')}")

    palette = brand.get("palette", {})
    if palette:
        swatches = ", ".join(
            f"{k} `{v.get('hex')}`" for k, v in palette.items() if isinstance(v, dict)
        )
        out.append(f"- **Palette:** {swatches}")

    typo = brand.get("typography", {})
    if typo:
        out.append(f"- **Typography:** headings {typo.get('heading', {}).get('family', '—')}, "
                   f"body {typo.get('body', {}).get('family', '—')}")

    specs = brand.get("channel_specs", {}).get(channel, {})
    if specs:
        out.append("- **Channel specs:** " +
                   ", ".join(f"{k} = {v}" for k, v in specs.items()))

    tone = brand.get("tone", {})
    if tone.get("banned_words"):
        out.append("- **Never use:** " + ", ".join(tone["banned_words"]))
    if tone.get("preferred_terms"):
        out.append("- **Preferred terms:** " +
                   ", ".join(f"{k} → {v}" for k, v in tone["preferred_terms"].items()))

    logo = brand.get("logo", {})
    if logo:
        out.append(f"- **Logo:** {logo.get('path', '—')}; clear space "
                   f"{logo.get('clear_space', '—')}; min width "
                   f"{logo.get('min_width_px', '—')}px")
    return out


# --- document assembly -----------------------------------------------------


def render(plan, brand, mode, registry):
    channel = plan["channel"]
    title = plan.get("engagement_title") or plan.get("run_id", "")
    out = [f"# {title}",
           f"**{channel_label(channel, registry)} — DRAFT FOR PRACTITIONER REVIEW**"]

    meta = [
        f"- **Client:** {plan.get('client', '—')}",
        f"- **Run:** `{plan.get('run_id', '—')}`",
        f"- **Audiences:** {', '.join(plan.get('target_audience_ids', [])) or '—'}",
        f"- **Brief:** `{plan.get('brief_ref', '—')}`",
    ]
    if plan.get("sender"):
        meta.append(f"- **Sender:** {plan['sender']}")
    if plan.get("send_window"):
        meta.append(f"- **Send window:** {plan['send_window']}")
    # One block, not one entry per line — the document joins on blank lines, which would
    # otherwise double-space every bullet.
    out += ["\n".join(meta), "---"]

    renderers = {
        "email": lambda: render_email(plan, mode),
        "article": lambda: render_article(plan, mode),
        "briefing_deck": lambda: render_deck(plan, mode),
        "newsletter": lambda: render_newsletter(plan, mode),
        "banner": lambda: render_banner(plan, mode),
        "short_form_video": lambda: render_video(plan, brand, mode),
        "explainer_video": lambda: render_video(plan, brand, mode),
    }
    if channel not in renderers:
        sys.exit(f"no renderer for channel '{channel}' — "
                 f"known: {', '.join(sorted(renderers))}")
    out += renderers[channel]()

    block = brand_block(brand, channel)
    out += ["---", block[0], "\n".join(block[2:])]
    out += ["---",
            f"*Generated {date.today().isoformat()}. This is a first draft for the "
            f"practitioner to review and edit — not an approved send.*"]
    return "\n\n".join(line for line in out if line)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("draft.md"))
    ap.add_argument("--brand", type=Path, help="brand_profile.json — emitted as a spec block")
    ap.add_argument("--sources", choices=["footer", "hidden"], default="footer",
                    help="Show provenance under each part (default: footer). 'hidden' is for "
                         "a reviewed copy only.")
    args = ap.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    brand = json.loads(args.brand.read_text(encoding="utf-8")) if args.brand else None

    registry = load_registry()
    doc = render(plan, brand, args.sources, registry)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(doc + "\n", encoding="utf-8")

    parts = sum(1 for _ in ordered_parts(plan))
    gaps = sum(1 for _, p in ordered_parts(plan)
               for b in p["blocks"] if b.get("gap"))
    entry = registry["channels"].get(plan["channel"], {})
    print(f"Rendered {parts} part(s) -> {args.out}  [{plan['channel']}]")
    if entry.get("producer"):
        print(f"  produces via {entry['producer']} ({entry.get('status', '?')}) — "
              f"run route_channel.py for the production route")
    if gaps:
        print(f"  {gaps} [GAP] block(s) rendered visibly — see qa_report.md for the action list")
    if not brand:
        print("  no brand profile supplied — the draft carries no brand spec for design")
    print(f"  Draft for practitioner review — generated {date.today().isoformat()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
