---
name: training-video-generator-v0.1
description: Turns a functional consultant's screen recording of a system demo into a narrated, annotated training video built in Synthesia with the practitioner's AI avatar. Reads the recording frame by frame to establish what is actually on screen, writes narration fitted to each scene's measured duration, specifies annotation copy and avatar placement, and emits a paste-ready build sheet for the Synthesia editor — then audits the result for whether the narration matches the screen. Use whenever someone wants to turn a screen recording, system walkthrough, or demo capture into training video, e-learning, or a how-to module — phrases like "turn this recording into a training video", "script this demo for Synthesia", "narrate this walkthrough", "add my avatar to this screen capture", "make a training video for this process". Do NOT use to record the demo itself — that requires system access only a functional consultant has — and do NOT use to QA finished training decks or storyboards, which is the training-qa-agent skill's job.
---

# Training Video Generator

Takes a screen recording a functional consultant made of a live system, and produces
everything needed to turn it into a training video in Synthesia: a scene map, narration that
fits the footage, annotation copy, avatar placement, and a build sheet the practitioner works
through in the editor.

**The point of this skill is that the narration provably matches the screen.** Anyone can
write a voiceover for a demo. What makes this worth running is that every sentence asserting
something about the system traces to a keyframe someone actually looked at, and every second
of the recording is accounted for. Both are checked in Stage 4, and neither is optional.

## Who does what, and why it is split this way

| Step | Owner | Why |
|---|---|---|
| Recording the demo | **Functional consultant** | The client system is behind their credentials. This skill never simulates a screen it has not been shown. |
| Reading the footage, writing the script | **This skill** | Slow, error-prone, and the part where accuracy actually matters |
| Compositing, avatar, voice, render | **Synthesia** | It ingests a screen recording, splits it into scenes, and places a Personal Avatar as a picture-in-picture with the background removed |
| Confirming the narration is factually right | **The consultant again** | They are the only one who knows the system |

Hand output over as **a draft for practitioner review**, never as a finished training asset.
Say so explicitly when you deliver it.

## MVP scope (read this before promising anything)

This is v0.1, built as a proof of concept for a team demo — one convincing module, not
production volume.

| In scope | Out of scope (v0.1) |
|---|---|
| One module, one recording per run | Batching modules, a shared glossary across modules |
| Scene map read from extracted keyframes | Speech recognition of the recording |
| Narration fitted to measured scene durations | Frame-accurate timing control inside the editor |
| Annotation copy and placement as instructions | Rendering annotations ourselves |
| A build sheet for the Synthesia editor | Driving Synthesia by API (needs Creator tier — see `reference/synthesia-build.md`) |
| Mechanical audit of script against footage | SCORM/LMS packaging, multi-language, branching video |

## Pipeline

```
  Stage 1  INGEST   demo.mp4 ──▶ capture_map.json
  Stage 2  SCRIPT   capture_map + objectives ──▶ video_script.json
  Stage 3  SHEET    video_script ──▶ build_sheet.md + scenes/*.txt + trim_list.csv
                    ······ practitioner assembles in Synthesia ······
  Stage 4  QA       ──▶ qa_report.md
```

Each stage writes a file, so a run can be resumed, inspected or re-run from any stage. Never
jump from a recording straight to a build sheet — the intermediate artifacts are what make the
output auditable, and they are what makes a later switch to the Synthesia API cheap.

### Run workspace

Create `videos/<module-slug>-<YYYYMMDD>/` in the user's current working directory:

```
videos/pr-creation-20260813/
├── inputs/            demo.mp4, guide_transcript.txt
├── frames/            extracted keyframes + contact sheet
├── capture_map.json   Stage 1
├── video_script.json  Stage 2
├── build_sheet.md     Stage 3
├── scenes/S01.txt …   Stage 3
├── trim_list.csv      Stage 3
└── qa_report.md       Stage 4
```

## Stage 1 — Ingest and read the capture

Check the toolchain first, then segment:

```bash
python scripts/preflight.py
python scripts/ingest_capture.py inputs/demo.mp4 -o capture_map.json --frames frames/
```

`ingest_capture.py` ffprobes the recording, finds scene boundaries with ffmpeg scene
detection, extracts one keyframe per scene plus a contact sheet, and writes every scene as
`read_status: "unread"`.

**Then read the frames.** Open every extracted keyframe and fill in `screen`, `action` and
`observed` for each scene, flipping `read_status` to `"read"`. This is the whole basis of the
skill's accuracy claim — a scene left `unread` cannot carry narration, and Stage 4 fails the
run if one does.

Record only what the frame establishes. "The Procurement group is visible" is an observation;
"the user has the Requisitioner role" is an inference and belongs in `[GAP]` if the narration
needs it.

### Dispositions

Every scene gets `keep`, `cut` or `accelerate`. `cut` and `accelerate` need a stated reason —
footage is never dropped silently. Cut dead air, mis-clicks, and **anything showing production
data, personal data or a real client name**; that last one is a hard stop, not a judgement
call. Accelerate loading spinners.

### The guide track

Ask the consultant to talk through the steps while recording — rough, unscripted, no retakes.
That commentary is the SME knowledge the narration needs. This skill has no speech
recognition, but **Synthesia transcribes every upload automatically**: the practitioner
uploads the raw recording, copies the transcript back to `inputs/guide_transcript.txt`, and
narration gets written from it. The avatar's voice replaces the guide track in the final video.

If the module was recorded silent, say so when handing over — the narration then rests on the
frames alone and needs closer review from the consultant.

## Stage 2 — Script to the footage

Write `video_script.json` against `schemas/video_script.schema.json`. Set objectives first;
every `keep` scene maps to at least one.

### Narration rules

- **Write to the word budget.** `fit_narration.py` computes it from each scene's measured
  duration at 130–165 wpm — a training pace, not a conversational one. A 7.7s scene takes
  roughly 17–21 words. Overrunning is not a style problem: it is precisely what
  desynchronises the voice from the screen, and it is checked mechanically.
- **Narrate the action, not the interface.** "Select Create Purchase Requisition" beats
  "click the button labelled Create Purchase Requisition in the upper left".
- **Say what the learner should do, in the order they will do it.** Present tense, second
  person, one action per sentence.
- **Never narrate something the frame does not show.** If a step needs a claim the footage
  does not establish, mark the scene `gap: true` with a `gap_note`. A plausible-sounding
  sentence is worse than a visible hole, because nobody will catch it later.
- **Fix terminology once, in the glossary, and never drift.** Legacy system names and informal
  shorthand are the commonest defect in system training — the `training-qa-agent` skill's
  system-training lens exists largely for this.
- **Write for a cloned voice.** Spell out acronyms the first time. Break long sentences with
  full stops rather than commas; TTS handles short declaratives far better. Write transaction
  codes as the avatar should say them.

### Annotation types

| Type | Use it for | Keep it to |
|---|---|---|
| `highlight` | Boxing the control being acted on | One per scene — two boxes means the learner does not know where to look |
| `callout` | Naming a field or a value being entered | ~4 words |
| `step_counter` | Orientation in a long procedure | "Step 3 of 7" |
| `lower_third` | Presenter name and role | Intro and outro only |

**Annotation copy must never restate the narration.** On-screen text duplicating the spoken
line splits attention and teaches nothing; it should name the object being acted on. Every
annotation needs to be readable at its duration — roughly 0.4s per word, minimum 1.5s.

### Avatar placement

The avatar appears at the intro, at section transitions and at the close — **not parked
bottom-right for the whole runtime**. A talking head competes with the screen exactly when the
learner is trying to follow a click path. It also costs credit on every second of runtime.
`role` drives the default (`visible` on intro/transition/outro, hidden on step); override
per scene where a step genuinely benefits from a presenter.

Check the fit before going near the editor:

```bash
python scripts/fit_narration.py video_script.json
```

## Stage 3 — Build sheet

```bash
python scripts/build_sheet.py capture_map.json video_script.json \
    -o build_sheet.md --scenes scenes/ --trim-list trim_list.csv
```

Produces the build sheet, one paste-ready narration file per scene, and a trim list. The point
is to make the Synthesia session mechanical rather than creative — no rewriting in the editor,
no transcription errors between plan and screen.

Then the practitioner works through `reference/synthesia-build.md`. **Spend the credits last**:
the Synthesia plan caps finished video per month, so get a clean QA report before the first
render.

## Stage 4 — QA

```bash
python scripts/qa_video.py capture_map.json video_script.json -o qa_report.md
```

Four checks, all mechanical, exiting non-zero on any hard failure:

1. **Screen provenance.** Every narrated scene has a `frame_ref` whose scene is `read`, or
   `gap: true`. No third state.
2. **Scene coverage.** Scenes tile the recording without gaps or overlaps; every `keep` scene
   has narration or `silent: true`; every `cut`/`accelerate` has a reason.
3. **Fit.** Narration inside the word budget; annotations readable at their duration; total
   runtime within the module's target.
4. **Consistency.** Glossary `avoid` terms absent; objectives all covered; annotation
   geometry on-canvas and not colliding with a visible avatar.

Then hand `video_script.json` to the **`training-qa-agent`** skill for the instructional-design
pass — objective alignment, sequencing, assessment fit. That checklist is not duplicated here.

Deliver the video, the QA report, and a plain statement of what is still open: the `[GAP]`s,
anything cut, and the reminder that the consultant must confirm the narration is factually
right about their system.

## Notes

- **The recording is the product's raw material, and a bad one cannot be rescued downstream.**
  `reference/recording-guide.md` is what the consultant should get *before* they record. Send
  it early; it costs five minutes and saves a re-record.
- **Scene detection is a starting point, not an oracle.** If boundaries land badly, tune
  `--threshold` and re-run rather than hand-editing timings — the threshold is recorded in
  `capture_map.json` so runs stay comparable.
- **Synthesia's own scene split may not match ours.** Check on the first real module and tune
  once; after that they track closely.
- **Credits are the real constraint, not features.** Finished video is capped per month, and
  every re-render costs the module's full length again. Keep modules short, and split a long
  procedure into several rather than one long one.
- If someone asks this skill to record the demo, or to generate the system screens, stop and
  explain why it cannot — that constraint is the reason the pipeline is shaped this way.
