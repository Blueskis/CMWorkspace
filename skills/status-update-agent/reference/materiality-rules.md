# Materiality — what earns airtime

A cadence update is a few minutes long. The diff finds every change; materiality decides
which ones the meeting hears. It is assigned by rule rather than by judgement so that the
same movement is rated the same way every week, and so that the reason a change was rated
high can be argued with.

`diff_snapshots.py --print-rules` dumps the defaults as JSON. Edit and pass back with
`--rules` to fit a programme's own vocabulary. Do that once, early, and keep the file with
the run — changing the thresholds mid-engagement makes weeks incomparable.

## The defaults

| Movement | Rating | Why |
|---|---|---|
| An item that was there last week is gone | **high** | Silent disappearance is the one change nobody in the room can see for themselves |
| A date moved later | **high** | A slip is the news; the size is in `detail` |
| A status went backwards down the ladder | **high** | Regression is always worth saying out loud |
| RAG deteriorated | **high** | ditto |
| A percentage moved ≥25 points | **high** | Big enough to be the story on its own |
| A status advanced | medium | Expected; it's the aggregate that matters, not each one |
| RAG improved | medium | |
| A date pulled in | medium | |
| An owner changed | medium | Rarely the headline, often the explanation |
| A new item appeared | medium | |
| A count changed | medium | |
| Prose changed, or a number moved inside prose | medium | Similarity below 0.90, or any number in the text moved |
| A percentage moved 10–24 points | medium | |
| Something renamed, a small percentage move, cosmetic prose | low | |

Two rules stop the same news being told twice:

- **Subsumption.** A completion percentage jumping to 100 in the same week the status went
  to Complete is one piece of news. The percentage change is downgraded to low and marked
  `subsumed_by` the status change. QA does not require subsumed changes to be mentioned.
- **Numbers inside prose override similarity.** "Change network stands at 14 champions" →
  "16 champions" is a 96%-similar sentence and completely material. Any change to the
  numbers in a text block makes it at least medium.

## Where the rules stop

Materiality is about the size and direction of a movement, not its consequences. The rules
cannot know that a two-week slip on one learner is fine and on another puts a go-live at
risk. That read is the consultant's, and when the update makes it, it gets marked
`[JUDGEMENT]` — that's exactly what the marker is for.

So: **never re-rate a change to justify a narrative.** If a low-rated change is the story
this week, say why in the update and mark the reasoning as judgement. Editing the rules to
make it come out high is how a diff stops being evidence.

## Weeks where nothing moved

A run that produces no high or medium changes is a real result and should be delivered as
one: "the plan, the tracker and the deck are unchanged since last week apart from N
cosmetic edits." Check first that the documents were actually updated — an unchanged
tracker more often means nobody touched it than that nothing happened. That distinction is
worth raising in the meeting; a flat "no change" is not.
