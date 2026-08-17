# Channel Library

The four channels `cm-comms-generator` v0.1 drafts, what each is actually for, and how each
one fails. Read the rules before the catalogue — they decide more outcomes than the anatomy
does.

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
`sharepoint_banner`, which is an open channel with no audience control. Checked mechanically in
Stage 4.

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

## SharePoint banner

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

## Slide deck

**Purpose.** A briefing someone *presents* — a manager cascade pack, a town hall, a leadership
pre-brief. This is the only channel that also renders to HTML.

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

## Short-form video outline

**Purpose.** A script and shot outline for a 30–90 second explainer. **The output is an outline
for a producer, not a video.** Say so at handover.

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

---

## Choosing when the practitioner has not chosen

| Impact | Required action? | Sensitivity | Primary channel | Also required |
|---|---|---|---|---|
| High | Yes | routine / sensitive | Email | Manager cascade deck first |
| High | No | routine | Email | Banner to sustain |
| High | Any | market-sensitive | Manager cascade deck | Email after release; **never** a banner |
| Medium | Yes | routine | Email | — |
| Medium | No | routine | Banner | Links to a hub page |
| Low / informational | No | routine | Banner | — |
| Any | Yes | routine, procedural | Email | Video outline if the action is a screen flow |

Recommend once, with the reason. Then build what was asked for.
