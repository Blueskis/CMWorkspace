#!/usr/bin/env python3
"""Render a training plan into a self-contained HTML deck (Stage 4, PoC path).

    python render_html.py training_plan.json training-assets/templates/html-training \\
        -o training/<run>/training.html
    python render_html.py training_plan.json <template> -o participant.html \\
        --answers hidden --sources hidden

Reuses lib/deckkit's validation and sequencing, so a plan is checked against the
template's layouts and placeholders exactly as it would be for the .pptx path — then
renders each slide through the matching layout in the template's layouts.html.

Output is one standalone .html file: CSS, JS and **every screenshot** inlined, so it opens
from disk with no server and no network. Arrow keys or space to advance; `?print-pdf`
appended to the URL then Print -> Save as PDF gives a paginated PDF.

Four things the renderer will not do quietly:

  * A block flagged `gap: true` renders as a visible amber [GAP] panel. Never dropped,
    never filled with substitute text.
  * A screenshot is embedded as its original bytes in a data: URI — not re-encoded, not
    resized, not cropped. Callouts are numbered steps rendered beside the image by the
    layout, so the capture stays an unmodified artifact of the spec.
  * Knowledge-check answers never reach a slide. They are written into the speaker notes,
    and `--answers hidden` drops them entirely for a participant copy.
  * A diagram whose renderer is missing degrades to a visible labelled panel of its
    Mermaid source, not to a blank space.

Mermaid is inlined from the template's vendor/ **only when the deck contains a diagram**,
so a deck without one stays small.
"""

import argparse
import base64
import html
import json
import mimetypes
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from deckkit.htmlkit import esc, fill_layout, load_layouts  # noqa: E402
from deckkit.manifest import build  # noqa: E402

DOC = """<!doctype html>
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
{mermaid}
<script>
// Diagrams are drawn before Reveal takes over the DOM; see MERMAID_BOOT for why.
(window.__diagramsReady || Promise.resolve()).then(function () {{
  Reveal.initialize({{ width: 1280, height: 720, margin: 0.04, center: false,
                      hash: true, slideNumber: 'c/t', transition: 'none' }});
}});
</script>
</body>
</html>
"""

# reveal.css hides every slide but the current one, and a diagram laid out inside a
# display:none subtree measures its text as zero-width and fails — mermaid then paints its
# generic "Syntax error" box over a diagram whose source is perfectly valid. So diagrams are
# NOT rendered in place: mermaid.render() draws each one in its own temporary container
# attached to the body, and the finished SVG is moved into the slide. Reveal is initialised
# only once every diagram is in place.
MERMAID_BOOT = """<script>{lib}</script>
<script>
mermaid.initialize({{ startOnLoad: false, securityLevel: 'strict', theme: 'base',
  themeVariables: {{ fontFamily: '"Segoe UI", Roboto, Arial, sans-serif', fontSize: '15px',
    primaryColor: '#e3f3f0', primaryBorderColor: '#0f7b6c', primaryTextColor: '#14213d',
    lineColor: '#43506b', secondaryColor: '#f5f7fa', tertiaryColor: '#ffffff' }} }});
window.__diagramsReady = (async function () {{
  var blocks = document.querySelectorAll('pre.mermaid');
  for (var i = 0; i < blocks.length; i++) {{
    var el = blocks[i];
    try {{
      var out = await mermaid.render('mmd-' + i, el.textContent.trim());
      el.innerHTML = out.svg;
      el.setAttribute('data-rendered', 'true');
    }} catch (err) {{
      // Leave the source visible and say so, rather than showing an error box.
      console.error('diagram ' + i + ' did not render:', err);
      el.classList.add('diagram-failed');
      el.setAttribute('data-rendered', 'false');
    }}
  }}
}})();
</script>
"""


# --- content helpers -------------------------------------------------------


def data_uri(path):
    """Inline a file as a data: URI so the deck stays one self-contained document."""
    path = Path(path)
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{media_type};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def render_list(items, css_class=None, ordered=False):
    tag = "ol" if ordered else "ul"
    attr = f' class="{css_class}"' if css_class else ""
    return (f"<{tag}{attr}>"
            + "".join(f"<li>{esc(i)}</li>" for i in items)
            + f"</{tag}>")


def render_table(content):
    header = content.get("header", [])
    rows = content.get("rows", [])
    head = "".join(f"<th>{esc(h)}</th>" for h in header)
    body = "".join(
        "<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_agenda(items):
    out = []
    for n, item in enumerate(items, 1):
        if isinstance(item, dict):
            label, duration = item.get("title", ""), item.get("duration", "")
        else:
            label, duration = item, ""
        dur = f'<span class="dur">{esc(duration)}</span>' if duration else ""
        out.append(f'<div class="item"><span class="n">{n:02d}</span>'
                   f'<span>{esc(label)}</span>{dur}</div>')
    return f'<div class="agenda">{"".join(out)}</div>'


def render_questions(questions):
    """The five questions, as a learner sees them. Never the answers."""
    out = []
    for n, q in enumerate(questions, 1):
        kind = q.get("type", "mcq")
        label = "True / False" if kind == "true_false" else "Choose one"
        body = ""
        if kind == "true_false":
            body = '<div class="tf"><span>True</span><span>False</span></div>'
        else:
            body = render_list(q.get("options", []), css_class="options", ordered=True)
        out.append(
            f'<div class="question"><span class="qn">{n}</span>'
            f'<div class="stem">{esc(q.get("stem", ""))}'
            f'<span class="type">{label}</span></div>{body}</div>'
        )
    return f'<div class="questions">{"".join(out)}</div>'


def render_diagram(spec, have_mermaid):
    caption = spec.get("caption", "")
    figcaption = f"<figcaption>{esc(caption)}</figcaption>" if caption else ""
    if have_mermaid:
        inner = f'<pre class="mermaid">{esc(spec["mermaid"])}</pre>'
    else:
        inner = (
            '<div class="diagram-source"><span class="tag">Diagram — mermaid.min.js '
            'is not vendored in this template, so the source is shown instead</span>'
            f'<pre>{esc(spec["mermaid"])}</pre></div>'
        )
    return f'<figure class="diagram">{inner}{figcaption}</figure>'


def render_block(fill, have_mermaid):
    """One manifest fill -> an HTML fragment. Gaps always render visibly."""
    if fill.get("gap"):
        note = esc(fill.get("gap_note") or "Not covered by the source documents.")
        return f'<div class="gap"><span class="gap-tag">[GAP]</span>{note}</div>'

    kind, content = fill["kind"], fill["content"]

    if kind == "text":
        return esc(content)
    if kind == "heading":
        return f"<h3>{esc(content)}</h3>"
    if kind == "paragraph":
        return "".join(f"<p>{esc(p)}</p>" for p in
                       (content if isinstance(content, list) else [content]))
    if kind == "bullets":
        return render_list(content)
    if kind in ("steps", "callouts"):
        return render_list(content, css_class="steps")
    if kind == "agenda":
        return render_agenda(content)
    if kind == "table":
        return render_table(content)
    if kind == "image":
        src = data_uri(fill["asset_path"])
        alt = fill.get("alt") or ""
        return f'<img src="{src}" alt="{html.escape(alt)}">'
    if kind == "diagram":
        return render_diagram(fill["diagram"], have_mermaid)
    if kind == "questions":
        return render_questions(fill["questions"])
    if kind == "notes":
        return ""  # handled separately as speaker notes

    return f"<p>{esc(content)}</p>"


# --- slides ----------------------------------------------------------------


def answer_notes(questions):
    lines = ["ANSWER KEY — trainer copy"]
    for n, q in enumerate(questions, 1):
        if q.get("type") == "true_false":
            answer = "TRUE" if q.get("answer") else "FALSE"
        else:
            options, idx = q.get("options") or [], q.get("answer_index")
            answer = (f"{chr(65 + idx)}. {options[idx]}"
                      if isinstance(idx, int) and idx < len(options) else "(none recorded)")
        line = f"{n}. {answer}"
        if q.get("rationale"):
            line += f" — {q['rationale']}"
        if q.get("sources"):
            line += f" [{', '.join(q['sources'])}]"
        lines.append(line)
    return "\n".join(lines)


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

    right = esc(plan.get("course_title") or plan.get("system") or "")
    return (f'<div class="slide-foot"><div class="sources">{left}</div>'
            f'<div>{right} · {position}/{total}</div></div>')


def render_slide(step, layouts, plan, sources_mode, answers_mode, have_mermaid,
                 position, total):
    layout_id = Path(step["layout_part"]).stem
    layout_html = layouts.get(layout_id) or layouts.get(step["layout_part"])
    if layout_html is None:
        raise SystemExit(f"{step['slide_id']}: template has no layout '{layout_id}'")

    values = {"title": esc(step["title"])}
    for fill in step["fills"]:
        values[fill["placeholder"]] = render_block(fill, have_mermaid)
    values["footer"] = slide_footer(step, plan, sources_mode, position, total)

    notes = []
    if step.get("speaker_notes"):
        notes.append(step["speaker_notes"])
    if answers_mode == "notes":
        for fill in step["fills"]:
            if fill["kind"] == "questions":
                notes.append(answer_notes(fill["questions"]))
    notes_html = (f'<aside class="notes">{esc(chr(10).join(notes))}</aside>'
                  if notes else "")

    return f"<section>{fill_layout(layout_html, values)}{notes_html}</section>"


# --- driver ----------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", type=Path)
    ap.add_argument("template_dir", type=Path, help="HTML template directory (has layouts.html)")
    ap.add_argument("-o", "--out", type=Path, default=Path("training.html"))
    ap.add_argument("--sources", choices=["footer", "hidden"], default="footer",
                    help="Show source anchors per slide (default: footer). 'hidden' is for "
                         "a learner-facing copy, once the trainer has reviewed provenance.")
    ap.add_argument("--answers", choices=["notes", "hidden"], default="notes",
                    help="Where the knowledge-check answer key goes. 'notes' (default) puts "
                         "it in the speaker notes for the trainer copy; 'hidden' omits it "
                         "entirely, for the copy handed to participants.")
    ap.add_argument("--profile", type=Path,
                    help="template_profile.json (default: <template_dir>/template_profile.json)")
    args = ap.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    profile_path = args.profile or (args.template_dir / "template_profile.json")
    if not profile_path.is_file():
        sys.exit(f"no template profile at {profile_path} — run profile_template.py first")
    profile = json.loads(profile_path.read_text(encoding="utf-8"))

    steps, errors = build(plan, profile, group_key="modules", group_id_key="module_id")
    if errors:
        for err in errors:
            print(f"  ERROR {err}", file=sys.stderr)
        sys.exit("plan does not validate against the template — fix the plan, not the renderer")

    layouts = load_layouts(args.template_dir)
    vendor = args.template_dir / "vendor"
    mermaid_lib = vendor / "mermaid.min.js"

    needs_mermaid = any(f["kind"] == "diagram" for s in steps for f in s["fills"])
    have_mermaid = needs_mermaid and mermaid_lib.is_file()

    total = len(steps)
    slides = "\n".join(
        render_slide(step, layouts, plan, args.sources, args.answers, have_mermaid, i, total)
        for i, step in enumerate(steps, 1)
    )

    doc = DOC.format(
        title=esc(f"{plan.get('course_title', 'Training')} — {plan.get('system', plan.get('run_id', ''))}"),
        reset=(vendor / "reset.css").read_text(encoding="utf-8"),
        reveal=(vendor / "reveal.css").read_text(encoding="utf-8"),
        theme=(args.template_dir / "theme.css").read_text(encoding="utf-8"),
        js=(vendor / "reveal.js").read_text(encoding="utf-8"),
        slides=slides,
        mermaid=(MERMAID_BOOT.format(lib=mermaid_lib.read_text(encoding="utf-8"))
                 if have_mermaid else ""),
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(doc, encoding="utf-8")

    gaps = sum(1 for s in steps for f in s["fills"] if f.get("gap"))
    images = sum(1 for s in steps for f in s["fills"] if f["kind"] == "image")
    diagrams = sum(1 for s in steps for f in s["fills"] if f["kind"] == "diagram")
    checks = sum(1 for s in steps for f in s["fills"] if f["kind"] == "questions")
    size_kb = args.out.stat().st_size // 1024

    print(f"Rendered {total} slides -> {args.out} ({size_kb:,} KB, self-contained)")
    print(f"  template: {profile['template']}   sources: {args.sources}   "
          f"answers: {args.answers}")
    print(f"  {images} screenshot(s) inlined, {diagrams} diagram(s), {checks} knowledge check(s)")
    if gaps:
        print(f"  {gaps} [GAP] block(s) rendered visibly — see qa_report.md for the action list")
    if needs_mermaid and not have_mermaid:
        print(f"  WARNING: {diagrams} diagram(s) rendered as source panels — "
              f"{mermaid_lib} is not vendored", file=sys.stderr)
    if size_kb > 15 * 1024:
        print(f"  WARNING: {size_kb:,} KB is large for a file people will email around. "
              f"The screenshots are the weight — consider fewer, or smaller captures.",
              file=sys.stderr)
    limit = plan.get("slide_budget", {}).get("limit")
    if limit and total > limit:
        print(f"  WARNING: {total} slides exceeds the session limit of {limit}", file=sys.stderr)
    print(f"  Draft for trainer review — generated {date.today().isoformat()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
