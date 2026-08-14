# Audio Workflow — From a Recording to Citable Evidence

What to do when an interview arrives as a recording rather than text.

## The one thing to understand first

**Claude cannot listen to audio.** There is no audio input. A recording is not evidence
until it is text, and turning it into text is a tool's job, not a model's. Everything below
is about doing that well enough that the result can be quoted in front of a steering
committee.

## Decision: where does the transcript come from?

```
Recording exists
      │
      ├─ Was it recorded on Teams / Zoom / Meet / Otter / Granola?
      │        └─ YES ──▶ export their transcript ────────────────▶ BEST. Stop here.
      │                    (speaker labels + correct name spellings)
      │
      ├─ Only a raw audio file?
      │        └─ transcribe_interview.py ──▶ attribute ──▶ ingest   GOOD
      │
      └─ Tempted by a cloud ASR service?
               └─ read "Confidentiality" below first ─────────────  A DECISION, NOT A DEFAULT
```

### Always ask for the platform transcript first

Teams, Zoom, Meet and most AI note-takers generate a transcript automatically. It beats
machine transcription on the two things this work depends on:

- **Speaker labels.** The platform knows who was in the meeting. Attribution decides whether
  a statement is testimony, a claim, design intent or hearsay — see `interview-evidence.md`
  §1 — and no local ASR tool can give it to you.
- **Correct name spellings**, for the same reason.

Consultants often have recordings and don't realise the transcript was generated alongside.
It costs nothing and takes a minute to export. Ask explicitly.

### Confidentiality — the cloud ASR decision

Interview recordings from a change programme are among the most sensitive material on the
engagement. They contain named employees discussing job security, describing colleagues,
admitting to control breaches and criticising their own leadership. That is personal data
under UK/EU GDPR, and often material the client would not expect to leave their environment.

Before uploading any of it, check the engagement's data-processing terms, whether consent for
recording extends to third-party processing, and what the interviewees were told. **When in
doubt, transcribe locally.** Raise it with the engagement lead rather than settling it as a
technical convenience — it isn't one.

## The local workflow

### 0. Check the machine is ready

```bash
python3 scripts/transcribe_interview.py --check
```

Reports the backend, the audio decoder and the model cache, with the exact command to fix
whatever is missing. If nothing is installed:

```bash
pip install faster-whisper
```

That pulls in PyAV too, so `.m4a`, `.mp3` and `.mp4` decode without a separate ffmpeg install.

**Air-gapped or offline?** Model weights download once from Hugging Face. Fetch them on a
connected machine, copy `~/.cache/huggingface`, and set `HF_HOME` — or pass `--model-dir`.

### 1. Size the job before starting it

```bash
python3 scripts/transcribe_interview.py recordings/ --dry-run
```

Prints duration per file and a CPU time estimate. Roughly, with the `small` model, expect
**about half to one times realtime on a laptop CPU** — a 60-minute interview takes 30–60
minutes. A batch of eight interviews is an overnight job, not something to sit and watch.

| Model | Relative speed | When |
|---|---|---|
| `tiny` / `base` | Very fast | Deciding whether a recording is worth transcribing properly |
| `small` | **Default** | Interview content. Good enough for extraction. |
| `medium` / `large-v3` | 3–5× slower | Poor audio, heavy accents, or a recording that really matters |

### 2. Transcribe, with the vocabulary loaded

```bash
python3 scripts/transcribe_interview.py recordings/ -o transcripts/ \
    --roster roster.txt \
    --context "Category management as-is discovery for an SAP Ariba implementation."
```

`roster.txt` is one attendee name per line. This matters more than it looks: speech
recognition fails hardest on proper nouns, and the model is far more likely to spell
"Priya Raman" and "Ariba" correctly if it has been told to expect them. The domain
vocabulary in `reference/asr-vocabulary.txt` loads by default — **trim it to the programme
in front of you**, because the model only attends to the last ~200 tokens of prompt and a
bloated list crowds out the terms you care about.

Long recordings checkpoint as they go. If a run dies at minute 80, `--resume` continues from
the checkpoint instead of starting over.

You get four files per recording:

| File | Purpose |
|---|---|
| `.vtt` | The transcript. Feeds straight into `ingest_sources.py`. |
| `.md` | Readable, with quality flags and a summary of what to distrust |
| `.json` | Segments with timings and per-segment confidence metrics |
| `.turns.csv` | The attribution worksheet — the next step |

### 3. Attribute the turns

**This is not optional if you intend to quote anything.** Machine transcription produces no
speaker labels, and an unattributed transcript cannot distinguish the person who does the
work from someone repeating what they were told.

Open the `.turns.csv`, play the audio at 1.5–2×, and fill the `speaker` column. For a
60-minute interview this takes about 10 minutes, because you are matching voices to turns,
not typing. Leave a cell blank where you genuinely cannot tell — that is a real answer, and
the tool records it as unattributed rather than guessing.

```bash
python3 scripts/transcribe_interview.py --apply-speakers transcripts/rec.turns.csv
```

The worksheet is authoritative: blanking a cell clears a previous label, so a
mis-attribution can be retracted.

### 4. Ingest and use

```bash
python3 scripts/ingest_sources.py transcripts/ -o ingested/
```

From here it is the normal path — `interview-evidence.md` for reading it, then
`extraction-guide.md` for building the register.

## Reading a machine transcript — what changes

Everything in `interview-evidence.md` applies, plus three cautions specific to ASR output:

- **The quality flags are there to be used.** The `.md` lists turns the model was unsure
  about, and turns showing the repetition signature of a hallucination. Listen back before
  quoting any of them. A fabricated sentence in a steering-committee pack is worse than no
  quote at all.
- **Every figure is suspect.** The tool lists turns containing quantities — in digits *or*
  spelled out, because people say "a hundred and fifty", not "150". Corroborate each one
  against a document before it drives a headcount, an audience size or an effort estimate.
  If it cannot be corroborated, the register row is Low confidence with an open question.
- **Names and acronyms are spellings to verify, not facts.** Even with the vocabulary loaded,
  treat every system name, module name and person's name as provisional.

## Consent and attribution in the deliverable

Two things to confirm before any of this material reaches a workbook:

- **Interviewees knew they were recorded**, and what it would be used for. A finding that
  quotes someone who believed they were speaking off the record is a problem however good
  the finding is.
- **Quote by role, not by name.** "Category Manager, INT-03 @00:01:08", not the person's
  name. The register goes to a committee that may include their manager. Names stay in your
  working transcript for attribution; they do not go in the deliverable.

## When it fails

| Symptom | What it means |
|---|---|
| `No transcription backend installed` | `pip install faster-whisper` — or get the platform transcript instead |
| Download fails / proxy 403 | Model weights are blocked. Fetch on another machine and set `HF_HOME`. |
| `.m4a`/`.mp3` fails, `.wav` works | No audio decoder. `pip install av`, or install ffmpeg. |
| Garbled output, many flags | Poor audio. Try `--model medium`, and check `--language` if it misdetected. |
| Long stretches of repeated words | Whisper hallucinating on silence. Flagged as `possible-repetition`; delete those turns. |
| Run died part-way | Re-run with `--resume`. |

**An untranscribed recording is a gap in the assessment, not a technicality.** If a recording
cannot be transcribed, say so at handover and name the stakeholder group whose evidence is
therefore missing.
