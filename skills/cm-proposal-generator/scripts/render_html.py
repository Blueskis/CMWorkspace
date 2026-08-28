#!/usr/bin/env python3
"""Render a proposal plan into a self-contained HTML slide deck (Stage 4, PoC path).

    python render_html.py proposal_plan.json proposal-assets/templates/html-generic \\
        -o proposals/acme-20260807/proposal.html

Reuses build_deck.py's validation and sequencing, so a plan is checked against the
template's layouts and placeholders exactly as it would be for the .pptx path — then
renders each slide through the matching layout in the template's layouts.html. Both come
from lib/deckkit, shared with the training-material generator.

Output is one standalone .html file with CSS and JS inlined, so it opens from disk with
no server and no network. Arrow keys or space to advance; `?print-pdf` appended to the
URL then Print → Save as PDF gives a paginated PDF.

Two things the renderer will not do quietly:

  * A block flagged `gap: true` renders as a visible amber [GAP] panel. It is never
    silently dropped and never filled with substitute text.
  * Every block's knowledge-bank source IDs render in the slide footer by default
    (`--sources footer`). Use `--sources hidden` only for a client-facing copy, and
    only once the practitioner has reviewed the provenance.

The .pptx path stays the eventual target — this exists so the pipeline can be exercised
end to end before the firm's approved template is available.
"""

import argparse
import html
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from deckkit.htmlkit import esc, fill_layout, load_layouts  # noqa: E402
from deckkit.manifest import build  # noqa: E402


# --- block rendering -------------------------------------------------------


def render_block(block):
    """One plan block -> an HTML fragment. Gaps always render visibly."""
    if block.get("gap"):
        note = esc(block.get("gap_note") or "Not covered by the knowledge bank.")
        return f'<div class="gap"><span class="gap-tag">[GAP]</span>{note}</div>'

    kind, content = block["kind"], block["content"]

    if kind == "text":
        # Bare text, no wrapper — for placeholders the layout already wraps in an
        # element of its own (<h1>{{title}}</h1>, <div class="client">{{client}}</div>).
        # Using "heading" there nests an <h3> inside and loses the layout's styling.
        return esc(content)

    if kind == "heading":
        return f"<h3>{esc(content)}</h3>"

    if kind == "paragraph":
        paras = content if isinstance(content, list) else [content]
        return "".join(f"<p>{esc(p)}</p>" for p in paras)

    if kind == "bullets":
        items = content if isinstance(content, list) else [content]
        return "<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>"

    if kind == "table":
        headers = content.get("headers", [])
        rows = content.get("rows", [])
        head = "".join(f"<th>{esc(h)}</th>" for h in headers)
        body = "".join(
            "<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>" for row in rows
        )
        return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"

    if kind == "metric":
        metrics = content if isinstance(content, list) else [content]
        tiles = "".join(
            f'<div class="metric"><div class="value">{esc(m.get("value", ""))}</div>'
            f'<div class="label">{esc(m.get("label", ""))}</div></div>'
            for m in metrics
        )
        return f'<div class="metrics">{tiles}</div>'

    if kind == "phases":
        phases = content if isinstance(content, list) else [content]
        out = []
        for i, phase in enumerate(phases, 1):
            detail = phase.get("detail")
            if isinstance(detail, list):
                inner = "<ul>" + "".join(f"<li>{esc(d)}</li>" for d in detail) + "</ul>"
            else:
                inner = f"<p>{esc(detail)}</p>" if detail else ""
            out.append(
                f'<div class="phase"><div class="n">{esc(phase.get("label", f"Phase {i}"))}</div>'
                f'<h3>{esc(phase.get("name", ""))}</h3>{inner}</div>'
            )
        return f'<div class="timeline">{"".join(out)}</div>'

    if kind == "members":
        members = content if isinstance(content, list) else [content]
        cards = []
        for m in members:
            name = str(m.get("name", ""))
            # A role profile can come from the bank while the person is still
            # unconfirmed — flag those names so an unstaffed slot reads as one.
            if name.startswith("[GAP]"):
                shown = (f'<span class="gap-tag">[GAP]</span>'
                         f'{esc(name[len("[GAP]"):].strip())}')
                cls = "member member-gap"
            else:
                shown, cls = esc(name), "member"
            cards.append(
                f'<div class="{cls}"><div class="name">{shown}</div>'
                f'<div class="role">{esc(m.get("role", ""))}</div>'
                f'<p>{esc(m.get("bio", ""))}</p></div>'
            )
        return f'<div class="team">{"".join(cards)}</div>'

    if kind == "image":
        src = content.get("src") if isinstance(content, dict) else content
        alt = content.get("alt", "") if isinstance(content, dict) else ""
        return f'<img src="{html.escape(str(src))}" alt="{html.escape(str(alt))}">'

    if kind == "notes":
        return ""  # handled separately as speaker notes

    return f"<p>{esc(content)}</p>"


def slide_footer(step, plan, mode, position, total):
    if mode == "hidden":
        return ""
    sources = sorted({s for fill in step["fills"] for s in fill.get("sources", [])})
    gaps = sum(1 for fill in step["fills"] if fill.get("gap"))

    left = ""
    if sources:
        left = "Sources: " + " ".join(f"<code>{esc(s)}</code>" for s in sources)
    if gaps:
        marker = f"{gaps} open gap{'s' if gaps > 1 else ''}"
        left = f"{left} · {marker}" if left else marker
    if not left:
        left = "No sources recorded"

    right = f"{esc(plan.get('client', ''))} · {position} / {total}".strip(" ·")
    return f'<div class="slide-foot"><div class="sources">{left}</div><div>{right}</div></div>'


def render_slide(step, layouts, plan, sources_mode, position, total):
    layout_html = layouts.get(step["layout_part"])
    if layout_html is None:
        raise KeyError(f"layout '{step['layout_part']}' not in layouts.html")

    values = {}
    for fill in step["fills"]:
        rendered = render_block(fill)
        key = fill["placeholder"]
        values[key] = values.get(key, "") + rendered

    values.setdefault("title", esc(step["title"]))
    values["title"] = values["title"] or esc(step["title"])
    values["footer"] = slide_footer(step, plan, sources_mode, position, total)

    body = fill_layout(layout_html, values)
    notes = ""
    if step.get("speaker_notes"):
        notes = f'<aside class="notes">{esc(step["speaker_notes"])}</aside>'
    return f'<section data-layout="{esc(step["layout_part"])}">{body}{notes}</section>'


# --- document assembly -----------------------------------------------------

DOC = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{reset}</style>
<style>{reveal}</style>
<style>{theme}</style>
</head>
<body>
<div class="reveal"><div class="slides">
{slides}
</div></div>
<script>{js}</script>
<script>
Reveal.initialize({{
  hash: true, slideNumber: false, controls: true, progress: true,
  center: false, transition: 'none',
  width: 1280, height: 720, margin: 0.04,
  pdfSeparateFragments: false
}});
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", type=Path)
    ap.add_argument("template_dir", type=Path, help="HTML template directory (has layouts.html)")
    ap.add_argument("-o", "--out", type=Path, default=Path("proposal.html"))
    ap.add_argument("--sources", choices=["footer", "hidden"], default="footer",
                    help="Show knowledge-bank source IDs per slide (default: footer). "
                         "'hidden' is for a reviewed client-facing copy only.")
    ap.add_argument("--profile", type=Path,
                    help="template_profile.json (default: <template_dir>/template_profile.json)")
    args = ap.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    profile_path = args.profile or (args.template_dir / "template_profile.json")
    if not profile_path.is_file():
        sys.exit(f"no template profile at {profile_path} — run profile_template.py first")
    profile = json.loads(profile_path.read_text(encoding="utf-8"))

    steps, errors = build(plan, profile)
    if errors:
        for err in errors:
            print(f"  ERROR {err}", file=sys.stderr)
        sys.exit("plan does not validate against the template — fix the plan, not the renderer")

    layouts = load_layouts(args.template_dir)
    vendor = args.template_dir / "vendor"

    total = len(steps)
    slides = "\n".join(
        render_slide(step, layouts, plan, args.sources, i, total)
        for i, step in enumerate(steps, 1)
    )

    doc = DOC.format(
        title=esc(f"{plan.get('client', 'Proposal')} — {plan.get('engagement_title', plan.get('run_id', ''))}"),
        reset=(vendor / "reset.css").read_text(encoding="utf-8"),
        reveal=(vendor / "reveal.css").read_text(encoding="utf-8"),
        theme=(args.template_dir / "theme.css").read_text(encoding="utf-8"),
        js=(vendor / "reveal.js").read_text(encoding="utf-8"),
        slides=slides,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(doc, encoding="utf-8")

    gaps = sum(1 for s in steps for f in s["fills"] if f.get("gap"))
    size_kb = args.out.stat().st_size // 1024
    print(f"Rendered {total} slides -> {args.out} ({size_kb} KB, self-contained)")
    print(f"  template: {profile['template']}   sources: {args.sources}")
    if gaps:
        print(f"  {gaps} [GAP] block(s) rendered visibly — see qa_report.md for the action list")
    limit = plan.get("slide_budget", {}).get("limit")
    if limit and total > limit:
        print(f"  WARNING: {total} slides exceeds the RFP limit of {limit}", file=sys.stderr)
    print(f"  Draft for practitioner review — generated {date.today().isoformat()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
