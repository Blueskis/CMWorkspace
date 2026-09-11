# Channel Library

The seven channels `cm-comms-generator` drafts, what each is actually for, and how each one
fails. Read the rules before the catalogue — they decide more outcomes than the anatomy does.

Which tool builds each one, and what to do when it is unreachable, is in
`channel-routing.md`. This file is about the writing.

## Rules

**1. The channel is a choice, not an order.** If the practitioner asks for a banner to carry a
high-impact message with a required action, say so once and recommend the pairing that works —
then build what they asked for. A banner is a signpost; it cannot be the only place an action
lives. Say it, don't refuse.

**2. One channel per run; one message spine across runs.** Cross-channel consistency comes from
the shared `change_brief.json`, never from copying text between drafts. Two channels disagreeing
about a go-live date is exactly the failure the shared brief exists to prevent. If the change
moves, edit the brief and re-run the affected channels.

**3. The messenger and the channel must agree.** A named sponsor's words on an unattributed
banner read as rumour. A corporate mailbox delivering a redundancy-adjacent message reads as
evasion. `governance.sender.why_this_messenger` in the brief forces this to be a deliberate
choice; honour it in the sign-off.

**4. Audience segments do not all get the same comm.** Where `manager_cascade_required` is set
on a segment, the manager brief goes *before* the mass channel — a line manager finding out
from the all-staff email is the fastest way to lose the cascade.

**5. Sensitivity gates the channel.** A `market-sensitive` message may not be planned onto a
`banner` or a `newsletter` — both are open channels with no audience control. Checked
mechanically in Stage 4.

**5a. Some channels are signposts, not comms.** A `banner` and a `short_form_video` carry one
message and point at where the detail lives; everything on them must exist in full somewhere
they link to. QA scores them that way (`coverage_mode: signpost`), so do not stuff a signpost
with the whole story to make coverage look better — that is the failure, not the fix.

**6. One primary action per comm.** A second call to action roughly halves compliance on the
first. Where a segment genuinely has two actions, sequence them across sends rather than
stacking them in one.

**7. Lead with the reader, not the programme.** "The payroll migration enters Phase 2" is
programme news. "You need to enrol by 14 September" is a comm. The programme's own milestones
belong in the timeline section, not the opening.

---

## Email

**Purpose.** The workhorse. Carries a required action to a named audience and leaves a durable
record they can re-read.

**The right choice when** there is an action, a date, or a rationale that needs more than a
sentence; the audience is addressable; the message is `routine` or `sensitive` with a named
sender.

**Anatomy** — the `part_kind` sequence:

| Part | Carries |
|---|---|
| `subject` | The single most important fact. Not the programme name. |
| `preheader` | The second most important fact — it shows in the inbox preview and is usually wasted. |
| `opening` | Who is writing, and why now |
| `whats-changing` | The substance, in the reader's terms |
| `whats-not-changing` | Named reassurance where the brief supplies it |
| `who-is-affected` | So a reader can tell in one line whether this is about them |
| `your-action` | Single, explicit, dated. Above the fold. |
| `timeline` | The dates that matter to *this* audience |
| `help` | Where to go when the action fails |
| `signoff` | A real name and role |

**Constraints.** Subject ≤ 50 characters (mobile truncation); preheader ≤ 90; total ≤ 300
words; one primary action, placed above the fold.

**Failure modes.** Rationale buried below the action. "Further details will follow" with no
date. A distribution list nobody recognises as being about them. The action expressed as a bare
link with no statement of what it does. Sending to all-staff because segmenting was hard.

---

## Banner

**Purpose.** Ambient awareness and a route to the detail. It is a signpost, not a comm.

**The right choice when** reinforcing a message already sent through an owned channel; driving
traffic to a hub; sustaining visibility between milestones.

**Anatomy.** `headline` → `subhead` → `cta` (label + destination) → `placement-spec` (pixel
dimensions, safe area, display window, alt text).

**Constraints.** No unique content — everything on a banner must exist in full somewhere it
links to. Contrast against the accessibility floor. On most tenancies the text is baked into the
image, so it is unsearchable and invisible to screen readers: **alt text is mandatory, not
optional**, and it must carry the message, not describe the picture.

**Failure modes.** A banner as the only channel for an action. Text outside the safe area,
clipped on narrow viewports. A stale banner outliving its milestone. Announcing news to people
who have not been told through an owned channel first.

---

## Article

**Purpose.** The considered version — an intranet or newsletter piece someone reads because
they want the whole story, not because an action is chasing them.

**The right choice when** the change has a rationale worth explaining at length, when
speculation needs answering in public, or when a comm has already gone out and people now want
the detail behind it. It is the channel that persuades; the email is the channel that instructs.

**Anatomy.** `headline` → `standfirst` (the one-paragraph promise of what the reader gets) →
opening → why this, why now → what's changing → `pull-quote` → what's not changing → who's
affected → what you need to do → timeline → where to get help → byline.

**Constraints.** Headline ≤ 80 characters; standfirst ≤ 200; body ≤ 900 words. One pull quote
per screen at most. A byline with a real person, because an unattributed article about pay
reads as a press release.

**Failure modes.** An article that is really a long email — if it opens with an instruction and
a deadline, it should have been an email. Burying the rationale under programme background.
A pull quote that repeats the sentence directly above it. Writing to the length of what you
know rather than what the reader needs.

---

## Newsletter

**Purpose.** A periodic round-up carrying several items, of which this change is one. It
reaches people who are not currently thinking about the change at all.

**The right choice when** you need sustained visibility across a programme rather than a single
announcement; when the change is one of several things an audience must track; when reinforcing
something already sent through a direct channel.

**Anatomy.** `headline` → `standfirst` → stacked `section-heading` blocks, each self-contained →
`cta` → placement and distribution spec.

**Constraints.** Headline ≤ 70 characters; each section ≤ 220; at most six sections before it
stops being read. Every section stands alone — assume nobody reads to the end, and put nothing
in the last section that matters.

**Failure modes.** Burying a deadline in item four. Sections that depend on each other in order.
Recycling the email verbatim, which tells subscribers the newsletter carries nothing new. Letting
the round-up become the only place an action was ever stated.

---

## Briefing deck

**Purpose.** A briefing someone *presents* — a manager cascade pack, a town hall, a leadership
pre-brief. Builds as `.pptx`, on the client's own `.potx` wherever one exists.

**The right choice when** the message needs a human in the room, or the audience needs to ask
questions; whenever `manager_cascade_required` is set on the target segment.

**Anatomy.** Title → why this, why now → what's changing → what's not changing → who's affected,
by segment → timeline → what we're asking of you → support and help → anticipated objections.

**Constraints.** ≤ 12 slides for a cascade pack. ≤ 5 bullets per slide. **Speaker notes on every
content slide** — a cascade deck without notes gets improvised, and the improvisation is what
the audience remembers.

**Failure modes.** A reading deck rather than a speaking deck. The timeline as a decorative
graphic with no dates. No anticipated-objections slide, so the cascade manager is ambushed by
the first question. A deck that reproduces the email verbatim, which tells the presenter they
are not needed.

---

## Short-form video

**Purpose.** A script and shot outline for a 30–90 second clip. **The output is a production
spec for a producer, not a video.** Say so at handover.

**The right choice when** the change is visual or procedural — a new screen, a new physical
process — and demonstration beats description; when reach matters more than depth.

**Anatomy.** Hook (≤ 5 s) → what's changing → what it means for you → one action → where to find
more → end card. Rendered as a table: scene | duration | visual / on-screen text | voiceover |
caption.

**Constraints.** `max_duration_seconds` from the brand profile. Runtime is estimated as
`spoken_words ÷ words_per_minute × 60` — Stage 4 computes it and fails an overrun. Captions
mandatory: most views are muted. One message, not three. No dates on screen unless the milestone
is `confirmed`, or the asset dates itself the moment the plan slips.

**Failure modes.** Scripting 200 words into a 45-second slot. The action arriving after viewers
have dropped off. On-screen text too small to read on a phone. Handing the outline over as
though it were a finished asset.

It is a **signpost**: one message, then point at the detail. Do not try to make a 60-second clip
carry a whole change.

---

## Explainer video

**Purpose.** A 2–5 minute walkthrough of a process or a system — the channel that shows rather
than tells. Typically an on-screen presenter over screen capture.

**The right choice when** the change is procedural and someone has to *do* something in a new
interface; when a written instruction keeps generating the same support tickets; when the
audience needs to see the screens before they meet them.

**Anatomy.** Hook → why this, why now → what's changing and what isn't → `chapter` per task,
each one a complete walkthrough → the deadline → where to get help → end card.

**Constraints.** `max_duration_seconds` from the brand profile, typically 240–300. Chaptered, so
someone stuck on step three can jump to it rather than rewatching. Captions mandatory. Runtime is
estimated from word count at the brand's words-per-minute — a scene near its budget is over,
because a real read has pauses.

**Failure modes.** A talking head with no screen capture, which is a video of a memo. Recording
the interface before it is final, so the video and the system disagree on day one. No chapters,
so it is unusable as reference. Dates on screen that date the asset the moment a plan slips —
only put a `confirmed` milestone on screen.

---

## Choosing when the practitioner has not chosen

| Impact | Required action? | Sensitivity | Primary channel | Also required |
|---|---|---|---|---|
| High | Yes | routine / sensitive | Email | Briefing deck cascade first |
| High | No | routine | Article | Banner to sustain |
| High | Any | market-sensitive | Briefing deck | Email after release; **never** a banner or newsletter |
| Medium | Yes | routine | Email | — |
| Medium | No | routine | Newsletter | Links to a hub page |
| Low / informational | No | routine | Banner | — |
| Any | Yes | routine, procedural | Email | Explainer video when the action is a screen flow |
| Any | No | routine, contested | Article | Answers speculation in public |
| Any | Yes | routine, high reach | Short-form video | Only alongside a channel carrying the detail |

Recommend once, with the reason. Then build what was asked for.
