---
name: cm-comms-generator-v0.2
description: Drafts a change communication for a requested channel and routes it to the tool that builds it — email and articles as .docx via the docx skill, briefing decks as .pptx via the pptx skill, newsletters and banners as Canva designs, short-form and explainer videos as production specs. Built from a structured read of the change and the client's approved brand, populated from a curated knowledge bank of past comms collateral, tone guidance and standing boilerplate. Runs a four-stage pipeline — interrogate the change into a brief with stable audience and message IDs, capture the client's approved theme and voice as a brand profile, plan and draft the requested channel then route it to its producer, and QA it for message coverage, audience coverage, provenance and brand fidelity before anything is produced. Use whenever a change practitioner wants to write, draft, build or plan a communication about a change to people, processes or technology — phrases like "draft a go-live email", "write an article about this change", "we need a banner for the intranet", "build a manager cascade pack", "put together a newsletter item", "outline an explainer video", "draft the announcement". Do NOT use for writing a bid or responding to an RFP — that is cm-proposal-generator — and do NOT use for diagnosing whether a change initiative is healthy; this skill writes comms, it does not analyse programmes.
---

# CM Comms Generator

Turns a described change — what's changing, who it affects, when, and what they have to do —
into a channel-appropriate communication draft, written on the client's approved brand and
from the firm's own bank of past collateral rather than invented from a blank page.

**The point of this skill is coverage and traceability, not prose.** Anyone can write a
go-live email. What makes this useful to a practitioner is that (a) every sentence traces back
to a knowledge-bank entry, a field of the change brief, or an explicit `[GAP]`, and (b) every
must-land message and every targeted audience is provably addressed. Both are checked in
Stage 4, and neither is optional.

## MVP scope (read this before promising anything)

This is v0.2. What it does and does not do:

| In scope | Out of scope (v0.2) |
|---|---|
| One change, one channel per run | A sequenced multi-channel campaign plan |
| The seven channels in `reference/channel-library.md` | Town halls, podcasts, print, physical signage |
| A Markdown draft for every channel | Sending, scheduling or publishing anything |
| `.docx` for email and articles, `.pptx` for briefing decks | A rendered video, or a built banner image |
| A Canva design brief, and the design itself when the connector is authorized | A design the client has approved |
| A video production spec with timing and captions | A produced video — both video lanes await a connector |
| Message, audience, provenance and brand QA, gating production | Judging whether the tone lands |
| A draft for the practitioner to edit | An approved, sendable communication |

Always hand the output over as **a first draft for the practitioner to review**, never as a
sendable comm. Say so explicitly when you deliver it, and name the approver from the brief.

## Provenance: three states, not two

`cm-proposal-generator` has a two-state rule — every block carries knowledge-bank sources or a
`[GAP]`, with no third state. **That rule does not transfer as-is, and this is the single thing
most likely to be mistaken for a bug.**

A comms draft is genuinely new writing about a new change, so most body copy legitimately has
no knowledge-bank ancestor. Here there are three valid states:

| State | Meaning |
|---|---|
| `"sources": ["cc-go-live-email-example"]` | Reused from past collateral — a proven structure, standing boilerplate, house tone |
| `"sources": ["brief:audiences.A1.required_action"]` | Traced to a field of the change brief — the practitioner asserted this fact |
| `"gap": true` + `gap_note` | Neither covers it; renders visibly, never filled with plausible text |

Anything else fails Stage 4. This keeps the property that matters — **no sentence in the draft
is invented** — while admitting that the brief, not the bank, is the source of most
change-specific content. A `brief:` reference must resolve to a real field; a dangling one is a
failure, or the third state becomes a loophole.

## Pipeline

```
  Stage 1   INTAKE   change inputs ──▶ change_brief.json
  Stage 2   BRAND    approved template / brand guide ──▶ brand_profile.json
  Stage 3a  PLAN     brief + brand + kb_index ──▶ comms_plan.json ─▶ draft.md
  Stage 4   QA       coverage + provenance + brand + channel specs ──▶ qa_report.md
  Stage 3b  ROUTE    comms_plan + registry ──▶ production_brief.md ─▶ the artifact
```

Stage 4 is numbered after 3a and before 3b on purpose: **QA gates production.** The Markdown
draft is what a practitioner reviews and what QA audits; nothing is built until it passes.

Stages 1 and 2 produce **reusable assets with different lifecycles**, and that is the point:
the brief is authored once per change, the brand profile once per client. Only Stages 3 and 4
repeat per channel.

**Never re-derive the brief for a second channel.** If the change itself has moved, edit
`change_brief.json` in place and re-run the affected channels. Two channels disagreeing about a
go-live date is exactly the failure the shared brief exists to prevent.

### Run workspace

Create `comms/<client-slug>/` in the user's current working directory:

```
comms/northwind/
├── inputs/                    # source material, and the client's template file
├── change_brief.json          # Stage 1 — authored ONCE, outlives every run below
├── brand_profile.json         # Stage 2 — per client, reused across changes
├── kb_index.json
└── runs/
    ├── email-20260817/
    │   ├── comms_plan.json
    │   ├── draft.md
    │   └── qa_report.md
    └── briefing_deck-20260819/
        ├── comms_plan.json
        ├── draft.md
        ├── qa_report.md
        ├── production_brief.md   # Stage 3b — the route
        ├── deck_theme.json
        └── deck.pptx
```

## Stage 1 — Intake

Interrogate the change into `change_brief.json`, against `schemas/change_brief.schema.json`.
`reference/change-intake.md` carries the question set, the order to ask in, and the questions
practitioners habitually skip.

Parse whatever the practitioner has with the appropriate skill — `docx` for briefing notes,
`xlsx` for impact assessments, `pdf` for programme packs, plain read for text.

**Ask about the audience before the message.** Practitioners arrive with the programme's
framing and the comm has to be written in the reader's. Starting with the audience forces that
translation while it is still cheap.

**Every audience, message and milestone gets a stable ID** — `A1`, `M1`, `T1`. These are the
spine of every run: Stage 3 maps content to them and Stage 4 proves none went unaddressed.
Never renumber; add `M7` rather than recycling `M3`.

Never invent an audience, a date, or a required action. Where the practitioner is unsure it
goes in `open_questions` and surfaces as a visible `[GAP]`. A draft that flags a date as
unconfirmed is worth more than one that confidently states the wrong date.

Report back a short read of the brief — change and type, segments and impact levels, how many
must-land messages, confirmed and indicative dates, sender, help route, open questions. This is
a transparency checkpoint, not an approval gate; continue into Stage 2 unless redirected.

## Stage 2 — Brand profile

Capture the client's approved theme and voice as `brand_profile.json`, against
`schemas/brand_profile.schema.json`. Full guidance in `reference/brand-profile-guide.md`.

**Hand-authoring from the client's brand guidelines is the primary path** and the only route
that produces a complete profile. **Extraction from a supplied `.potx` is the backup**, and
recovers less than people assume: `profile_template.py` reads layouts, placeholders, geometry
and theme *fonts*, but does not parse `a:clrScheme` — colours are a manual `theme1.xml` read —
and it rejects `.docx`/`.dotx` outright. Tone of voice is hand-written on either route.

**Never build a brand lookalike.** No approved template and no brand guide means stop and ask,
not approximate from the client's website. Comms go out to a whole employee base under the
client's name. The schema enforces what it can: `approval` is required, `source` has no
`inferred` value, and both `apply_brand.py` and `qa_comms.py` exit non-zero without a named
approver.

Store finished profiles in `proposal-assets/brand-profiles/<client>.brand_profile.json` and
copy one into the run.

## Stage 3a — Plan and draft

**1. Select the channel** and read its entry in `reference/channel-library.md` — purpose,
anatomy, constraints, failure modes. Where the practitioner has not chosen, the table at the
end of that file maps impact × action × sensitivity to a recommended channel. Recommend once,
with the reason, then build what was asked for.

**2. Build the message architecture** — which of `M1…Mn` this channel carries, for which of
`A1…An`. Set `target_audience_ids` on the plan: coverage is computed against that subset, so a
single-audience email is not failed for omitting messages aimed elsewhere.

Note the channel's `coverage_mode` in `schemas/channel_registry.json`. A **full** comm must
carry every in-scope must-land message; a **signpost** (a banner, a 30-second clip) carries one
and points at where the detail lives. Do not stuff a signpost with the whole story to make
coverage look better — that is the failure, not the fix.

**3. Retrieve from the shared knowledge bank**, always with `--strict-section`:

```bash
python skills/cm-proposal-generator/scripts/index_kb.py proposal-assets/knowledge-bank \
    -o comms/<client>/kb_index.json

python skills/cm-proposal-generator/scripts/retrieve.py comms/<client>/kb_index.json \
    --section comms-collateral --tags email,technology,go-live --strict-section --top 5
```

The bank is shared with `cm-proposal-generator`. **The section is the isolation boundary and
`--strict-section` is what enforces it** — without the flag `--section` only adds +2 to the
score, so a comms entry can surface in a bid. Three sections are ours: `comms-collateral`,
`comms-tone`, `comms-boilerplate`.

**4. Write `comms_plan.json`** against `schemas/comms_plan.schema.json`. Adapt retrieved
content to this change — its system names, its dates, its audience's language. Adaptation is
expected; fabrication is not. Every block carries KB sources, a `brief:` reference, or an
explicit gap.

**5. Render the reviewable draft:**

```bash
python skills/cm-comms-generator/scripts/render_markdown.py comms/<run>/comms_plan.json \
    --brand comms/<client>/brand_profile.json -o comms/<run>/draft.md
```

This Markdown is what the practitioner reads and what Stage 4 audits. It is **not** the
deliverable — that comes out of Stage 3b.

## Stage 3b — Route to the producer

```bash
python skills/cm-comms-generator/scripts/route_channel.py comms/<run>/comms_plan.json \
    --brief comms/<client>/change_brief.json --brand comms/<client>/brand_profile.json \
    -o comms/<run>/production_brief.md
```

The router reads `schemas/channel_registry.json`, **re-runs QA itself**, checks the lane's
preconditions, and prints the exact commands for that channel. Full detail, including how to
add a channel, is in `reference/channel-routing.md`.

| Channel | Builds as | Producer | Status |
|---|---|---|---|
| `email`, `article` | `.docx` | `docx` skill | live |
| `briefing_deck` | `.pptx` | `pptx` skill | live |
| `newsletter`, `banner` | Canva design | Canva MCP | needs the connector authorized |
| `short_form_video` | scene spec + captions | ElevenLabs MCP | planned, v0.3 |
| `explainer_video` | scene spec + captions | Synthesia MCP | planned, v0.3 |

**Nothing is produced until QA passes.** The router exits non-zero and emits no route while a
hard failure stands. Production is where a comm becomes expensive and externally visible; the
plan is where defects are cheap.

**An unreachable producer is not a failed run.** When Canva is unauthorized or a video lane has
no connector, the router exits 0 and the handoff artifact — a Canva brief, a video spec with
captions — *is* the deliverable. A designer or producer picks it up. Say that plainly at
handover rather than reporting it as a failure.

### email and article → `.docx`

```bash
python skills/cm-comms-generator/scripts/build_docx.py <plan> --brand <brand> -o <run>
NODE_PATH="$(npm root -g)" node <run>/build.js
python skills/cm-comms-generator/scripts/verify_docx.py <run>/draft.docx \
    --plan <plan> --brief <brief>
```

`build_docx.py` emits a Node script rather than assembling OOXML, so the build is inspectable
and the `docx` skill's footguns are encoded once. **Always run `verify_docx.py`**: it checks the
plan's content survived into the artifact and, above all, that every `[GAP]` is still visible.
A gap lost in production makes an incomplete draft read as finished.

Where LibreOffice works, also render and look at the pages. That path is unavailable in some
environments, which is why the text-level check exists.

### briefing_deck → `.pptx`

With a client `.potx`, validate the plan against the real template first — `profile_template.py`
then `build_deck.py`, both reused unchanged from `cm-proposal-generator` — then build through
the `pptx` skill's **template** workflow (unzip → edit `ppt/slides/slideN.xml` → rezip, never
`pptxgenjs`).

Without a `.potx`, `apply_brand.py` emits `deck_theme.json` and `build_pptx.py` generates a
pptxgenjs build script from the plan. That carries the client's colours and is **not** their
approved template: `design_provenance` records `generated-unapproved` and the handover says so.
`build_pptx.py` refuses when the brand names a `.potx` — from-scratch is the wrong route then.

### newsletter and banner → Canva

```bash
python skills/cm-comms-generator/scripts/canva_brief.py <plan> --brand <brand> \
    -o <run>/canva_brief.json
```

Then `generate-design` and `export-design` when the connector is available.

**This lane generates rather than autofills, and that has a cost.** Canva invents the layout, so
the copy has passed QA but the *design* has been approved by nobody. Stamp
`design_provenance: "generated-unapproved"` and say at handover that the design needs client
sign-off before publish. Where the client has an approved Canva Brand Template,
`create-design-from-brand-template` is the better route and a one-line registry change.

### short_form_video and explainer_video → reserved

```bash
python skills/cm-comms-generator/scripts/video_spec.py <plan> --brand <brand> \
    -o <run>/video_spec.json
```

Writes the scene table, VO script with timing, on-screen text and a WebVTT caption file. Neither
lane has a reachable producer: ElevenLabs is installed but disabled in chat and currently
exposes voice-*agent* tools rather than TTS or rendering; no Synthesia connector exists in the
Claude connector directory at all. The router reports each `blocked_by` verbatim. The spec and
captions are the deliverable until a connector arrives.

## Stage 4 — QA

```bash
python skills/cm-comms-generator/scripts/qa_comms.py \
    comms/<client>/change_brief.json comms/<run>/comms_plan.json \
    --brand comms/<client>/brand_profile.json -o comms/<run>/qa_report.md
```

Seven checks. The first five exit non-zero; the last two report.

Per-channel limits and coverage rules come from `schemas/channel_registry.json`,
so a default lives in one place and the router, the renderer and QA all agree.

1. **Message coverage** — for a **full** comm, every must-land message in scope for this run's
   audiences is carried by a part. For a **signpost**, at least one is, and the draft must have
   somewhere to send the reader. Messages aimed at other segments are reported out of scope,
   not failed.
2. **Audience coverage** — every targeted audience is addressed, and its required action
   appears in an action part or the action section. A comm that names an audience but never
   tells it what to do is the defining failure of change comms.
3. **Provenance** — sources or an explicit gap on every block, and every `brief:` reference
   resolves.
4. **Brand approval** — a named human approved the profile.
5. **Channel specs** — stated character, slide and runtime limits; banned words and prohibited
   terms; market-sensitive messages kept off open channels; indicative dates hedged in the
   copy. A limit the brand profile *states* fails; a channel-library default only warns.
6. **Design provenance** — a design a tool invented (a generated Canva design, a from-scratch
   deck) is flagged as needing client sign-off, even when the copy passes. The copy and the
   design are approved separately.
7. **The six questions** — what's changing, why, who's affected, when, what do I do, where do I
   get help. `help` is the one that goes missing most.

Only once this passes does Stage 3b hand over a production route.

Then deliver: the artifact, the draft, the QA report, and a plain statement of what's still
open — the `[GAP]`s, any uncovered message, whether the *design* as well as the copy has been
approved, the approver's name and whether they have signed off, and the reminder that this is a
draft for review, not an approved send.

## Notes

- **The knowledge bank is the product.** A thin bank produces drafts full of `[GAP]`s, and that
  is correct behaviour — it reports what the firm hasn't written down yet. Don't paper over it
  with generated filler; point the practitioner at the folder READMEs to add entries instead.
- **A `[GAP]` in a comm is more urgent than one in a bid.** A bid gap is a missing credential;
  a comms gap is usually a question 2,000 people are about to ask that nobody can answer. Lead
  the handover with them.
- **Comms collateral is more sensitive than bid collateral, not less.** A real all-staff email
  about a redundancy-adjacent change should be `anonymised` or `internal-only` in the bank.
- **Embargoes and send windows are real.** Surface `governance.embargo` early and mention it at
  handover.
- **Copy and design are approved separately.** A run can pass every QA check and still carry a
  design nobody has signed off — that is what `design_provenance` records. Never let "QA passed"
  be heard as "the client has approved this."
- **A blocked lane is not a failed run.** When Canva is unauthorized or a video connector is
  missing, the handoff artifact is real work a person can act on. Hand it over as a deliverable
  and say what would unblock the rest.
- If asked for a channel outside the seven — a town hall script, a podcast, print — say what the
  library covers and offer the nearest fit rather than improvising an eighth channel silently.
- **Adding a channel is a registry edit plus a producer**, not a change in three scripts. A
  channel whose producer does not exist yet is a supported state: declare it `planned` with an
  honest `blocked_by`. See `reference/channel-routing.md`.
