# Building the module in Synthesia

The editor session should be mechanical. Everything creative was decided in
`video_script.json` and written down in `build_sheet.md`; this is assembly.

> ⚠️ **Verify the figures below against Synthesia's own pages before relying on them.** They
> were gathered from secondary sources because `synthesia.io` was unreachable when this skill
> was written. Plan tiers, credit rates and upload limits change. Anything marked *(verify)*
> has not been read from Synthesia's documentation directly.

---

## One-time setup

Do this once. Every module afterwards inherits it, and consistency across modules is most of
what makes a training library look professional rather than assembled.

### 1. Create the Personal Avatar

Record the source footage for your avatar following Synthesia's guidance — good even lighting,
plain background, neutral expression, and the script they provide. Processing takes about a
business day *(verify)*.

Starter includes 3 Personal Avatars *(verify)*, which is enough for one presenter plus two
alternates or a second language.

**Background removal is included for Personal Avatars** *(verify)*, which is what makes the
corner picture-in-picture work. You do not need to chroma-key anything yourself, and you do
not need a transparent export — Synthesia composites the avatar over the screen recording
inside the editor.

### 2. Build the module template

Create one video you never publish and treat it as the template. Set:

- **Avatar position:** bottom-right, `box` framing, sized so it occupies roughly a quarter of
  the frame width. Drag it into place once and do not move it again — an avatar that changes
  size or corner between scenes reads as sloppy immediately.
- **Annotation text styles:** one style for callouts, one for step counters, one for lower
  thirds. Set the font, size and colour once.
- **Brand colours** for highlight boxes, if there is a brand kit.
- **Captions on.**

`qa_video.py` assumes the avatar occupies a 25%×35% box with a 3% margin in its corner, and
checks that no annotation collides with it. If your template differs materially, adjust
`AVATAR_WIDTH` / `AVATAR_HEIGHT` at the top of that script so the collision check stays honest.

---

## Per-module workflow

### 1. Upload the recording

`Record → Upload screen recording`, and select the consultant's unedited MP4.

Limits: 500MB, 30 minutes *(verify)*. If the recording is over, it should have been split at
recording time — see `recording-guide.md`.

Synthesia will transcribe the audio, strip filler words, and split the recording into scenes.

### 2. Capture the transcript — before anything else

**Copy the transcript out and save it as `inputs/guide_transcript.txt` in the run workspace.**

This is the consultant's spoken walkthrough, and it is the SME knowledge the narration gets
written from. It is easy to skip and annoying to recover. Do it first.

If you are running the pipeline in the intended order you will already have done this, since
Stage 2 needs the transcript to write the script. In that case just confirm nothing changed.

### 3. Reconcile the scene split

Synthesia's scenes and `capture_map.json`'s scenes are produced by different algorithms and
will not match exactly the first time.

- Where Synthesia split something our map keeps whole, merge it.
- Where it kept whole something our map splits, split it.
- If they disagree badly across the board, the detection threshold is wrong: re-run
  `ingest_capture.py --threshold` (lower finds more cuts, higher finds fewer) and regenerate
  the build sheet rather than hand-editing thirty scenes.

Expect to tune this once, on the first module. After that they track closely.

### 4. Apply the trim list

From `trim_list.csv`: delete every `cut` scene, and speed up every `accelerate` scene.

Check the reasons as you go. A scene cut for showing production data is not optional.

### 5. Paste narration, scene by scene

For each scene in `build_sheet.md`, paste from the matching `scenes/S**.txt`.

**Paste — do not retype, and do not edit in the editor.** If a line is wrong, fix
`video_script.json`, re-run `fit_narration.py`, regenerate the build sheet, and paste again.
Editing in place is how the reviewed script and the built video quietly become different
things, and the QA report then attests to something that was never built.

Set the avatar visible or hidden per the sheet. The avatar appears at the intro, at section
transitions and at the close — not throughout.

### 6. Add annotations

Per the sheet. Positions are given as percentages of frame width and height from the top-left,
which is how the editor's own positioning reads.

Keep to one highlight per scene. If the sheet asks for a highlight and a callout together, the
callout labels the same control the box marks.

### 7. Preview before rendering

Watch it through once in preview. You are looking for three things:

- Narration that finishes noticeably before or after its scene does.
- Annotations under the avatar, clipped at an edge, or on screen too briefly to read.
- Anything on screen that should not be there.

**Then render.** Renders cost credits and there is no free re-roll.

### 8. Export and QA

Export MP4 with captions. Then run `qa_video.py` and hand `video_script.json` to the
`training-qa-agent` skill for the instructional pass.

---

## Plan limits and credits

*(All figures verify.)*

| | Starter | Creator |
|---|---|---|
| Finished video | ~10 min/month | ~30 min/month |
| Credits | 1,200/month | 3,600/month |
| Personal Avatars | 3 | 5 |
| API access | **No** | Yes |
| Watermark | Removed | Removed |

One second of standard generated video costs 2 credits, so a minute costs 120. Credits are a
shared pool — dubbing, generated assets and API renders all draw it down.

**Annual billing grants the balance annually rather than monthly.** For training this matters
more than it sounds: production is lumpy, bunching before each go-live, and an annual balance
can be spent in a burst where a monthly one expires unused.

### What this means in practice

- A 5-minute module is half a monthly Starter allowance. Budget roughly two attempts.
- **Every revision re-renders the full module at full cost.** Get the QA report clean first.
- Keep modules to 3–5 minutes. Splitting a long procedure is cheaper *and* better training.

---

## The API, and when it is worth buying

**The API requires Creator or above; Starter has no API access** *(verify)*. There is no
Synthesia MCP connector, so on Starter this pipeline ends at the build sheet by necessity,
not by choice.

If Creator is bought later, the pipeline needs almost no rework — Stages 1, 2 and 4 are
unchanged, and only Stage 3 swaps a build sheet for API calls off the same `video_script.json`.
Three things change in the work, though:

1. **The AI Screen Recorder's auto-transcribe and auto-scene-split are editor features, not
   API ones.** Stage 1 already does its own segmentation, so nothing is lost — but Stage 3
   then has to physically cut the recording into per-scene clips (`ffmpeg -ss/-to -c copy`)
   and upload one asset per scene rather than describing the cuts.
2. **The API creates videos; it does not edit them.** Every revision is a fresh render and a
   fresh charge.
3. **The free SME transcript disappears**, because it comes from the editor's upload
   processing. The consultant's spoken knowledge would need capturing another way.

The API removes the manual editor session, but costs several times more, triples the credit
cap rather than removing it, and hands back a pipeline that must do more work. Worth buying
when the editor session is genuinely the bottleneck — not before.
