# Fixture demo — a worked example

A complete run of the training video pipeline against an invented system. **Nothing here is
real** — no client, no system, no data — the same fictional-input discipline as
`examples/acme-erp/`.

It exists so the pipeline can be exercised end to end without a Synthesia account, without
ffmpeg, and without anyone's client system.

## What ships here

| File | What it demonstrates |
|---|---|
| `capture_map.json` | Stage 1 output — seven scenes tiling a 70s recording, all read |
| `video_script.json` | Stage 2 output — narration fitted to measured durations |
| `inputs/guide_transcript.txt` | The consultant's spoken walkthrough, the SME source |
| `make_fixture.sh` | Generates the synthetic `demo.mp4` (needs ffmpeg) |

## Run it

Stages 2 to 4 need no ffmpeg and no video:

```bash
cd examples/fixture-demo
S=../../skills/training-video-generator/scripts

python $S/fit_narration.py video_script.json
python $S/build_sheet.py capture_map.json video_script.json \
    -o /tmp/build_sheet.md --scenes /tmp/scenes/ --trim-list /tmp/trim_list.csv
python $S/qa_video.py capture_map.json video_script.json -o /tmp/qa_report.md
```

Expected: fit check passes with three warnings, 66s of footage building to an 81s module, one
open `[GAP]`, QA passes.

To exercise Stage 1 as well, generate the video first — this needs ffmpeg:

```bash
./make_fixture.sh
python $S/ingest_capture.py inputs/demo.mp4 -o /tmp/capture_map.json --frames /tmp/frames/
```

Boundaries should land at 12, 27, 31, 41, 49 and 56 seconds. If they don't, that is the
scene-detection threshold needing a tune — which is the point of running it.

## What each part is here to show

**A cut with a reason (`S03`).** The consultant opens the wrong tile and navigates back.
Dropped footage always carries a stated reason; `qa_video.py` fails the run otherwise, so
content cannot vanish silently between the recording and the video.

**An acceleration (`S05`).** Eight seconds of a posting spinner. Kept, sped up, and narrated
as a deliberate silent beat rather than padded with filler.

**Cleaned-verbatim narration.** Every scene carries `source_excerpt` — what the consultant
actually said — beside the cleaned `narration`. Compare S02's pair to see the whole editorial
policy in one place: `"Right, so Create Purchase Requisition. First line, material number goes
in here."` becomes `"So, Create Purchase Requisition. First line, the material number goes in
here."` Filler out, article in, meaning and voice untouched. Nothing is added anywhere, and
`qa_video.py` diffs the vocabulary against the transcript to prove it.

**Frame holds (`S01`, `S02`, `S04`).** The consultant talks faster than the avatar delivers,
so all three step scenes need more time than their clip — 1.8s, 2.4s and 3.8s. That is the
normal case in cleaned-verbatim mode, not a defect: the footage holds its last frame. It is
also why the built module is 81s against 66s of recording, and why credits are budgeted on the
former.

**A boundary that had to move (`S04`/`S05`).** As first cut, S04 ran 31–41s and its narration
needed 7.8s more — too long to hold a still for, so `fit_narration.py` failed it and said to
re-cut. The boundary was wrong: the consultant kept explaining the cost centre rule while the
save spinner started. Moving it to 45s fixed the scene and shrank the spinner to 4s. The
`disposition_note` on S05 records why.

**A `[GAP]` (`S06`).** The consultant says the requisition has "gone off for approval" but
never says to whom, and the approval status chip is truncated at the frame edge — so neither
the words nor the screen establish the routing. Rather than writing a plausible sentence about
approval rules, the scene is flagged for the consultant to confirm. This is the invariant that
matters most.

**An intermittent avatar.** Visible on the intro and outro, hidden across the three step
scenes. Two of six scenes, not six of six: a talking head competes with the screen exactly
when the learner is following a click path, and it costs render credit every second it is on.

**A glossary that bites.** `cost centre` is fixed against `cost center`, and
`Purchase Requisition` against `PR ticket`. Terminology drift is the commonest defect in
system training and the least likely to be noticed by eye.

## Proving the checks actually work

A clean fixture passing proves little on its own — a QA script that always returned zero would
pass it too. `check_invariants.py` mutates the fixture once per rule and asserts each breach
is caught, with a control case asserting the untouched fixture still passes:

```bash
python check_invariants.py
```

```
  ok    control (clean fixture passes, no fidelity warning)
  ok    provenance: narration over a frame nobody read
  ok    coverage: hole in the scene tiling
  ok    fit: narration over its word budget
  ok    consistency: annotation parked under the avatar
  ok    fidelity: narration invents content the SME never said
  ...
all 16 invariant breaches caught
```

Fidelity breaches are warnings rather than failures, so those cases are asserted against the
report text instead of the exit code.

Run it after changing anything in `qa_video.py` or `fit_narration.py`.
