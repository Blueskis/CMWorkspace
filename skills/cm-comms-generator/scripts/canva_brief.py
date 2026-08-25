#!/usr/bin/env python3
"""Turn a comms plan into a Canva design brief (Stage 3b, newsletter and banner).

    python canva_brief.py comms_plan.json --brand brand_profile.json \\
        -o comms/<run>/canva_brief.json

Writes the brief the Canva lane consumes: a generation prompt, the copy for each named
field, the canvas dimensions, the palette and typography to hold to, and the alt text.

The brief is a real deliverable, not a stub. When the Canva connector is unavailable — and
it frequently is, since it needs authorizing — the brief is what ships, and a designer
builds from it by hand. When the connector IS available, the same file is the input to
`generate-design`. Neither path needs the other to have run.

A NOTE ON PROVENANCE, because it matters here more than anywhere else in this skill:
`generate-design` means Canva invents the layout. The copy in this brief has passed QA;
the DESIGN has not been approved by anyone. That is why the brief stamps
`design_provenance: "generated-unapproved"` and carries an explicit sign-off warning — a
generated design must not go out under a client's name until they have seen it. Where the
client has an approved Canva Brand Template, `create-design-from-brand-template` with
`get-brand-template-dataset` is the better route and this brief's `copy_fields` map onto
that dataset directly.

STATUS (v0.2): this writes the brief; it does not call Canva. Keeping the external call
out of a script means a failed run leaves an inspectable file rather than a half-created
design in someone's Canva account.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_markdown import ordered_parts, body_of  # noqa: E402
from qa_comms import registry_specs  # noqa: E402

CANVA_CHANNELS = ("newsletter", "banner")


def plain(part):
    """The part's copy as one flat string — Canva fields take text, not Markdown."""
    return " ".join(body_of(part).replace("\n", " ").split())


def build(plan, brand, channel):
    specs = dict(registry_specs(channel))
    specs.update((brand.get("channel_specs") or {}).get(channel, {}))

    palette = {k: v.get("hex") for k, v in (brand.get("palette") or {}).items()
               if isinstance(v, dict) and v.get("hex")}
    typo = brand.get("typography") or {}

    copy_fields, sections, over = {}, [], []
    for _, part in ordered_parts(plan):
        kind = part.get("part_kind") or "content"
        text = plain(part)
        gaps = [b.get("gap_note") for b in part["blocks"] if b.get("gap")]

        limit_key = {"headline": "headline_max_chars", "subhead": "body_max_chars",
                     "standfirst": "section_max_chars", "cta": "cta_max_chars",
                     "section-heading": "section_max_chars"}.get(kind)
        limit = specs.get(limit_key) if limit_key else None
        if limit and len(text) > limit:
            over.append(f"{part['slide_id']} ({kind}): {len(text)} chars over the {limit} limit")

        entry = {"part_kind": kind, "title": part.get("title", ""), "text": text,
                 "char_count": len(text), "char_limit": limit,
                 "sources": sorted({s for b in part["blocks"] for s in b.get("sources", [])})}
        if gaps:
            entry["open_gaps"] = gaps
        copy_fields[part["slide_id"]] = entry
        sections.append(part["slide_id"])

    if channel == "banner":
        canvas = {"width_px": specs.get("image_width_px"),
                  "height_px": specs.get("image_height_px"),
                  "safe_area_px": specs.get("safe_area_px")}
        shape = ("A single wide banner image. All text inside the safe area — on most "
                 "intranet tenancies the text is baked into the image, so anything outside "
                 "it is clipped on narrow viewports.")
    else:
        canvas = {"width_px": specs.get("image_width_px"),
                  "max_sections": specs.get("max_sections")}
        shape = ("A vertical newsletter with a headline, a standfirst, and stacked sections "
                 "a reader skims. Each section stands alone — assume nobody reads to the end.")

    prompt_bits = [
        f"A {channel.replace('_', ' ')} for {plan.get('client', 'the client')}"
        f" about: {plan.get('engagement_title', '')}.",
        shape,
        "Use ONLY these brand colours: "
        + ", ".join(f"{k} {v}" for k, v in sorted(palette.items())) + ".",
        f"Headings in {(typo.get('heading') or {}).get('family', 'the brand heading face')}; "
        f"body in {(typo.get('body') or {}).get('family', 'the brand body face')}.",
        "Do not invent copy, statistics, names or dates — every word comes from copy_fields.",
        "No stock photography of people unless the brief supplies an approved asset.",
    ]
    for rule in (brand.get("palette_rules") or []):
        prompt_bits.append(rule)

    brief = {
        "generated": date.today().isoformat(),
        "run_id": plan.get("run_id"),
        "channel": channel,
        "client": plan.get("client"),
        "title": plan.get("engagement_title"),
        "design_provenance": "generated-unapproved",
        "sign_off_required": (
            "Canva generates this layout — the DESIGN is not client-approved. The copy has "
            "passed QA; the design must be signed off by the client before publish."
        ),
        "canvas": canvas,
        "prompt": " ".join(prompt_bits),
        "section_order": sections,
        "copy_fields": copy_fields,
        "palette": palette,
        "typography": {
            "heading": (typo.get("heading") or {}).get("family"),
            "body": (typo.get("body") or {}).get("family"),
            "min_size_pt": typo.get("min_size_pt"),
        },
        "accessibility": {
            **(brand.get("accessibility") or {}),
            "alt_text": _alt_text(plan, copy_fields),
            "note": ("Text baked into an image is invisible to screen readers. The alt text "
                     "must carry the message, not describe the picture."),
        },
        "logo": brand.get("logo") or {},
        "over_limit": over,
        "mcp_route": {
            "preferred": "create-design-from-brand-template + get-brand-template-dataset "
                         "(use when the client has an approved Canva Brand Template — the "
                         "copy_fields map onto the dataset)",
            "current": "generate-design, then export-design",
        },
    }
    return brief


def _alt_text(plan, copy_fields):
    head = next((v["text"] for v in copy_fields.values()
                 if v["part_kind"] in ("headline", "subject")), "")
    cta = next((v["text"] for v in copy_fields.values() if v["part_kind"] == "cta"), "")
    bits = [b for b in (head, cta) if b]
    return " ".join(bits) or plan.get("engagement_title", "")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", type=Path)
    ap.add_argument("--brand", type=Path, required=True)
    ap.add_argument("-o", "--out", type=Path, default=Path("canva_brief.json"))
    args = ap.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    brand = json.loads(args.brand.read_text(encoding="utf-8"))

    channel = plan.get("channel")
    if channel not in CANVA_CHANNELS:
        sys.exit(f"canva_brief.py handles {' and '.join(CANVA_CHANNELS)}; got '{channel}'")
    if not (brand.get("approval") or {}).get("approved_by"):
        sys.exit("brand profile has no recorded approval — stop and ask before producing")

    brief = build(plan, brand, channel)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(brief, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    print(f"Canva brief -> {args.out}  [{channel}]")
    print(f"  {len(brief['copy_fields'])} copy field(s), canvas "
          f"{brief['canvas'].get('width_px')}x{brief['canvas'].get('height_px', '—')}")
    gaps = sum(1 for v in brief["copy_fields"].values() if v.get("open_gaps"))
    if gaps:
        print(f"  {gaps} field(s) carry an open [GAP] — resolve before the design is built")
    for o in brief["over_limit"]:
        print(f"  WARNING over limit: {o}", file=sys.stderr)
    print("  design_provenance: generated-unapproved — the DESIGN needs client sign-off, "
          "even though the copy has passed QA.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
