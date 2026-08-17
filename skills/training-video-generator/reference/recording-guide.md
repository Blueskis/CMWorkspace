# Recording guide — for the functional consultant

**Send this before they record, not after.** It costs five minutes to read and saves a
re-record. Everything downstream is built from this recording, and no amount of scripting
recovers a capture that shows the wrong client's data or splits into unusable fragments.

You are not making a video. You are capturing raw material — someone else adds the voice,
the annotations and the presenter. Record like a demo you would give a new joiner, then stop.

---

## Before you hit record

**Use a training or sandbox client. Never production.** This is the one hard stop in the
whole process. If real customer names, personal data, salary figures, or a live client's
transactions appear on screen, the recording cannot be used at all and the whole thing gets
re-shot. Check what is in the test data before you start, not after.

Then:

- **1920×1080, 16:9.** Match it exactly if you can; anything else gets letterboxed or cropped.
- **Close everything you are not demonstrating.** Email, chat, calendar, ticketing.
- **Turn off notifications.** Do Not Disturb on the OS, and quit anything that pops toast.
- **Clean the browser.** No bookmarks bar full of client names, no other tabs, no extensions
  that inject banners.
- **Check the bottom-right corner is not where the important content sits.** The presenter
  avatar appears there. If a key total or status field lives in that corner, mention it and it
  will be moved for those scenes.
- **Zoom the UI up if the text is small.** What is readable on your 27" monitor is not
  readable on a laptop at half size. 110–125% browser zoom is usually about right.

## While recording

**Talk through what you are doing. Your words become the script, close to verbatim.**

Say what you are clicking and why — "now I pick the cost centre, and this one is mandatory for
stocked items, people forget that". Rough and unscripted is fine. Do not write a script, do
not do retakes, do not worry about ums: fillers, false starts and the bit where you take a
wrong turn all get edited out.

What does *not* get added is anything you did not say. The narration is your explanation with
the mess removed — not a rewrite, and not somebody else's guess at why a field matters. So the
useful instinct while recording is simply to **explain more than feels necessary**:

- Why a field is mandatory, and what happens if it is skipped.
- What people habitually get wrong here.
- What the system is doing when it pauses.
- Which of two similar-looking options is the right one, and how to tell.

That is the knowledge the screen cannot show, and it is the difference between a module that
demonstrates the clicks and one that actually prepares somebody. **A silent recording produces
a much weaker module**, because then the only material available is what the screen happens to
display.

Your voice does not end up in the final video — the presenter avatar re-records it in a
consistent voice — but the words stay yours.

Anything you cannot answer on camera, say so out loud ("I'd have to check who this routes
to"). That becomes a flagged gap for you to confirm later, rather than someone inventing a
plausible answer.

Then:

- **Pause a beat between steps.** One second of stillness after each action. This is what lets
  the recording be split into scenes automatically, and it is the difference between clean
  boundaries and a script that has to be timed by hand.
- **Move the mouse deliberately.** Slow, direct movements. No circling or waggling to point at
  things — annotations will do the pointing.
- **Do the steps in the order a learner would.** If you need to set something up first, either
  do it before recording or say clearly that it is preparation.
- **If you fluff a step, pause, say "again", and redo it.** Do not stop recording. The bad take
  gets cut, and the pause makes it easy to find.
- **Let the system take as long as it takes.** Do not sit and wait awkwardly — long spinners
  get sped up automatically. Just carry on when it finishes.

## Length

**Aim for 3–5 minutes per module.** Two reasons, and both bite:

- Finished video is capped by the monthly Synthesia credit budget, so length is a planning
  input rather than an outcome.
- Every revision re-renders the whole module at full cost, and modules always get revised.

If a procedure genuinely needs fifteen minutes, record it as three or four separate modules
split at natural boundaries. That is better training anyway — nobody watches a fifteen-minute
system walkthrough in one sitting.

There is also a hard ceiling on what can be uploaded in one piece (currently 500MB and 30
minutes, but check — see `synthesia-build.md`).

## When you are done

Send:

1. **The recording**, unedited. Do not trim it yourself — cuts are decided against the script,
   and a file that has already been cut cannot be re-cut differently.
2. **What it is:** which module, which system, which role it is for, and which release or
   environment you recorded against. That last one matters when the UI changes later.
3. **Anything you got wrong or skipped**, in a sentence. Cheaper to note now than to discover
   in QA.

## When the system changes

Releases change screens, and training that shows the old screen is worse than no training —
people trust it and then get lost.

**Re-record only the affected steps.** The pipeline is built around per-scene units precisely
so one step can be replaced without redoing the module. Tell us which step changed and record
just that fragment, matching the original resolution and zoom level so it cuts in cleanly.

---

## Quick checklist

```
[ ] Training/sandbox client — no production data, no real client names
[ ] 1920x1080, notifications off, browser clean
[ ] UI zoomed enough to read on a laptop
[ ] Talking through the steps as I go — my words become the script
[ ] Explaining why, not just what: gotchas, mandatory fields, what breaks
[ ] Said out loud anything I wasn't sure about
[ ] One second pause between steps
[ ] Aiming for 3-5 minutes
[ ] Noted the release/environment I recorded against
```
