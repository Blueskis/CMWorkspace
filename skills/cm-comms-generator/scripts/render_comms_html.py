#!/usr/bin/env python3
"""Render one comms plan into a self-contained, brand-applied HTML artefact —
banner, newsletter-roundup or edm (Stage 3b's `local:render_comms_html` producer).

    python render_comms_html.py comms_plan.json --brief change_brief.json \\
        --brand brand_profile.json -o comms/<run>/comms_banner.html

Exists because neither Canva route in this skill guarantees a finished, editable, client-
owned artefact: `generate-design` invents the layout (`design_provenance:
generated-unapproved`, needing sign-off before publish) and — for banner specifically —
does not reliably hold the QA'd words verbatim at all, since Canva's poster generator
rewords whatever copy an image-shaped design is given. This script is the alternative for
banner, newsletter and edm: `apply_brand.py`'s palette/typography/contrast machinery is
reused unmodified (`--format html`), `profile_template.py` is reused unmodified for the
layout/placeholder profile (same as the briefing_deck lane reuses it for a client .potx),
and every word is substituted from the plan's blocks exactly as written — never
regenerated, never reworded.

THE GATE — the same one `route_channel.py` enforces before printing a route: this script
imports `qa_comms` and calls `qa_comms.audit()` itself, refusing to render while a hard
failure stands. A brand-applied HTML file is a finished-looking artefact; it must not be
reachable from a plan QA has not passed.

Two things this script will not do quietly:

  * Invent content for a missing or `gap: true` block. It renders as a visible [GAP]
    marker (banner/newsletter) or an inline-styled equivalent (edm).
  * Apply a brand profile that fails its own `accessibility.min_contrast_ratio` — that
    check lives in `apply_brand.py` and this script calls the same `build_theme()`
    function, so a failing palette never reaches this renderer either.

STATUS: banner and newsletter render as ordinary self-contained web pages, brand applied
via CSS custom properties (see comms-assets/templates/comms-html/base.css). edm renders as
table-based HTML with every style inlined literally, because mail clients do not reliably
honour <style> blocks, classes, var(), or flex/grid. edm's markup has been checked only by
static inspection (no <style> reliance, no flex/grid, literal colours, every <table> role=
"presentation") — it has NOT been opened in a real mail client (Outlook, Gmail, Apple
Mail), and that is a real gap, not a formality.
"""

import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
# profile_template.py's real implementation lives in lib/ (cm-proposal-generator/scripts/
# profile_template.py is a thin CLI shim over it, exposing only main()) — same shared
# module the briefing_deck lane's profiling step ultimately runs.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from profile_template import profile_html_template  # noqa: E402
import apply_brand  # noqa: E402  (same-directory sibling module)
import qa_comms  # noqa: E402  (same-directory sibling module)
from render_markdown import ordered_parts  # noqa: E402  (reused, not re-derived)

COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
TEMPLATE_BLOCK_RE = re.compile(
    r'<template\s+data-layout="([^"]+)"\s*>(.*?)</template>', re.DOTALL
)
OPTIONAL_RE = re.compile(r"\{\{#([a-z_]+)\}\}(.*?)\{\{/\1\}\}", re.DOTALL)
TOKEN_RE = re.compile(r"\{\{([a-z_]+)\}\}")
URL_RE = re.compile(r"https?://\S+")

CHANNEL_LAYOUT = {"banner": "banner", "newsletter": "newsletter-roundup", "edm": "edm"}
DEFAULT_TEMPLATE_DIR = Path(__file__).resolve().parents[2].parent / "comms-assets" / "templates" / "comms-html"


class RenderError(Exception):
    """A refusal this script makes on purpose — printed plainly, no traceback."""


# --- content helpers ---------------------------------------------------------


def esc(value):
    return html.escape(str(value), quote=False)


def esc_attr(value):
    return html.escape(str(value), quote=True)


def flatten_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return " ".join(flatten_text(v) for v in value)
    if isinstance(value, dict):
        return " ".join(flatten_text(v) for v in value.values())
    return str(value)


def render_gap(block, inline=None):
    note = esc(block.get("gap_note") or "Not covered by the knowledge bank or the brief.")
    if inline:
        return (
            f'<div style="background:#fef3c7;border-left:4px solid #b45309;'
            f'padding:8px 12px;color:#78350f;font-size:14px;">'
            f'<strong style="color:#b45309;">[GAP]</strong> {note}</div>'
        )
    return f'<div class="gap"><span class="gap-tag">[GAP]</span>{note}</div>'


def render_block_html(block, inline_gap=None):
    """One plan block -> an HTML fragment. Gaps always render visibly. Same block `kind`
    vocabulary as render_markdown.py's render_block(), emitting HTML instead of Markdown."""
    if block.get("gap"):
        return render_gap(block, inline=inline_gap)

    kind, content = block["kind"], block["content"]

    if kind in ("text", "paragraph"):
        paras = content if isinstance(content, list) else [content]
        return "".join(f"<p>{esc(p)}</p>" for p in paras)

    if kind == "heading":
        return f"<h3>{esc(content)}</h3>"

    if kind == "bullets":
        items = content if isinstance(content, list) else [content]
        return "<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>"

    if kind == "table":
        headers = content.get("headers", [])
        rows = content.get("rows", [])
        head = "".join(f"<th>{esc(h)}</th>" for h in headers)
        body = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>" for row in rows)
        return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"

    if kind == "metric":
        items = content if isinstance(content, list) else [content]
        return "".join(
            f'<div class="metric"><b>{esc(m.get("value", ""))}</b> — {esc(m.get("label", ""))}</div>'
            for m in items
        )

    if kind == "phases":
        items = content if isinstance(content, list) else [content]
        out = []
        for p in items:
            when = p.get("when") or p.get("date") or ""
            name = p.get("name") or p.get("label") or ""
            detail = p.get("detail") or p.get("description") or ""
            line = f"<b>{esc(when)}</b> — {esc(name)}" if when else f"<b>{esc(name)}</b>"
            if detail:
                line += f": {esc(detail)}"
            out.append(f"<p>{line}</p>")
        return "".join(out)

    if kind == "members":
        items = content if isinstance(content, list) else [content]
        return "".join(
            f'<p><b>{esc(m.get("name", ""))}</b>, {esc(m.get("role", ""))} — {esc(m.get("bio", ""))}</p>'
            for m in items
        )

    if kind == "image":
        src = content.get("src") if isinstance(content, dict) else content
        alt = content.get("alt", "") if isinstance(content, dict) else ""
        return f'<img src="{esc_attr(src)}" alt="{esc_attr(alt)}">'

    if kind == "notes":
        return ""

    return f"<p>{esc(content)}</p>"


def part_html(part, inline_gap=None):
    return "".join(render_block_html(b, inline_gap) for b in part.get("blocks", []))


def part_plain_text(part):
    """Flattened plain text of a part, gaps excluded — used only for the cta URL sniff."""
    out = []
    for b in part.get("blocks", []):
        if b.get("gap"):
            continue
        out.append(flatten_text(b.get("content")))
    return " ".join(out)


# --- per-layout fill assembly -------------------------------------------------


def fill_banner(plan):
    """Banner anatomy per channel-library.md: headline -> subhead -> cta on the artefact
    face; placement-spec and anything else (e.g. help) are production notes, not printed
    on the banner — matching how canva_brief.py's own 'shape' prompt describes the design
    as headline+subhead+cta only."""
    headline = subhead = pointer = None
    notes = []
    for _, part in ordered_parts(plan):
        kind = part.get("part_kind")
        body = part_html(part)
        if kind == "headline" and headline is None:
            headline = body
        elif kind == "subhead" and subhead is None:
            subhead = body
        elif kind == "cta" and pointer is None:
            pointer = body
        else:
            label = part.get("title") or kind or "Note"
            notes.append(f'<div style="margin-bottom:10px;"><b>{esc(label)}:</b> {body}</div>')

    if headline is None:
        raise RenderError("banner has no 'headline' part to render as the banner face")

    values = {"headline": headline, "pointer": pointer or ""}
    if subhead:
        values["subhead"] = subhead
    return values, "".join(notes)


def fill_newsletter(plan):
    """Newsletter is coverage_mode 'full': every part except headline/standfirst/cta/
    placement-spec is genuine reader content and becomes an item card."""
    title = intro = cta = None
    items, notes = [], []
    for _, part in ordered_parts(plan):
        kind = part.get("part_kind")
        body = part_html(part)
        if kind == "headline" and title is None:
            title = body
        elif kind == "standfirst" and intro is None:
            intro = body
        elif kind == "cta" and cta is None:
            cta = body
        elif kind == "placement-spec":
            notes.append(f'<div style="margin-bottom:10px;"><b>Placement:</b> {body}</div>')
        else:
            heading = part.get("title") or ""
            items.append(f'<div class="nl-item">'
                         + (f'<div class="nl-item-heading">{esc(heading)}</div>' if heading else "")
                         + f'<div class="nl-item-body">{body}</div></div>')

    if title is None:
        raise RenderError("newsletter has no 'headline' part to use as the title")

    values = {"title": title, "items": "".join(items)}
    if intro:
        values["intro"] = intro
    if cta:
        values["cta"] = cta
    return values, "".join(notes)


def _extract_cta_link(part, theme):
    """A cta part's block content is a label, same as banner/newsletter — this schema has
    no structured url field. If the practitioner has written the destination into the
    label itself (e.g. "Activate your account: https://portal.example/activate"), use it
    as a real href; otherwise render the label as emphasised text with no invented link,
    per the never-invent rule."""
    text = part_plain_text(part)
    m = URL_RE.search(text)
    if not m:
        return None, esc(text)
    url = m.group(0)
    label = esc((text[:m.start()] + text[m.end():]).strip(" :—-") or "Activate")
    accent = theme["palette"].get("accent", "#000000")
    on_accent = "#ffffff"
    font = _inline_font_stack(theme, "body")
    href = esc_attr(url)
    return (
        f'<a href="{href}" style="display:inline-block;background:{accent};'
        f'color:{on_accent};font-family:{font};font-size:15px;font-weight:600;'
        f'padding:12px 24px;border-radius:4px;text-decoration:none;">{label}</a>'
    ), None


def fill_edm(plan, theme):
    subject = preheader = headline = None
    body_parts, cta_part = [], None

    for _, part in ordered_parts(plan):
        kind = part.get("part_kind")
        inline_gap = {}
        rendered = part_html(part, inline_gap=inline_gap)
        if kind == "subject" and subject is None:
            subject = part_plain_text(part)
        elif kind == "preheader" and preheader is None:
            preheader = esc(part_plain_text(part))
        elif kind == "headline" and headline is None:
            headline = rendered
        elif kind == "cta" and cta_part is None:
            cta_part = part
        else:
            title = part.get("title")
            if title and kind not in ("signoff",):
                body_parts.append(f'<p style="margin:0 0 4px 0;font-weight:700;color:{theme["palette"].get("ink", "#000")};">{esc(title)}</p>')
            body_parts.append(rendered)

    if headline is None:
        raise RenderError("edm has no 'headline' part to render as the headline")
    if not body_parts:
        raise RenderError("edm has no body content")

    values = {"headline": headline, "body": "".join(body_parts)}

    if cta_part is not None:
        cta_html, plain_label = _extract_cta_link(cta_part, theme)
        if cta_html:
            values["cta_block"] = cta_html
        else:
            print("  WARNING edm: cta part has no URL in its text — rendering as text, "
                  "not a button (write the destination into the cta label to get a real link)",
                  file=sys.stderr)
            values["cta_block"] = f'<p style="font-weight:600;">{plain_label}</p>'

    sources = sorted({s for _, part in ordered_parts(plan) for b in part.get("blocks", []) for s in b.get("sources", [])})
    values["footer"] = esc(f"Sources: {', '.join(sources)}" if sources else "No sources recorded")
    values["_subject"] = subject or headline
    values["_preheader"] = preheader or ""

    for token in ("canvas", "ink", "ink_soft", "muted", "accent", "rule"):
        values[token] = theme["palette"].get(token, "#000000")
    values["font_sans"] = _inline_font_stack(theme, "body")
    for token, px in (("pad_sm", 8), ("pad_md", 16), ("pad_lg", 24)):
        values[token] = f"{px}px"

    return values


def _inline_font_stack(theme, role):
    """Quote family names with spaces for a bare CSS value. Flattens first: apply_brand.py's
    font_stack() appends `web_safe_fallback` (e.g. "system-ui, sans-serif") as ONE stack
    entry, which already contains a comma — quoting that whole entry as a single family
    name would be wrong, so every entry is split on "," before quoting."""
    stack = theme.get("typography", {}).get(role) or ["sans-serif"]
    names = [n.strip() for entry in stack for n in str(entry).split(",") if n.strip()]
    return ", ".join(f"'{n}'" if " " in n else n for n in names)


FILLERS = {"banner": fill_banner, "newsletter-roundup": fill_newsletter}


# --- layout loading and substitution -----------------------------------------


def load_layouts(template_dir):
    source = COMMENT_RE.sub("", (template_dir / "layouts.html").read_text(encoding="utf-8"))
    return dict(TEMPLATE_BLOCK_RE.findall(source))


def fill_layout(layout_html, values):
    def drop_or_keep(match):
        name, inner = match.group(1), match.group(2)
        return inner if values.get(name) else ""

    filled = OPTIONAL_RE.sub(drop_or_keep, layout_html)
    return TOKEN_RE.sub(lambda m: str(values.get(m.group(1), "")), filled)


# --- document assembly -------------------------------------------------------


WEB_DOC = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{brand_css}</style>
<style>{base_css}</style>
</head>
<body>
{body}
{notes}
</body>
</html>
"""

NOTES_WRAP = '<div style="max-width:640px;margin:16px auto;font-size:13px;color:#555;">{inner}</div>'

EDM_DOC = """<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<title>{subject}</title>
</head>
<body style="margin:0;padding:0;background:{canvas};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{preheader}</div>
{body}
</body>
</html>
"""


def brand_css_block(theme):
    p = theme["palette"]
    heading = _inline_font_stack(theme, "heading").replace("'", '"')
    sans = _inline_font_stack(theme, "body").replace("'", '"')
    lines = [":root {"]
    for role in ("primary", "secondary", "accent", "ink", "ink_soft", "muted", "canvas", "panel", "rule"):
        if role in p:
            lines.append(f"  --{role.replace('_', '-')}: {p[role]};")
    lines += [
        f'  --font-heading: {heading};',
        f'  --font-sans: {sans};',
        "  --space-1: 4px; --space-2: 8px; --space-3: 16px; --space-4: 24px; --space-5: 40px;",
        "}",
    ]
    return "\n".join(lines)


# --- main ---------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", type=Path)
    ap.add_argument("--brief", type=Path, required=True, help="change_brief.json — QA is re-run against it")
    ap.add_argument("--brand", type=Path, required=True, help="brand_profile.json")
    ap.add_argument("--template-dir", type=Path, default=DEFAULT_TEMPLATE_DIR,
                     help="comms-html template directory (default: comms-assets/templates/comms-html)")
    ap.add_argument("-o", "--out", type=Path, default=None)
    args = ap.parse_args()

    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        brief = json.loads(args.brief.read_text(encoding="utf-8"))
        brand = json.loads(args.brand.read_text(encoding="utf-8"))

        channel = plan.get("channel")
        if channel not in CHANNEL_LAYOUT:
            raise RenderError(
                f"channel '{channel}' has no comms-html route. Supported: {', '.join(CHANNEL_LAYOUT)}"
            )

        # THE GATE — identical to route_channel.py: refuse while a hard QA failure stands.
        audit = qa_comms.audit(brief, plan, brand)
        if audit["fail"]:
            raise RenderError(
                f"{plan.get('run_id', '?')}: QA has {len(audit['fail'])} failure(s) — nothing is "
                f"rendered until they are fixed:\n" + "\n".join(f"  - {m}" for m in audit["fail"])
            )

        approval = (brand.get("approval") or {})
        if not approval.get("approved_by"):
            raise RenderError(
                "brand profile has no approval.approved_by — stop and ask for an approved brand "
                "before rendering. Do not build a lookalike."
            )

        if not args.template_dir.is_dir():
            raise RenderError(f"--template-dir not found: {args.template_dir}")

        layout_name = CHANNEL_LAYOUT[channel]
        profile = profile_html_template(args.template_dir)
        layout_profile = next((l for l in profile["layouts"] if l["part"] == layout_name), None)
        if layout_profile is None:
            available = ", ".join(l["part"] for l in profile["layouts"])
            raise RenderError(f"layout '{layout_name}' not found in {args.template_dir}. Available: {available}")

        layouts = load_layouts(args.template_dir)
        if layout_name not in layouts:
            raise RenderError(f"layout '{layout_name}' profiled but not found in layouts.html — stale profile")

        theme = apply_brand.build_theme(
            brand,
            apply_brand.palette_hex(brand),
            "html",
        )
        # apply_brand.py's own CLI validates contrast before writing a theme to disk; this
        # script imports the same function it uses to compute a ratio and re-checks here so
        # a caller who skipped `apply_brand.py`'s CLI cannot slip an inaccessible theme
        # through by calling build_theme() directly.
        min_ratio = (brand.get("accessibility") or {}).get("min_contrast_ratio", 4.5)
        colours = theme["palette"]
        failures = []
        for fg, bg in apply_brand.CONTRAST_PAIRS:
            if fg in colours and bg in colours:
                ratio = apply_brand.contrast_ratio(colours[fg], colours[bg])
                if ratio < min_ratio:
                    failures.append(f"{fg} on {bg}: {ratio:.2f}:1 (needs {min_ratio}:1)")
        if failures:
            raise RenderError("brand palette fails the accessibility floor:\n" +
                              "\n".join(f"  - {f}" for f in failures))

        if channel == "edm":
            values = fill_edm(plan, theme)
            known = {p["name"] for p in layout_profile["placeholders"]}
            unknown = set(values) - known - {"_subject", "_preheader"}
            if unknown:
                raise RenderError(f"internal error: filler produced token(s) not on layout 'edm': {unknown}")
            doc = EDM_DOC.format(
                subject=esc(values["_subject"]),
                canvas=theme["palette"].get("canvas", "#ffffff"),
                preheader=values["_preheader"],
                body=fill_layout(layouts[layout_name], values),
            )
        else:
            values, notes = FILLERS[layout_name](plan)
            known = {p["name"] for p in layout_profile["placeholders"]}
            unknown = set(values) - known
            if unknown:
                raise RenderError(f"internal error: filler produced token(s) not on layout '{layout_name}': {unknown}")
            base_css = (args.template_dir / "base.css").read_text(encoding="utf-8")
            doc = WEB_DOC.format(
                title=esc(f"{channel} — {plan.get('run_id', '')}"),
                brand_css=brand_css_block(theme),
                base_css=base_css,
                body=fill_layout(layouts[layout_name], values),
                notes=(NOTES_WRAP.format(inner=notes) if notes else ""),
            )

        out = args.out or Path(f"comms_{channel}.html")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(doc, encoding="utf-8")

        gaps = sum(1 for _, part in ordered_parts(plan) for b in part.get("blocks", []) if b.get("gap"))
        print(f"Rendered {channel} ({layout_name}) '{plan.get('run_id', '')}' -> {out} ({out.stat().st_size} bytes)")
        print(f"  brand: {brand.get('client', '?')} approved by {approval.get('approved_by')}   "
              f"design_provenance: {theme.get('design_provenance')}")
        if audit["warn"]:
            print(f"  {len(audit['warn'])} QA warning(s) carried into production")
        if gaps:
            print(f"  {gaps} [GAP] block(s) rendered visibly")
        return 0

    except RenderError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
