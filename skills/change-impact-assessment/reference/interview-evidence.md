# Reading Interviews as Evidence

Interview material is where the as-is actually lives. Design documents describe the future;
only people describe what happens today, including the parts nobody wrote down. This guide is
about turning that material into register rows without over-claiming.

**A transcript is not a better set of notes — it is a different kind of evidence.** Notes have
already been interpreted by whoever took them: filtered, tidied, and reconciled. A transcript is
raw. That makes it noisier and much richer, and it needs to be read differently.

| | Written notes | Verbatim transcript |
|---|---|---|
| Already interpreted | Yes — by the note-taker | No |
| Verbatim quotes | Rarely | Always available |
| Hesitation, hedging, self-correction | Removed | Preserved — and it's signal |
| Contradictions within a session | Reconciled away | Visible |
| Who said what | Often lost | Usually attributed |
| Numbers | Cleaned to one figure | Several, disagreeing |
| Effort to read | Low | High — 60 min ≈ 9,000 words |

## 1. Attribute before you believe

**Who said it determines what it is.** The same sentence is different evidence from different
mouths, and this is the discipline that most affects the quality of a register:

| Speaker | What their statement is | Use it for |
|---|---|---|
| The person who does the work | **Testimony** — the strongest as-is evidence available | `as_is`, workarounds, `people_impact` |
| Their manager | A **claim** about the as-is, often the official version | `as_is`, corroborate against the doer |
| A designer, architect or programme lead | **Design intent** — evidence of the to-be, not of today | `to_be`, but check it against the spec |
| Anyone relaying what they've been told | **Hearsay** — evidence that a message landed, not that it's true | Comms findings only |
| A consultant or facilitator | The **question**, not the answer | Nothing. Don't mine your own prompts. |

The trap is hearsay about the to-be. In a real session you will hear things like *"we've been
told the new system does have a negotiation round"* — that is evidence about what people
believe, not about what the system does. It belongs nowhere near a `to_be` field until a
functional spec or process model confirms it. If a to-be statement's only source is an
interview, mark the row **Medium confidence at best** and say where it came from.

**Unattributed transcripts are weaker evidence.** Machine transcription produces no speaker
labels. If you can't tell who said something, you can't classify it, and everything drawn from
that file drops a confidence level. Get the platform transcript, or attribute the turns from the
attendee list before relying on it.

## 2. Harvest the verbatim

This is the thing a transcript gives you that nothing else will. **Take the sentences.**

> *"That's a phone call. Always has been. That's — I mean that's the job, isn't it. That's where
> I actually earn my money. You can't do that through a portal."* — Category Manager, INT-04
> @00:00:38

That single quote establishes: what the as-is is (offline negotiation), that the change removes
it, that the person's professional identity is bound up in it, and roughly how hard the
resistance will be. A note would have recorded "second-round negotiation currently by phone".

Put quotes in `people_impact` where they explain a score, and in `notes` where they're evidence
for a judgement someone might challenge. **A real sentence from a real person moves a steering
committee in a way no assessment adjective does** — and it is much harder to argue with, because
it isn't your opinion.

Clean lightly for the deliverable: drop filler and false starts, keep meaning, tone and register.
Never smooth someone into sounding more measured than they were — the heat is the finding. Always
carry the timestamp so it can be checked.

## 3. Read the hesitation

Disfluency is not noise. These patterns are worth stopping for:

- **Self-interruption on a value statement** — *"That's — I mean that's the job, isn't it."*
  Someone defending their professional worth. Expect High resistance.
- **"Supposed to" / "in theory" / "officially"** — a control gap. What follows is the real
  process. *"We're supposed to check the DOA, but…"*
- **Tag questions** (*"isn't it", "right?"*) — seeking agreement, often because the speaker
  senses the position is weak or unpopular.
- **Laughter, sarcasm, "well, good luck with that"** — usually a prior-failure reference. Ask
  what happened last time; it is almost always the thing that will happen again.
- **Long pause before answering a simple question** — the honest answer is awkward.
- **Volunteering credentials** (*"I've been doing this nineteen years"*) — status is at stake,
  not just task. That distinction changes the mitigation entirely.

## 4. Contradiction and corroboration

**Contradictions are findings, not noise to resolve.** People describe the official process
early and the real one later, once they've relaxed. The gap between the two *is* the workaround,
and the workaround is usually what the new system blocks.

**Two speakers independently → corroboration.** Raises confidence. One speaker saying it twice
→ emphasis: it tells you the topic matters to them, not that it's true.

**Disagreement about a number is itself the finding.** When one person says the team runs
"a hundred and forty, hundred and fifty" sourcing events a year and a colleague says *"closer to
two hundred if you count the small ones we don't formally log"* — the register shouldn't record
either figure as fact. It should record that there is unlogged sourcing activity, which is a
scope and a compliance finding. A note would have written "~150 events/year" and lost it.

## 5. Never bank a number heard once

Figures from speech are the least reliable thing in the room, for two compounding reasons:
people estimate loosely when talking, and ASR mangles numbers, acronyms, system names, module
names and people's names — precisely the vocabulary a CIA runs on.

Rules:
- A headcount, volume or percentage whose **only** source is speech → **Low confidence**, and an
  open question in `notes`. Always.
- Corroborate against an HR extract, org chart or system report before it drives a training
  audience size or an effort estimate.
- Treat any system or module name from a machine transcript as a spelling to verify.

## 6. Mine the silence

- **Questions asked and not answered** are design holes. If someone asks twice and gets nothing,
  that is an unowned decision — write the row at Low confidence with the gap as the open
  question, and escalate it. This is one of the highest-value things a CIA surfaces.
- **Who didn't speak.** In a group session, a function that never spoke has not consented — it
  wasn't consulted. Check the attendee list against the speaker list; the difference is a
  coverage gap.
- **Groups nobody mentioned.** Suppliers, approvers, downstream finance teams and shared-service
  centres are routinely absent from every interview, because nobody in the room does that job.

## 7. Working through a long transcript

A 60-minute interview is ~9,000 words. Skimming produces generic rows. Work it in passes:

1. **Skim for structure** — mark where the topic changes. Sessions run process by process.
2. **Pass for as-is** — every description of how work is done today, with the timestamp.
3. **Pass for the human signal** — resistance, loss, fear, prior failure, status, benefit.
4. **Pass for numbers, names and dates** — flag every one as needing corroboration.
5. **Pass for gaps** — unanswered questions, hedges, "I don't know who owns that".

Then map to rows. Don't write the register while reading; you'll anchor on the first speaker.

## 8. What feeds what

| From the interview | Goes to |
|---|---|
| How work is done today, including workarounds | `as_is` |
| Design intent, only if a designer is speaking authoritatively | `to_be` — corroborate against the spec |
| Job changes, new skills, mindset shift, verbatim quotes | `people_impact` + `score_people` |
| Hand-offs, sequence, who does what today | `process_impact` + `score_process` |
| Which systems they touch, and how often | `tech_impact` + `score_technology` |
| Policy, control, audit findings, compliance obligations | `other_impacts` |
| Roles as people describe them, in their own language | `current_roles` |
| Team sizes, volumes — corroborate first | `headcount_impacted` (Low confidence if speech-only) |
| Tone, loss, prior failure, status threat | `resistance_risk` + `mitigation_actions` |
| What the group says they'd gain | `benefit_narrative` — if nobody names one, that's a finding |
| Who the group actually listens to | `change_champion` |
| Unanswered questions, disputed numbers | `notes` + Low `confidence` |

## 9. Citing interview evidence

Cite the ref and, for transcripts, the timestamp: **`INT-04 @00:00:38`**. Multiple sources with
`; ` between them, e.g. `INT-04 @00:00:38; FS-01`.

The timestamp is better than a page number, because a reviewer can jump straight to the audio
and hear the tone — which is often the part being disputed. For a claim that rests on several
moments, cite the strongest one rather than a range.

## 10. Honest limits

A transcript will not give you:

- **The to-be**, unless a designer is speaking and you corroborate it against a document.
- **Reliable figures.** Ever. See §5.
- **Anything about people not in the room** — most obviously suppliers and other external
  audiences, who are never interviewed and are the most commonly missed group on a
  network-based implementation.
- **What people will actually do**, as opposed to what they say they'll do. Stated intent to
  work around a control (*"I'll go around it"*) is strong evidence of risk, not of outcome —
  record it as a risk with a mitigation, not as a prediction.
