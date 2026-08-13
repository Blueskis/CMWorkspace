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

Expected: fit check passes, 6 scenes and 1m06s, one open `[GAP]`, QA passes with no warnings.

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

**A `[GAP]` (`S06`).** The approval status chip is truncated at the frame edge, so the
recording never establishes where a stocked-item requisition routes. Rather than writing a
plausible sentence about approval routing, the scene is flagged for the consultant to confirm.
This is the invariant that matters most — the narration cannot assert something the footage
does not show.

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
  ok    control (clean fixture passes)
  ok    provenance: narration over a frame nobody read
  ok    coverage: hole in the scene tiling
  ok    fit: narration over its word budget
  ok    consistency: annotation parked under the avatar
  ...
all 13 invariant breaches caught
```

Run it after changing anything in `qa_video.py` or `fit_narration.py`.
