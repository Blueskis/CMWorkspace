# Comms Channel Library

How Stage 2 selects channels per audience, and how Stage 3 drafts and Stage 5 audits
against each one. `schemas/channel_registry.json` is the machine-readable source of
truth — this file is its prose counterpart, one section per channel, for reading rather
than parsing. If the two ever disagree, the registry wins; fix this file to match it.

Seven channels, matching the Change Comms Console's `CHANNELS` array (artifact `aa44b762`,
synced at registry `version: "0.1.0"`).

---

## Email

**Purpose.** The direct, individually-received communication. The channel most audiences
treat as the authoritative record of "did I hear about this."

**When to use.** For every audience, in almost every run — email is the one channel that
reaches someone whether or not they go looking for the change. Skipping it for an audience
needs a stated reason (e.g. a factory-floor population with no individual work email,
where a poster or briefing carries the load instead).

**Hard constraint.** Subject line ≤ 50 characters. Body ≤ 400 words. Subject is the harder
limit in practice — draft it last, once the body has said everything the subject only
needs to summarise.

**Must carry.** The full mandatory message set for the audience it targets (what / who /
why / when / action / help), a sender the audience recognises as authoritative, and a
single clear call to action.

**Must never carry.** More than one call to action, or a timeline date the briefing deck
or newsletter doesn't also carry unmarked as a deliberate update.

**Producer.** `.docx`, via the `docx` skill. One document per audience.

**QA rules.** Subject ≤ 50 chars (hard fail if not). Every mandatory message kind present
in the drafted body, checked against the actual text, not just referenced by ID. Sender
name matches `change_brief.json`'s `sender`.

---

## Article (intranet)

**Purpose.** The longest-form written channel — carries the case for change in full,
where email only has room to summarise it.

**When to use.** Wherever an intranet, portal, or comparable internal publishing surface
exists for the audience. Pairs with email rather than replacing it: email drives people to
read the article for context they want but don't need immediately.

**Hard constraint.** Body ≤ 900 words.

**Must carry.** The full case for change in more than one sentence (the "why," expanded),
a link or reference to where to get help, and the same headline dates every other live
channel in the run states.

**Must never carry.** A call to action that contradicts the email's, or an unconfirmed
timeline event presented as settled.

**Producer.** `.docx`, via the `docx` skill.

**QA rules.** Word count within limit. Every date/figure cross-checked against every other
channel in the run (Stage 5 check 5). No mandatory message kind entirely absent, since the
article is often where practitioners bury the "why" and skip the rest.

---

## Briefing deck (manager)

**Purpose.** Equips managers to present the change to their own teams — a talking-points
artifact, not a read-solo document.

**When to use.** Any run with a manager/line-lead audience distinct from the general
population. The console's Step 02 audience segmentation exists largely to make this
distinction possible.

**Hard constraint.** ≤ 12 slides.

**Must carry.** Talking points a manager can deliver without additional prep, an FAQ or
objection-handling slide sourced from `comms-assets/knowledge-bank/faqs/`, and an
escalation path — where a manager sends a question they can't answer themselves.

**Must never carry.** Information the manager's own team should hear from the manager
first, appearing anywhere the team might see it before the manager's briefing happens.
Dense prose paragraphs — this deck gets talked over, not read.

**Producer.** `.pptx`, via the `pptx` skill's template route. Same non-negotiables as
`cm-proposal-generator`'s deck: build from the firm's approved template, never from
scratch; stop and ask if none exists.

**QA rules.** Slide count ≤ 12. Every talking point traces to a message ID or a KB entry.
Escalation path present and matches `change_brief.json`'s `sender` or a named alternative.

---

## Newsletter

**Purpose.** A scannable, mid-length format for a broad or recurring readership — carries
the mandatory set condensed, with a pointer into the article for readers who want more.

**When to use.** Where the org already runs a regular newsletter the audience reads. Not a
substitute for email — treat it as an additional surface, since a newsletter is opt-in
attention in a way email isn't.

**Hard constraint.** ≤ 350 words.

**Must carry.** The mandatory message set, condensed for a scannable format, and a link or
pointer into the article.

**Must never carry.** A call to action Canva's generator has reworded. This is the
channel where verbatim protection actually matters, because it's the one honoured route
(see Producer, below).

**Producer.** Canva `generate-design`, `design_type: "doc"`, `verbatim: true`. This is the
**only** Canva route where `verbatim` is honoured — the supplied markdown lands in the
Canva Doc with no AI rewriting. QA'd copy survives intact. See `SKILL.md` Stage 4 for the
full Canva findings (no brand kits, no brand templates on this account — the autofill
route is unavailable regardless).

**QA rules.** Word count within limit. Content matches the QA'd `comms_plan.json` blocks
verbatim — this is checkable precisely because `verbatim: true` makes it a fair
comparison, unlike the banner.

---

## Banner

**Purpose.** A single-glance, high-visibility surface — a poster, a digital signage slide,
a launch-day visual. Carries one message, not the full set.

**When to use.** Wherever the org has a physical or digital signage surface, or wants a
launch-day visual asset. Always pairs with a channel that can carry the full detail — a
banner alone is never sufficient coverage for a mandatory message set.

**Hard constraint.** ≤ 25 words.

**Must carry.** The single headline message (not the full mandatory set), and a pointer
(URL or QR reference) to a channel with the full detail.

**Must never carry.** A date or figure not also stated in the email or article — a banner
can't carry `sources` the way a document can, and it's the hardest channel to correct once
printed or posted, so drift here is the most expensive kind. A call to action inconsistent
with the email's.

**Producer.** Canva `generate-design`, `design_type: "poster"`. `verbatim` is **ignored**
for posters — Canva's generator rewords whatever copy it's given, every time. **The banner
therefore ships as a design plus the QA'd copy as text to paste in by hand, never as an
autofilled design.** Say this at handover, every time — a finished-looking poster with
reworded copy is the single easiest way for this skill to mislead a practitioner.

**QA rules.** Word count of the *pasted-in* copy (not whatever Canva's generator produced)
≤ 25 words. Every date/figure on it cross-checked against the email and article. Flag
explicitly, in the QA report, that the shipped design's on-canvas text is not guaranteed
to match the QA'd copy until the practitioner pastes it in.

---

## Short-form video

**Purpose.** A brief, single-message video for a fast-attention channel — the video
analogue of the banner.

**When to use.** Where the org has a channel that supports video and the audience responds
better to a short clip than a document. Selecting this channel in Stage 2 is legitimate;
expecting a rendered file out of Stage 4 in v0.1 is not.

**Hard constraint.** ≤ 60 seconds of narration.

**Must carry.** The single headline message, matching the banner's. Captions covering
100% of spoken narration.

**Must never carry.** Any claim that a narrated video file exists. It doesn't, in v0.1 —
see Producer.

**Producer.** **Planned, not live.** No narration engine is wired (ElevenLabs is not
enabled in this session; see `SKILL.md` Stage 4 for the full finding). Stage 4 produces a
script, full captions, and `narration_spec.json` — voice direction, timings, pronunciation
notes — so wiring a narration engine later is a build step against an already-QA'd spec.

**QA rules.** Script length maps to ≤ 60 seconds of spoken narration at a normal reading
pace. Captions cover 100% of the script. `narration_spec.json` present and validated.

---

## Explainer video

**Purpose.** A longer video carrying the full mandatory message set scene by scene, often
with a worked example or walkthrough — the video analogue of the article.

**When to use.** Where the change is complex enough that a written article underperforms —
a new system walkthrough is the common case.

**Hard constraint.** ≤ 180 seconds of narration.

**Must carry.** The mandatory message set in full, scene by scene. Captions covering 100%
of spoken narration.

**Must never carry.** Any claim that a narrated video file exists. Same limitation as
short-form video.

**Producer.** **Planned, not live.** Same reason as short-form video. Stage 4 produces a
scene-by-scene script, captions, and `narration_spec.json`.

**QA rules.** Same as short-form video, scaled to the longer duration and scene structure.
Every mandatory message kind present somewhere in the scene sequence.
