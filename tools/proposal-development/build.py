#!/usr/bin/env python3
"""Assemble the Proposal Development Tool artifact from its template and
the tested src/*.js modules — stdlib only, matching the rest of this repo.

    python3 build.py -o out/proposal-development-tool.html

The template carries a single {{MODULES}} marker inside its main <script>
block; this script replaces it with the concatenated, tested modules from
src/ (in dependency order). Each module ends with a
`if (typeof module !== "undefined") { module.exports = ... }` guard for
Node's test runner — that guard is dead code in a browser (module is never
declared there), so the modules are inlined verbatim, unmodified from what
node --test actually exercised. xml-shim.js is deliberately NOT inlined:
it exists only for Node, where no native DOMParser is available; a browser
always takes the DOMParser branch in ooxml-read.js's parseXml(), so the
shim's require() call is never reached there.
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "src"
TEMPLATE = HERE / "artifact" / "proposal-development-tool.html.tmpl"

# Dependency order: a module may only reference names defined by a module
# earlier in this list (they all land in one top-level script scope).
MODULE_ORDER = [
    "ooxml-zip.js",
    "ooxml-read.js",
    "ooxml-write.js",
    "build-pptx.js",
    "outline.js",
    "retrieve.js",
    "triage-edit.js",
    "draft.js",
    "assistant.js",
    "export.js",
]


def build_modules_bundle():
    parts = []
    for name in MODULE_ORDER:
        path = SRC / name
        if not path.is_file():
            sys.exit(f"missing module: {path}")
        parts.append(f"/* ---- {name} ---- */\n" + path.read_text(encoding="utf-8"))
    return "\n\n".join(parts)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-o", "--out", type=Path, default=HERE / "out" / "cm-proposal-reference-tool.html")
    args = ap.parse_args()

    if not TEMPLATE.is_file():
        sys.exit(f"template not found: {TEMPLATE}")
    template_text = TEMPLATE.read_text(encoding="utf-8")

    if "{{MODULES}}" not in template_text:
        sys.exit("template has no {{MODULES}} marker")

    bundle = build_modules_bundle()
    output = template_text.replace("{{MODULES}}", bundle)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(output, encoding="utf-8")
    print(f"Wrote {args.out} ({len(output):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
