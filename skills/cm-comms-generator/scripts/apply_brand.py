#!/usr/bin/env python3
"""Validate a brand profile and emit the theme every producer builds against.

    python apply_brand.py brand_profile.json -o comms/<run>/deck_theme.json
    python apply_brand.py brand_profile.json --format docx -o comms/<run>/docx_theme.json

Turns the palette and typography into a flat, producer-ready theme — hex values resolved,
font stacks assembled, page setup carried through — so the .pptx and .docx builds read one
small file instead of re-deriving the brand each time.

Two hard stops, both before anything is written:

  * `approval.approved_by` must be populated. A brand profile nobody approved is a
    lookalike, and this script will not emit a theme for one.
  * Every ink-on-background pair is checked for WCAG contrast against
    `accessibility.min_contrast_ratio`. A palette that produces unreadable slides fails
    here rather than in front of an audience.

STATUS (v0.2): this validates and translates; it does not build. It places no logo — that
needs an asset this repo does not have and a placement judgement a script should not make —
and it does not alter any client template. When a theme is used for a from-scratch build
rather than on the client's own .potx/.dotx, the result carries the client's colours but is
NOT the client's approved template: say exactly that at handover.

(v0.1 also copied and recoloured an HTML slide template. That render target was retired when
the deck channel moved to .pptx; the palette and contrast logic is unchanged.)
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Palette role -> the semantic name producers consume.
PALETTE_ROLES = ("primary", "secondary", "accent", "ink", "ink_soft", "muted",
                 "canvas", "panel", "rule", "error", "success")

# Pairs that must stay legible: (foreground key, background key).
CONTRAST_PAIRS = [
    ("ink", "canvas"),
    ("ink_soft", "canvas"),
    ("ink", "panel"),
    ("ink_soft", "panel"),
    ("accent", "canvas"),
]

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def relative_luminance(rgb):
    """WCAG 2.1 relative luminance."""
    channels = []
    for raw in rgb:
        c = raw / 255
        channels.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg_hex, bg_hex):
    l1 = relative_luminance(hex_to_rgb(fg_hex))
    l2 = relative_luminance(hex_to_rgb(bg_hex))
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def palette_hex(brand):
    """Flatten the profile's palette to {role: '#rrggbb'}, skipping malformed entries."""
    out = {}
    for key, value in (brand.get("palette") or {}).items():
        if isinstance(value, dict) and HEX_RE.match(str(value.get("hex", ""))):
            out[key] = value["hex"]
    return out


def font_stack(face, fallback):
    if not face or not face.get("family"):
        return None
    parts = [face["family"]] + list(face.get("fallbacks", []))
    if fallback:
        parts.append(fallback)
    return parts


def build_theme(brand, colours, fmt):
    typo = brand.get("typography", {})
    fallback = typo.get("web_safe_fallback", "sans-serif")
    specs = brand.get("channel_specs", {})

    theme = {
        "client": brand.get("client"),
        "format": fmt,
        "approved_by": (brand.get("approval") or {}).get("approved_by"),
        "approved_date": (brand.get("approval") or {}).get("approved_date"),
        "palette": {k: colours[k] for k in PALETTE_ROLES if k in colours},
        "typography": {
            "heading": font_stack(typo.get("heading"), fallback),
            "body": font_stack(typo.get("body"), fallback),
            "min_size_pt": typo.get("min_size_pt"),
        },
        "accessibility": brand.get("accessibility", {}),
        "palette_rules": brand.get("palette_rules", []),
        "logo": brand.get("logo", {}),
        "logo_placement": "NOT APPLIED — a practitioner places the logo by hand",
    }

    if fmt == "pptx":
        deck = specs.get("briefing_deck", {})
        theme["deck"] = {
            "aspect_ratio": deck.get("aspect_ratio", "16:9"),
            "max_slides": deck.get("max_slides"),
            "bullets_per_slide_max": deck.get("bullets_per_slide_max"),
            "potx_path": deck.get("potx_path"),
        }
        theme["design_provenance"] = ("client-approved-template" if deck.get("potx_path")
                                      else "generated-unapproved")
    elif fmt == "docx":
        page = specs.get("docx", {})
        theme["page"] = {
            "size": page.get("page_size", "A4"),
            "margins_mm": page.get("margins_mm", 25),
            "dotx_path": page.get("dotx_path"),
        }
        theme["design_provenance"] = ("client-approved-template" if page.get("dotx_path")
                                      else "generated-unapproved")
    return theme


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("brand", type=Path, help="brand_profile.json")
    ap.add_argument("-o", "--out", type=Path, default=Path("deck_theme.json"))
    ap.add_argument("--format", choices=["pptx", "docx"], default="pptx",
                    help="Which producer this theme is for (default: pptx)")
    args = ap.parse_args()

    brand = json.loads(args.brand.read_text(encoding="utf-8"))

    approval = brand.get("approval") or {}
    if not approval.get("approved_by"):
        sys.exit(
            "brand profile has no approval.approved_by — stop and ask the client for an "
            "approved template or brand guidelines. Do not build a lookalike."
        )

    colours = palette_hex(brand)
    if not colours:
        sys.exit("brand profile has no usable palette — nothing to apply")

    min_ratio = (brand.get("accessibility") or {}).get("min_contrast_ratio", 4.5)
    failures, reported = [], []
    for fg, bg in CONTRAST_PAIRS:
        if fg in colours and bg in colours:
            ratio = contrast_ratio(colours[fg], colours[bg])
            reported.append((fg, bg, ratio))
            if ratio < min_ratio:
                failures.append(f"{fg} on {bg}: {ratio:.2f}:1 (needs {min_ratio}:1)")

    # Fail before writing. A theme on disk that fails accessibility is worse than none,
    # because the next command will happily build from it.
    if failures:
        for fg, bg, ratio in reported:
            print(f"  contrast {fg} on {bg}: {ratio:.2f}:1"
                  f"{'  OK' if ratio >= min_ratio else '  FAIL'}")
        for f in failures:
            print(f"  ERROR {f}", file=sys.stderr)
        sys.exit("palette fails the accessibility floor — fix the profile. Nothing was written.")

    theme = build_theme(brand, colours, args.format)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(theme, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    print(f"Theme ({args.format}) -> {args.out}")
    print(f"  palette: {', '.join(f'{k}={v}' for k, v in sorted(theme['palette'].items()))}")
    for fg, bg, ratio in reported:
        print(f"  contrast {fg} on {bg}: {ratio:.2f}:1  OK")

    if theme.get("design_provenance") == "generated-unapproved":
        print("  no client template referenced — this is a FROM-SCRATCH build carrying the "
              "client's colours, NOT their approved template. Say so at handover.")
    else:
        print("  builds on the client's own template — design_provenance: "
              "client-approved-template")
    print("  No logo placed — that remains a practitioner step.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
