---
name: cm-comms-generator-v0.1
description: Generates a change-communications pack from a practitioner's change brief and other client inputs, built against a routing table of communication channels (email, article, briefing deck, newsletter, banner, video) and populated from a curated knowledge bank of narrative, channel examples, tone-and-style rules, FAQs, and glossary terms. Runs a five-stage pipeline — interrogate the brief into audiences, messages, and timeline events, plan the audience-by-channel matrix, retrieve matching knowledge-bank content, route to each channel's producer, then QA for message coverage and provenance. Use whenever a CM practitioner wants to draft, plan, or produce change communications — an announcement, an all-staff email, a manager briefing, a newsletter item, a launch banner, a comms plan for a go-live — or when a practitioner arrives from the Change Comms Console handoff. Phrases like "draft comms for this change", "write the go-live announcement", "build a comms plan for this rollout", "I need an email and a briefing deck for managers". Do NOT use for writing an RFP response, a pitch, or a bid deck — that is `cm-proposal-generator`. Do NOT use for diagnosing or assessing an existing change initiative — this skill drafts communications, it does not analyse programmes.
---

# CM Comms Generator

Turns a change brief — who is affected, what is changing, why, when, and where to get
help — into a client-ready pack of change communications, drafted per audience and
routed to each channel's actual producer, written from the firm's own knowledge bank
rather than invented from scratch.

**The point of this skill is provenance and coverage, not prose.** Anyone can write an
announcement email. What makes this useful to a practitioner is that (a) every content
block traces back to a message the brief actually contains, a knowledge-bank entry, or an
explicit `[GAP]` flag, and (b) every mandatory message reaches every audience it applies
to through at least one channel. Both are checked at Stage 5, and neither is optional.

## MVP scope (read this before promising anything)

This is v0.1. What it does and does not do:

| In scope | Out of scope (v0.1) |
|---|---|
| One change, one org, one run | Multi-change programmes sharing a single comms calendar |
| Audience segmentation from the brief, not one draft broadcast to everyone | Dynamic/personalised comms generated per individual |
| Seven channels from `schemas/channel_registry.json` | Channels the registry doesn't carry — no free-form channel invention |
| Knowledge-bank retrieval by section + tag match (reused unchanged from `cm-proposal-generator`) | Semantic/embedding search over the bank |
| Email/article (`.docx`), briefing deck (`.pptx`), newsletter and banner via Canva | A CMS-published, scheduled, or sent communication — this drafts, it doesn't publish |
| Message-coverage and provenance QA, plus cross-channel date/figure consistency | Sentiment analysis, delivery tracking, read-receipt reporting |
| Narrated video **scripts** plus a `narration_spec.json` for both video channels | An actual rendered video file — no narration engine is wired in v0.1 (see Stage 4) |
| A draft pack for the practitioner to edit | A sent, published, or approved-for-distribution pack |

Always hand the output over as **a first draft for the practitioner to review**, never as
cleared-for-distribution communications. Say so explicitly when you deliver it.

## Pipeline

```
  Stage 1  INTAKE      brief + inputs                ──▶ change_brief.json
  Stage 2  PLAN        change_brief + registry        ──▶ comms_plan.json  (audience x channel matrix)
  Stage 3  DRAFT        kb_index + plan                ──▶ comms_plan.json  (content + sources)
  Stage 4  BUILD        comms_plan + producers          ──▶ .docx / .pptx / Canva designs / narration_spec.json
  Stage 5  QA           coverage + provenance + consistency ──▶ deliver
```

Each stage writes to the run workspace, so a run can be resumed, inspected, or re-run from
any stage without redoing the ones before it. Never skip straight from a brief to a draft —
the intermediate artifacts are what make the output auditable.

### Run workspace

Create `comms/<org-slug>-<YYYYMMDD>/` in the user's current working directory, matching
the `proposals/` convention `cm-proposal-generator` already uses:

```
comms/payroll-cadence-20260904/
├── inputs/              # copies of the brief, the console handoff, and any other inputs
├── change_brief.json    # Stage 1
├── comms_plan.json      # Stages 2-3, updated through Stage 4
├── build/                # .docx / .pptx / narration_spec.json outputs from Stage 4
└── qa_report.md         # Stage 5
```

### The A/M/T id spine

`cm-proposal-generator` hangs everything off requirement IDs (`R1`, `R2`…). Comms needs
three axes instead of one, because a comms pack has to answer "who", "what", and "when"
separately before it can answer "through which channel":

- **`A1..` audiences** — who, roughly how many, and what is genuinely different for them.
  Not a demographic segment for its own sake — an audience only earns its own ID if the
  change lands on it differently from every other audience.
- **`M1..` messages** — the six mandatory questions (what / who / why / when / action /
  help), plus what is explicitly **not** changing, plus open unknowns the audience will
  ask about whether or not the brief answers them.
- **`T1..` timeline events** — dates, each flagged `confirmed: true/false`. An unconfirmed
  date is not a reason to omit it — it's a reason to flag it, because the audience will ask
  regardless.

These IDs are the spine of the whole run: Stage 2 maps channels to audiences and messages,
Stage 3 attaches sources to every block, and Stage 5 checks none went uncovered.

### The two invariants (non-negotiable, mechanically enforced)

1. **Provenance.** Every content block in `comms_plan.json` carries a non-empty `sources`
   array (message IDs and/or knowledge-bank entry IDs) **or** `gap: true` with a
   `gap_note`. No third state. Identical rule to `cm-proposal-generator`'s
   `qa_deck.py:40` — a block with neither is a hard Stage 5 failure, and the practitioner
   has no way to tell an invented claim from a sourced one once it's in a draft.
2. **Coverage.** Every mandatory message ID reaches every audience ID it applies to,
   through at least one selected channel. An uncovered `M` x `A` pair fails the run. This
   is the check that makes the audience-segmentation feature real rather than cosmetic —
   Payroll's 2,400 employees and its line managers are different audiences precisely
   because a channel that reaches one doesn't automatically reach the other.

Both are checked mechanically in Stage 5, not by eye, and neither is a warning you can
talk yourself past.

## Stage 1 — Intake

Ask for, or locate, the inputs: the change brief itself (often prose, often the Change
Comms Console handoff), plus whatever else exists — a project charter, a stakeholder
list, prior communications on related changes, named sender/leadership guidance.

Parse each input with the appropriate skill — `docx` for Word, `pdf` for PDFs, plain read
for prose or the console's handoff text. Then extract into `change_brief.json` against
`schemas/change_brief.schema.json`. See `reference/brief-interrogation.md` for what
practitioners habitually omit and how to interrogate prose into the A/M/T spine without
inventing anything the brief doesn't actually say.

**Every audience, message, and timeline event gets a stable ID.** Assign them in the order
`reference/brief-interrogation.md` describes — audiences first, since messages and
channel selection both key off them.

Report back a short read of the brief before moving on: the org, the change in one
sentence, how many audiences and messages extracted, the confirmed vs. unconfirmed
timeline events, and anything the console handoff or prose brief left unanswered. This is
a transparency checkpoint, not a request for approval — continue straight into Stage 2
unless the practitioner redirects.

### Confidence and gaps

Never invent an audience, a message, or a date the brief doesn't support, and never soften
one it does state. Where the brief is genuinely silent on something a practitioner usually
supplies — most often **where to get help**, the single most-omitted field — that becomes
an `open_questions` entry, not a plausible-sounding placeholder. It flows through to a
visible `[GAP]` in the plan and, if still unanswered, in the delivered pack.

## Stage 2 — Plan the audience x channel matrix

Read `schemas/channel_registry.json` — the single source of truth for what a channel is,
what produces it, and its hard constraints. `reference/channel-library.md` carries the
same information in prose, with purpose, when-to-use, and QA rules per channel.

Build `coverage_matrix` in `comms_plan.json`: for every audience, which channels actually
reach it. Rules that matter more than any default channel list:

1. **Start from the audience's `preferred_channels` if the brief states them**, then check
   coverage against the registry's live channels. A channel the audience doesn't actually
   read is not coverage even if it's technically selected.
2. **Every audience needs at least one channel**, and the union of channels selected for
   an audience must be able to carry every mandatory message aimed at it — a banner alone
   (25 words) cannot carry all six mandatory questions; pair it with an email or article.
3. **Managers get the briefing deck before or alongside the email their team receives**,
   never after. A manager finding out from their own team's inbox is a change-management
   failure the registry's `must_never_carry` rule for `briefing_deck` exists to prevent.
4. **`short_form_video` and `explainer_video` are `planned`, not `live`** (see Stage 4).
   Select them in the matrix if the brief calls for video, but the run produces a script
   and `narration_spec.json`, never a rendered file — say so at plan time, not as a
   surprise at handover.
5. **Every mandatory `M` x `A` pair must appear in at least one `channel_runs` entry** by
   the end of this stage, even before Stage 3 fills in content. An audience with no
   channel able to carry a given mandatory message is a plan defect to fix now, not a
   Stage 5 surprise.

Write the skeleton `channel_runs` — one entry per selected audience x channel cell, with
`message_ids` populated and `blocks` empty — before moving to Stage 3.

## Stage 3 — Knowledge-bank retrieval and drafting

The knowledge bank lives at `comms-assets/knowledge-bank/` (or a path the practitioner
gives). Build or refresh its index and retrieve per channel run with the same tooling
`cm-proposal-generator` uses — unchanged, because the indexer derives `section` from the
top-level folder under the bank root and doesn't care what's in it:

```bash
python skills/cm-proposal-generator/scripts/index_kb.py comms-assets/knowledge-bank \
    -o comms/<run>/kb_index.json
python skills/cm-proposal-generator/scripts/retrieve.py comms/<run>/kb_index.json \
    --section narrative --tags payroll,portal --top 5
```

For each `channel_run`, pull candidate entries from `narrative/`, `channel-examples/`,
`tone-and-style/`, `faqs/`, and `glossary/` as the channel needs them, choose what actually
fits, and write blocks into `comms_plan.json` with their `sources` — the message IDs
and/or knowledge-bank entry IDs the content came from. Adapt tone and phrasing to the
channel and audience; adaptation is expected, fabrication is not.

**Provenance rule** (restated because it's the invariant that matters most here): every
block carries `sources` or `gap: true` with `gap_note`. A drafted paragraph with neither
is indistinguishable, once it's in a pack, from an invented claim — that's why Stage 5
fails the run on it rather than warning about it.

Dates and figures are the highest-risk content at this stage. Pull a date from `T1..` or a
number from the brief verbatim, never round or paraphrase it — a banner that says "over
2,000 people" when the brief says 2,400 is exactly the kind of drift Stage 5's
cross-channel consistency check exists to catch, and it's cheaper to avoid at draft time
than to catch later.

## Stage 4 — Build (route to each channel's producer)

Four routes, by channel. All four consume `comms_plan.json` blocks already checked for
provenance in Stage 3.

**Email and article → `.docx` via the `docx` skill.** One document per `channel_run` —
per audience, not one broadcast document. Standard `docx` skill workflow.

**Briefing deck → `.pptx` via the `pptx` skill's template route.** Follow the same
non-negotiables `cm-proposal-generator` documents for its deck: build from the firm's
approved template if one exists, never from scratch. If no approved template is
available, stop and ask rather than building a lookalike.

**Newsletter and banner → Canva.** Read this section in full before calling any Canva
tool — the two channels do not behave the same way, and the difference is not cosmetic.

This account's Canva connector is connected and authenticated, but has **no brand kits**
(`list-brand-kits` returned `{"items":[]}`) and **no brand templates**
(`search-brand-templates` returned `{"items":[]}`). Brand Kits and Brand Templates are
Canva Teams/Enterprise features. That means the autofill route
(`create-design-from-brand-template` + `get-brand-template-dataset`) has nothing to
target on this account — **it is unavailable regardless of how the run is set up**, not a
missing configuration step to fix. If a client engagement later provides a Canva Teams
workspace with real brand templates, that route becomes available and this section gets a
branch — it is not a gap in this skill's logic.

What does work on this account: `generate-design` → `create-design-from-candidate` →
`export-design`. The detail that decides whether QA'd copy survives is `verbatim`:

- **Newsletter** uses `generate-design` with `design_type: "doc"` and `verbatim: true`.
  `verbatim` is honoured **only** for `design_type: "doc"` — it places the supplied
  markdown into a Canva Doc with **no AI rewriting**. This is the one Canva route where
  the copy that shipped Stage 3's QA is the copy that lands in the design.
- **Banner** uses `generate-design` with `design_type: "poster"`. `verbatim` is **ignored**
  for posters — Canva's generator rewords whatever copy it's given, every time. QA'd copy
  cannot survive that route. **The banner therefore ships as a design plus the QA'd copy
  as text to paste in by hand — never as an autofilled design**, and say this plainly at
  handover. Presenting a poster-route Canva design as though it carries the QA'd words is
  the one honesty failure this skill cannot afford, because it is invisible to the
  practitioner until someone reads the banner closely.

**Both video channels are `planned`, not `live`, and this is a v0.1 limitation, not a
policy choice.** `ListConnectors` reports ElevenLabs `installState: "unknown"` and
`enabledInChat: false` in this session — its tools are not loaded, so no real
request/response pair from it can be observed, and wiring a call to a connector on a
guessed shape is fabrication, not integration. So for `short_form_video` and
`explainer_video`, Stage 4 produces:

- a script (scene-by-scene for `explainer_video`, single-beat for `short_form_video`)
- captions covering 100% of the spoken narration
- `narration_spec.json` — voice direction, per-scene timings, and pronunciation notes for
  domain terms (system names, acronyms) the narration would need to get right

and stops there. This is deliberate groundwork: wiring a narration engine later (Higgsfield
runs an ElevenLabs voice engine and is connected in this session, `generate_audio` with
`variant: "elevenlabs"`, or ElevenLabs directly once enabled) becomes a build step against
an already-QA'd spec, not a design job done under time pressure. Never claim a rendered
video file exists when the run only produced a spec.

## Stage 5 — QA

Both invariants, plus channel constraint compliance and cross-channel consistency, all
required. `qa_comms.py` (Part 2 of the plan this skill scaffolds against — not yet built
in this v0.1 scaffold) writes results to `qa_report.md` in the same layout and handover
language as `cm-proposal-generator`'s `qa_deck.py`. Until that script exists, run the same
five checks by hand and report them the same way:

1. **Message x audience coverage.** Every mandatory `M` reaches every `A` it applies to
   through at least one channel run. Report any uncovered pair explicitly.
2. **Provenance.** Every block has `sources` or `gap: true` with a `gap_note`. List every
   `[GAP]` as an action item, with what's missing and which message/audience it exposes.
3. **Mandatory-field presence per draft** — the six questions, checked against the
   *drafted* content in `comms_plan.json`, not the raw brief text. A message extracted at
   Stage 1 that never made it into an actual block is not coverage.
4. **Channel constraint compliance** — subject length, word counts, slide counts, video
   durations, all against `channel_registry.json`'s `constraints`.
5. **Cross-channel consistency** — every date, figure, name, deadline, and URL drafted for
   this run must agree across every channel that states it. If the email says 14 September
   and the banner says 15 September, that is a hard failure, not a style note.

Then deliver: the pack, the QA read (or the report once `qa_comms.py` exists), and a plain
statement of what's still open — the `[GAP]`s, any planned-not-live channel, anything the
brief left as an open question, and the reminder that this is a **draft for review**, not
cleared communications.

## Notes

- **The knowledge bank is the product**, exactly as it is for `cm-proposal-generator`. A
  thin bank produces a pack full of `[GAP]`s, and that's correct behaviour — it names what
  the firm hasn't written down about how it communicates change, not a bug in the run.
  Point the practitioner at `reference/knowledge-bank-guide.md`'s counterpart guidance
  (there is no separate comms KB guide in v0.1 — the proposal generator's guide's field
  notes apply unchanged, since `kb_entry.schema.json` is shared) to add entries rather than
  papering over a thin bank with generated filler.
- **Canva's honesty matters more than its polish.** A banner that looks finished but
  carries reworded copy is worse than one handed over with the paste-in instruction
  attached — the first looks QA'd and isn't; the second is visibly what it is.
- **Video is a script and a spec, not a video, in v0.1.** Say this before the practitioner
  asks, not after they notice there's no file.
- This skill does not send, publish, or schedule anything. It hands back a reviewable
  draft pack; distribution is the practitioner's decision, on their own systems.
