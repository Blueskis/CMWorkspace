"""The HTML template dialect: {{tokens}}, {{#optional}} regions, and layout loading.

An HTML template directory is the render target that lets a pipeline be exercised before
an approved .potx exists. Its layouts.html holds one `<template data-layout="...">` block
per layout — the equivalent of a slideLayout in a .potx — with `{{name}}` placeholders and
`{{#name}}...{{/name}}` regions that drop out entirely when that placeholder has no
content, so a layout degrades cleanly rather than leaving an empty panel behind.

These regexes are the single definition of that dialect. `template_profile` derives a
template's placeholder inventory with them and the renderers fill layouts with them, so a
profile cannot describe a syntax the renderer does not honour.
"""

import html
import re

COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
TEMPLATE_BLOCK_RE = re.compile(
    r'<template\s+data-layout="([^"]+)"\s*>(.*?)</template>', re.DOTALL
)
OPTIONAL_RE = re.compile(r"\{\{#([a-z_]+)\}\}(.*?)\{\{/\1\}\}", re.DOTALL)
TOKEN_RE = re.compile(r"\{\{([a-z_]+)\}\}")


def esc(value):
    """Escape for HTML body text.

    `quote=False` deliberately: this escapes text destined for element content, where a
    literal quote is fine and escaping it to &quot; would be visible on the slide. Values
    going into an attribute are escaped by the caller with `html.escape` directly.
    """
    return html.escape(str(value), quote=False)


def fill_layout(layout_html, values):
    """Substitute {{tokens}}, dropping {{#optional}} regions with no value."""

    def drop_or_keep(match):
        name, inner = match.group(1), match.group(2)
        return inner if values.get(name) else ""

    filled = OPTIONAL_RE.sub(drop_or_keep, layout_html)
    return TOKEN_RE.sub(lambda m: values.get(m.group(1), ""), filled)


def load_layouts(template_dir):
    """Return {layout_id: html} from a template directory's layouts.html."""
    source = COMMENT_RE.sub(
        "", (template_dir / "layouts.html").read_text(encoding="utf-8")
    )
    return dict(TEMPLATE_BLOCK_RE.findall(source))
