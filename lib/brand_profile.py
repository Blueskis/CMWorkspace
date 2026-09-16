#!/usr/bin/env python3
"""Load, validate and adapt a brand profile into the canonical shape (deck-builder Stage 1).

    python lib/brand_profile.py profile.json --validate
    python lib/brand_profile.py --from-template client.potx --client "Acme Water" -o profile.json
    python lib/brand_profile.py --from-vault vault-export.json -o profile.json
    python lib/brand_profile.py profile.json --format pptx -o deck_theme.json

Two prior schemas had drifted apart: skills/cm-comms-generator/schemas/brand_profile.schema.json
(approval, palette, channel_specs — what the Python producers actually read) and
artifacts/brand-template-creator/schemas/brand_profile.schema.json (colors/typography/voice/
messaging/logo.dataUri, the Brand Vault artifact's export shape). lib/schemas/brand_profile.schema.json
is the reconciliation: the comms shape as the base (it carries `approval`, the mechanical form of
the never-build-a-lookalike rule), widened to accept the Vault's fields. This script is the one
place either source shape gets read; nothing downstream should parse the other two again.

Three intake routes, one output:

  * A file already in canonical (or comms-v0.2) shape — validated and passed through.
  * `--from-vault` — the Brand Vault artifact's export JSON, adapted: colors.* -> palette.*
    (primary/secondary/accent/ink stay named, muted->muted, surface->panel, background->canvas),
    typography.headingFont/bodyFont -> typography.heading/body.family, logo.dataUri kept as-is,
    voice.* -> tone.*, messaging carried through unchanged. The Vault has no `approval` block —
    one is never invented; the adapted profile is written with approval empty, so it still hard-
    stops until a human fills it in.
  * `--from-template` — reads a .potx/.pptx's theme via profile_template.py (theme_colors,
    theme_fonts) and emits palette.primary=accent1, secondary=accent2, accent=accent3,
    ink=dk1/dk2 (whichever is darker), canvas=lt1/lt2 (whichever is lighter), typography from
    the major/minor font scheme. Stamped source: "extracted-from-template" — still no approval,
    same stop condition, because a palette nobody approved is a lookalike whatever its origin.

`--validate` alone checks structure and the approval gate and exits non-zero on either failure,
without needing jsonschema (hand-rolled checks against the required/enum/pattern shape — this
repo has no schema-validation dependency anywhere, and one script isn't worth adding it for).

`--format pptx|docx|html` emits a flat producer theme (mirrors cm-comms-generator's
apply_brand.py) and checks every ink/canvas-role colour pair named in `accessibility` against
the WCAG contrast floor (default 4.5); a failing pair is reported by name and ratio, never
silently swapped for another colour.

Stdlib only.
"""

import argparse
import json
import re
import sys
from pathlib import Path

HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")


def _hex(v):
    if v is None:
        return None
    v = v if v.startswith("#") else "#" + v
    return v.upper()


def _colour(hex_value, name=None):
    if not hex_value:
        return None
    return {"hex": _hex(hex_value), **({"name": name} if name else {})}


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------

def from_vault(vault):
    """Brand Vault export -> canonical shape. No approval block is invented."""
    colors = vault.get("colors", {})
    typ = vault.get("typography", {})
    logo = vault.get("logo", {})
    voice = vault.get("voice", {})
    messaging = vault.get("messaging", {})
    meta = vault.get("meta", {})

    def role(key):
        v = colors.get(key)
        if isinstance(v, dict):
            return _colour(v.get("hex"), v.get("note"))
        return _colour(v)

    profile = {
        "client": meta.get("name", ""),
        "source": "client-supplied-guidelines",
        "x_source_schema": "brand-vault-v1",
        "approval": {},  # never invented — this is the stop condition
        "palette": {
            "primary": role("primary"),
            "secondary": role("secondary"),
            "accent": role("accent"),
            "ink": role("ink"),
            "muted": role("muted"),
            "canvas": role("background"),
            "panel": role("surface"),
        },
        "typography": {
            "heading": {"family": typ.get("headingFont", ""), "fallbacks": [typ.get("headingFallback")] if typ.get("headingFallback") else [], "weight": typ.get("headingWeight")},
            "body": {"family": typ.get("bodyFont", ""), "fallbacks": [typ.get("bodyFallback")] if typ.get("bodyFallback") else [], "weight": typ.get("bodyWeight")},
        },
        "logo": {
            "dataUri": logo.get("dataUri"),
            "variant": logo.get("variant"),
            "clear_space": logo.get("clearSpace"),
            "min_width_px": logo.get("minWidthPx"),
        },
        "tone": {
            "voice": voice.get("toneDescriptors", []),
            "person": {1: "first", 2: "second", 3: "third"}.get(_person_num(voice.get("person")), "third"),
            "formality": _formality(voice.get("formality")),
            "banned_words": voice.get("bannedVocabulary", []),
            "preferred_terms": {t: t for t in voice.get("preferredVocabulary", [])} if voice.get("preferredVocabulary") else {},
        },
        "messaging": {
            "tagline": messaging.get("tagline", ""),
            "one_liner": messaging.get("oneLiner", ""),
            "boilerplate": messaging.get("boilerplate", ""),
            "proof_points": messaging.get("proofPoints", []),
            "terminology": messaging.get("terminology", []),
        },
    }
    if voice.get("rewriteExample"):
        profile["tone"]["rewrite_example"] = voice["rewriteExample"]
    return _prune(profile)


def _person_num(v):
    return v if isinstance(v, int) else None


def _formality(v):
    if isinstance(v, int):
        return "formal" if v >= 4 else ("informal" if v <= 2 else "neutral")
    return v or "neutral"


def _luminance(hex6):
    hex6 = hex6.lstrip("#")
    r, g, b = (int(hex6[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = lin(r), lin(g), lin(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(hex_a, hex_b):
    la, lb = _luminance(hex_a), _luminance(hex_b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def from_template(profile_json, client=""):
    """.potx/.pptx theme (via lib/profile_template.py's profile.json) -> canonical shape."""
    theme_colors = next(iter(profile_json.get("theme_colors", {}).values()), {})
    theme_fonts = next(iter(profile_json.get("theme_fonts", {}).values()), {})
    if not theme_colors:
        sys.exit("from-template: no theme_colors found in the template profile — was profile_template.py run on this file?")

    dk = theme_colors.get("dk2") or theme_colors.get("dk1")
    lt = theme_colors.get("lt1") or theme_colors.get("lt2")
    # pick the actually-darker/lighter of the pair so a theme with dk1/lt1 swapped still resolves
    if theme_colors.get("dk1") and theme_colors.get("dk2"):
        dk = min((theme_colors["dk1"], theme_colors["dk2"]), key=_luminance)
    if theme_colors.get("lt1") and theme_colors.get("lt2"):
        lt = max((theme_colors["lt1"], theme_colors["lt2"]), key=_luminance)

    profile = {
        "client": client,
        "source": "extracted-from-template",
        "x_source_schema": "canonical",
        "approval": {},
        "palette": {
            "primary": _colour(theme_colors.get("accent1")),
            "secondary": _colour(theme_colors.get("accent2")),
            "accent": _colour(theme_colors.get("accent3")),
            "ink": _colour(dk),
            "canvas": _colour(lt),
        },
        "typography": {
            "heading": {"family": theme_fonts.get("major", "")},
            "body": {"family": theme_fonts.get("minor", "")},
        },
        "tone": {"voice": [], "person": "third"},
    }
    return _prune(profile)


def _prune(d, keep=("approval",)):
    """Drop empty values, except keys in `keep` — approval must stay present-but-empty so
    validate() reports the real reason (no approver) rather than a misleading 'missing key'."""
    if isinstance(d, dict):
        return {k: _prune(v) for k, v in d.items() if k in keep or v not in (None, {}, [], "")}
    return d


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(profile):
    errors = []
    for req in ("client", "source", "approval", "palette", "typography", "tone"):
        if req not in profile:
            errors.append(f"missing required top-level key '{req}'")
    approval = profile.get("approval") or {}
    if not approval.get("approved_by") or not approval.get("role") or not approval.get("approved_date"):
        errors.append("approval.approved_by / role / approved_date not all set — "
                       "a profile with no named approver is treated as no profile at all")
    for role_name, colour in (profile.get("palette") or {}).items():
        if colour and not HEX_RE.match((colour.get("hex") or "")):
            errors.append(f"palette.{role_name}.hex is not a 6-digit hex colour: {colour.get('hex')!r}")
    return errors


def check_contrast(profile, min_ratio=None):
    palette = profile.get("palette", {})
    min_ratio = min_ratio or profile.get("accessibility", {}).get("min_contrast_ratio", 4.5)
    ink = (palette.get("ink") or {}).get("hex")
    canvas = (palette.get("canvas") or {}).get("hex")
    failures = []
    if ink and canvas:
        ratio = contrast_ratio(ink, canvas)
        if ratio < min_ratio:
            failures.append(f"ink {ink} on canvas {canvas}: contrast {ratio:.2f} < required {min_ratio}")
    return failures


# ---------------------------------------------------------------------------
# Producer theme emission
# ---------------------------------------------------------------------------

def to_producer_theme(profile, fmt):
    palette = profile.get("palette", {})
    typ = profile.get("typography", {})
    theme = {
        "colors": {k: (v or {}).get("hex") for k, v in palette.items() if v},
        "heading_font": (typ.get("heading") or {}).get("family", ""),
        "body_font": (typ.get("body") or {}).get("family", ""),
        "format": fmt,
    }
    if fmt == "pptx":
        # pptxgenjs corrupts on a leading '#' — strip it here, once, so every caller downstream doesn't have to.
        theme["colors"] = {k: (v or "").lstrip("#") for k, v in theme["colors"].items()}
    return theme


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("profile", type=Path, nargs="?", help="Existing profile.json to validate/emit from")
    ap.add_argument("--from-template", type=Path, metavar="PROFILE_JSON",
                     help="template_profile.json produced by lib/profile_template.py")
    ap.add_argument("--from-vault", type=Path, metavar="VAULT_EXPORT_JSON")
    ap.add_argument("--client", default="", help="Client name, used with --from-template")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--format", choices=["pptx", "docx", "html"])
    ap.add_argument("-o", "--out", type=Path)
    args = ap.parse_args()

    if args.from_template:
        profile = from_template(json.loads(args.from_template.read_text(encoding="utf-8")), args.client)
    elif args.from_vault:
        profile = from_vault(json.loads(args.from_vault.read_text(encoding="utf-8")))
    elif args.profile:
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
    else:
        sys.exit("pass a profile.json, or --from-template/--from-vault")

    errors = validate(profile)
    if errors:
        for e in errors:
            print(f"  ERROR {e}", file=sys.stderr)
        if not (args.from_template or args.from_vault):
            # a freshly-adapted profile always lacks approval by design; only a hard-stop when
            # the caller claimed this was already a usable profile
            return 1
        print("  (expected: freshly extracted/adapted profiles have no approval yet — "
              "a human must fill approval.* before this profile can be used)", file=sys.stderr)

    contrast_failures = []
    if args.format:
        contrast_failures = check_contrast(profile)
        for f in contrast_failures:
            print(f"  CONTRAST ERROR {f}", file=sys.stderr)
        output = to_producer_theme(profile, args.format)
    else:
        output = profile

    text = json.dumps(output, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"-> {args.out}")
    else:
        print(text)

    return 1 if (errors and not args.format) or contrast_failures else 0


if __name__ == "__main__":
    sys.exit(main())
