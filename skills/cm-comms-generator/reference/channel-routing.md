# Channel Routing

Stage 3b: which tool builds each channel's artifact, what has to be true first, and what
happens when the producer is out of reach.

The routing table itself lives in `../schemas/channel_registry.json` — it is data, read by
`route_channel.py`, `qa_comms.py` and `render_markdown.py` alike, so a limit or a status is
stated in exactly one place. This file is the reasoning behind it.

```bash
python skills/cm-comms-generator/scripts/route_channel.py --list
```

| Channel | Format | Producer | Status |
|---|---|---|---|
| `email` | `.docx` | `docx` skill | live |
| `article` | `.docx` | `docx` skill | live |
| `briefing_deck` | `.pptx` | `pptx` skill | live |
| `newsletter` | brand-applied `.html` | `render_comms_html.py` (local) | live |
| `banner` | brand-applied `.html` | `render_comms_html.py` (local) | live |
| `edm` | brand-applied, email-safe `.html` | `render_comms_html.py` (local) | live |
| `short_form_video` | scene outline + VO script | ElevenLabs MCP | planned, v0.3 |
| `explainer_video` | scene outline + screen direction | ElevenLabs MCP (narration only) | planned, v0.3 |

**"live" means an automated build chain exists, not that it is guaranteed reachable this
run.** `docx`/`pptx` depend on a local npm package, an ordinary precondition
`route_channel.py` checks at run time — a missing package downgrades the outcome to the
honest handoff rather than a false READY. `newsletter`/`banner`/`edm` run entirely locally
(no MCP connector, no npm package) through `render_comms_html.py`, so the only thing that can
downgrade them is `brand_approved` being unmet or QA itself failing. Canva remains available
as an alternative producer for `banner`/`newsletter` when a client specifically wants a Canva
asset or has an approved Canva Brand Template — see that lane below.
`short_form_video`/`explainer_video` are the only channels genuinely `planned`: no automated
build chain exists for either yet.

## The gate

**Nothing is produced until QA passes.** `route_channel.py` runs `qa_comms.audit()` itself
rather than trusting that someone ran it earlier, and refuses to emit a route while a hard
failure stands.

This is not ceremony. Production is where a comm becomes expensive and externally visible —
a Canva design in the client's account, a document that gets forwarded. The plan is where
defects are cheap. Fix the plan, re-route.

## Three outcomes, and the exit code tells them apart

| Exit | Outcome | Meaning |
|---|---|---|
| 0 | `route` | Preconditions met. The brief prints runnable commands. |
| 0 | `handoff_only` | The producer is unreachable. The handoff artifact **is** the deliverable, and a human finishes the job. **This is a successful run.** |
| 1 | blocked | QA failed, or a hard precondition is unmet. No route is emitted. |

The middle case matters. A blocked connector is not a broken run — a Canva brief or a video
spec is a real, complete piece of work that a designer or producer can act on. Reporting it
as a failure would train people to ignore the exit code.

## Preconditions

`brand_approved` is the only **hard** one: without a named human approving the brand
profile, every producer refuses, because that is the mechanical form of the
never-build-a-lookalike rule. Connector reachability is deliberately *not* hard — the
handoff still ships.

`node_docx_available` is checked rather than assumed. The `docx` skill's own SKILL.md says
the package is preinstalled; on at least one environment it is not, and the check reports
`npm install -g docx` instead of failing three steps later with a stack trace.

`route_channel.py` cannot introspect its own session's MCP tool list from inside a Python
process. Pass `--available-servers Canva` when you can see the connector; absent that, it
reports reachability as unknown rather than guessing, because a wrong guess wastes an
external call. This only matters for the Canva alternative route — `local:render_comms_html`
needs no connector, so it never depends on `--available-servers`.

## The lanes

### email, article → `.docx`

```bash
python skills/cm-comms-generator/scripts/build_docx.py <plan> --brand <brand> -o <run>
NODE_PATH="$(npm root -g)" node <run>/build.js
python skills/cm-comms-generator/scripts/verify_docx.py <run>/draft.docx --plan <plan> --brief <brief>
```

`build_docx.py` emits a Node script rather than assembling OOXML, so the build is
inspectable before it runs and the `docx` skill's footguns are encoded once: dual DXA table
widths, `ShadingType.CLEAR` (SOLID renders black), bullets from a `numbering` config rather
than a literal `•`, and separate `Paragraph`s instead of `\n`.

**Verify the artifact, not just the plan.** Between QA and the document sits a producer that
can silently drop content. `verify_docx.py` checks every block's text survived and — most
importantly — that every `[GAP]` is **still visible**. A gap lost in production is the worst
possible failure, because the draft then reads as finished when it is not.

Where LibreOffice works, also render and look: `soffice --convert-to pdf` then rasterise the
pages. That path is unavailable in some environments (it is broken in this one, for plain
text as much as for `.docx`), which is exactly why the text-level check exists.

A client `.dotx` letterhead cannot be used by this route — docx-js cannot open an existing
file. When `channel_specs.docx.dotx_path` is set, build on it through the `docx` skill's
edit path (unzip → edit `word/document.xml` → zip) instead.

### briefing_deck → `.pptx`

With a client `.potx`, the plan is validated against the real template before anything is
assembled:

```bash
python skills/cm-proposal-generator/scripts/profile_template.py <client.potx> -o <run>/template_profile.json
python skills/cm-proposal-generator/scripts/build_deck.py <plan> <run>/template_profile.json -o <run>/build_manifest.json
```

Then the `pptx` skill's **template** workflow: unzip → edit `ppt/slides/slideN.xml` → rezip.
Never `pptxgenjs` on a client template — a visually similar deck is not an approved-template
deck, and someone notices.

Without a `.potx`:

```bash
python skills/cm-comms-generator/scripts/apply_brand.py <brand> -o <run>/deck_theme.json
python skills/cm-comms-generator/scripts/build_pptx.py <plan> --theme <run>/deck_theme.json -o <run>
NODE_PATH="$(npm root -g)" node <run>/build_deck.js
python /root/.claude/skills/synced/pptx/scripts/office/validate.py <run>/deck.pptx
```

`build_pptx.py` emits a pptxgenjs script — inspectable before it runs, with the `pptx` skill's
footguns encoded once (layout set before any slide, hex with no `#`, a fresh options object per
call, bullets via `bullet: true`, notes through `addNotes`). It refuses outright when the brand
names a `.potx`, because from-scratch is the wrong route then. A slide with no speaker notes gets
a visible placeholder note rather than shipping silently bare.

That result carries the client's colours and is **not** their approved template:
`design_provenance` records `generated-unapproved` and the handover says so.

Speaker notes on every content slide are a hard requirement either way. A cascade deck
without notes gets improvised, and the improvisation is what the audience remembers.

### newsletter, banner, edm → local HTML render

```bash
python skills/cm-comms-generator/scripts/render_comms_html.py <plan> \
    --brief <brief> --brand <brand> -o <run>/comms_<channel>.html
```

Renders a self-contained, brand-applied `.html` file directly from the plan and brand
profile — no external connector, no npm package, nothing pending on a client's Canva Brand
Template before anyone can even open it. It calls `qa_comms.audit()` itself before writing
anything (the same gate `route_channel.py` runs — belt and braces, since this script can also
be invoked directly), re-checks the accessibility contrast pairs `apply_brand.py --format
html` computed, and refuses to write a file if either check fails. A block flagged `gap: true`
renders as a visible flagged placeholder, same convention as every other channel; a `cta`
block with no URL embedded in its text renders as plain emphasis with a build-time warning
rather than a broken button, since the schema carries no structured URL field for a `cta`.

**`edm` is email-safe HTML, `banner`/`newsletter` are not.** `edm` renders as a table-based
layout with every style inlined and MSO conditional comments for Outlook — mail clients do
not reliably support `<style>` blocks, CSS classes or `var()`. `banner` and `newsletter` are
ordinary web pages (an intranet strip, a scannable page) and use `var(--token)` CSS resolved
from the same brand theme.

No client design ships with any of these three, so all three carry
`design_provenance: "generated-unapproved"`. `qa_comms.py` warns on it and the handover says
the design needs client sign-off before publish — the copy has passed QA; the layout has been
approved by nobody.

**Canva remains available as an alternative** for `banner`/`newsletter` when a client
specifically wants a Canva asset or has an approved Canva Brand Template:

```bash
python skills/cm-comms-generator/scripts/canva_brief.py <plan> --brand <brand> -o <run>/canva_brief.json
```

Then `generate-design` with the brief's prompt and copy fields, and `export-design` to
retrieve the asset. Which Canva route runs is decided by the brand profile:

| `channel_specs.<channel>.canva_brand_template_id` | Route | `design_provenance` |
|---|---|---|
| set (a `BTM…` id) | `get-brand-template-dataset` → `autofill-design` → `export-design` | `client-approved-template` |
| absent | `generate-design` → `create-design-from-candidate` → `export-design` | `generated-unapproved` |

`canva_brief.py` emits the matching `route` block either way. A Brand Template is not a file
you upload — it is built in Canva and referenced by id, recorded in the brand profile once
per client, exactly as `potx_path` works for decks. Listing or autofilling one requires a
**Canva paid plan** (Pro, Teams or Enterprise); on a free plan `search-brand-templates`
refuses and the generate route is the only one available. On this route specifically, the
asset exports as a raster image: on most intranet tenancies the text is baked in and invisible
to screen readers, so **alt text is mandatory, not optional**, and must carry the message
rather than describe the picture. The local HTML render has no such gap — its text is real
DOM text.

### short_form_video, explainer_video → reserved

```bash
python skills/cm-comms-generator/scripts/video_spec.py <plan> --brand <brand> -o <run>/video_spec.json
```

Writes the scene table, VO script with per-scene timing, on-screen text, a WebVTT caption
file, and direction. Both lanes are declared with an intended producer and a `blocked_by`
string naming exactly what is missing:

- **`short_form_video` → ElevenLabs.** Installed on the account but disabled in this chat,
  and the tools it exposes are voice-*agent* management (`create_agent`, `get_agent_link`),
  not TTS or video rendering. Enable it and re-check the tool surface before wiring.
- **`explainer_video` → ElevenLabs, for narration only.** Same connector and same blocker as
  above. This lane is only ever partly served: scene assembly and any presenter avatar remain a
  human production step. No avatar-video connector exists in the directory — Synthesia has none,
  and the nearest neighbours (HyperFrames by HeyGen, Tella) are different vendors, not installed.

Until then the spec and captions are the deliverable, written to be handed to a person or an
app without further translation. When a connector arrives, the same file is the adapter's
input.

The runtime estimate earns its place here: a script written for a 45-second slot that
actually reads at 90 seconds is the commonest defect in a video brief, and it is invisible
until someone records it.

## Coverage mode: full comms and signposts

Not every channel is a full communication, and the registry says which is which via
`coverage_mode`.

A **full** comm (`email`, `article`, `briefing_deck`, `newsletter`, `edm`, `explainer_video`)
must carry every must-land message in scope for its audiences, name its sender, and give a
help route.

A **signpost** (`banner`, `short_form_video`) carries one message and points at where the
detail lives. Holding it to full coverage would force content onto it that the channel
library explicitly says must not be there. Instead QA requires that a signpost carries at
least one in-scope must-land message and has somewhere to send the reader — a `cta` or
`placement-spec` part. A signpost with neither is decoration.

`requires_signature` works the same way: a written comm without a named sender reads as
unattributed, but a banner carries no signature by nature and a video's messenger is the
on-screen presenter, so demanding the name in the script would force an unnatural line into
the read.

## Adding a channel

1. Add an entry to `channel_registry.json`: `format`, `producer`, `status`, `blocked_by`,
   `preconditions`, `part_kinds`, `default_specs`, `coverage_mode`, `requires_signature`.
2. Add its `part_kind` values to `comms_plan.schema.json` and a spec block to
   `brand_profile.schema.json`.
3. Add a renderer to `render_markdown.py` and an entry to `channel-library.md`.
4. If the producer is new, add a `commands_for` branch in `route_channel.py`.

A channel whose producer does not exist yet is a normal, supported state. Declare it with
`status: "planned"` and an honest `blocked_by` rather than leaving a TODO in code.
