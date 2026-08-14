# Source Ingestion — Getting Client Material Into a Readable State

Clients hand over whatever they have: Word documents, PowerPoint blueprints, PDF specs,
Signavio exports, spreadsheets of headcount, Teams recordings, and a folder of notes someone
typed on their phone. This is how to get all of it into a state you can actually read, with a
stable reference per source so every register row can cite where it came from.

## The one-command path

```bash
python3 scripts/ingest_sources.py /path/to/client/documents -o ingested/
```

Produces:

| Output | What it is |
|---|---|
| `ingested/<REF>__<name>.md` | One readable file per source, with a provenance header |
| `ingested/sources.json` | The manifest — paste into `meta.source_documents` |
| `ingested/INGEST_REPORT.md` | What was read, what was skipped, what needs attention |

Standard library only, so it runs anywhere without a setup ritual. `.xlsx` needs `openpyxl`,
which the generator needs anyway.

**Then correct `sources.json` by hand.** The script guesses `type` from the file extension; only
a person can tell interview notes from a functional specification from an org design pack.
Fix the types and titles, add dates and participants. This takes two minutes and it is what makes
the Traceability sheet worth having.

## What handles what

| Format | Handling |
|---|---|
| `.docx` | Text with heading levels and tables preserved, in document order |
| `.pptx` | Slide by slide, **including speaker notes** — which routinely carry the reasoning the slide omits |
| `.xlsx` `.csv` `.tsv` | Sheet dumps, truncated at 400 populated rows per sheet |
| `.vtt` `.srt` | Speaker turns with timestamps — see below |
| `.bpmn` `.xml` | Pools, **lanes**, activities by lane, sequence flow, documentation notes |
| `.txt` `.md` `.json` `.rtf` | Passthrough, with encoding detection |
| **`.pdf`, images** | **Not extracted — read these with the Read tool** |
| **Audio** | **Needs a transcript first** — see below |

### Why PDFs and images go to the Read tool

Claude reads PDFs and images natively, including page layout, process diagrams, org charts and
scanned annotations. A text extractor throws all of that away, and on a CIA the diagram is often
the most informative thing in the document. The script lists them in the report as
`read_natively` so they don't get forgotten — open each one directly.

### Why BPMN is worth extracting properly

A process model's **lanes are the impacted roles**. That mapping — lane → who performs this
activity → who is impacted by it changing — is the single most useful thing a process model
gives a change impact assessment, and it's the reason the extractor groups activities by lane
rather than dumping the XML. Sequence flow gives you the hand-offs; `documentation` elements
often carry the modeller's own notes about what is still undecided.

## Audio: the honest position

**Claude cannot listen to audio.** There is no audio input. Any voice recording must become text
first, and that has to happen with a tool. Three routes, in order of preference:

### 1. The meeting platform's own transcript — almost always the right answer

Teams, Zoom, Google Meet, Otter, Granola and most AI note-takers already produce a transcript.
Export it as `.vtt` (best — timestamps and speaker labels) or `.docx`, drop it in the source
folder, re-run the ingest.

This beats machine transcription on the things that matter most to a CIA:

- **Speaker labels**, because the platform knows the attendee roster. Attribution is what lets
  you tell testimony from hearsay — see `interview-evidence.md` §1.
- **Correctly spelled names**, for the same reason.
- No install, no processing time, no data leaving anywhere it isn't already.

Ask for it explicitly. Consultants often have recordings and don't realise the transcript was
generated automatically alongside.

### 2. Local transcription — when there's only a raw recording

Use the dedicated tool; **`reference/audio-workflow.md` covers this properly.**

```bash
pip install faster-whisper
python3 scripts/transcribe_interview.py --check              # is the machine ready?
python3 scripts/transcribe_interview.py recordings/ -o transcripts/ --roster roster.txt
```

`ingest_sources.py --transcribe` runs the same tool inline if you'd rather do it in one pass,
but running it directly gets you roster and vocabulary control, a time estimate before you
commit, and the attribution worksheet.

Runs entirely on the machine. Audio decoding is bundled (PyAV), so no separate ffmpeg install.
Model weights download once on first use.

| Model | Speed on CPU | Use when |
|---|---|---|
| `tiny` / `base` | Fast | Checking whether a recording is worth transcribing at all |
| `small` | ~1-2× realtime | **Default.** Good enough for interview content |
| `medium` / `large-v3` | Slow | A recording that genuinely matters and has poor audio |

**What you lose:** no speaker labels. Machine transcription cannot tell who is talking, and
attribution is the first discipline in reading interview evidence. The tool emits a turn
worksheet for exactly this — fill the speaker column while skimming the audio (about 10 minutes
for a 60-minute interview), then `--apply-speakers` merges it back in. Leave a cell blank where
you genuinely can't tell; that is a real answer and it is recorded as unattributed.

**Budget the time.** A 60-minute interview on `small` takes roughly 30–60 minutes on a laptop
CPU. Transcribe overnight rather than blocking a working session.

### 3. A cloud ASR service — a decision, not a default

Faster and more accurate, and it sends the recording to a third party.

**Interview recordings from a change programme are among the most sensitive material on the
engagement.** They contain named employees discussing job security, describing colleagues,
admitting to control breaches, and criticising their own leadership. That is personal data under
UK/EU GDPR, and it is often material the client would not expect to leave their environment.

Before uploading any of it, check: the engagement's data-processing terms, whether the client's
consent for recording extends to third-party processing, and the interviewees' own understanding
of who would hear it. **If in doubt, use route 1 or 2.** Raise it with the engagement lead
rather than deciding it as a technical convenience — it isn't one.

### Consent and note-taking

Two things worth confirming before the material is used, whatever the route:

- **Interviewees were told the session was recorded**, and what it would be used for. A CIA row
  that quotes someone who thought they were speaking off the record is a problem regardless of
  how good the finding is.
- **Attribution in the deliverable.** Quotes in a CIA should be attributed by role, not by name
  — "Category Manager, INT-04" not "Tom Beckett". The register goes to a steering committee that
  may include the person's manager. Keep names in the ingested transcript for your own
  attribution work; keep them out of the workbook.

## After ingestion

1. Correct `type` and `title` in `sources.json`, add dates and participants.
2. **Read every extracted file in full.** Open the PDFs and images with the Read tool.
3. Read transcripts with `interview-evidence.md` open — it is a different job from reading notes.
4. Build the register per `extraction-guide.md`, citing the refs, with timestamps for transcripts
   (`INT-04 @00:23:15`).
5. **Report what couldn't be read.** An unreadable source, an untranscribed recording, or a
   document nobody supplied is a gap in the assessment. Say so at handover — the generator warns
   about declared documents that no row cites, but it cannot know about a document that was never
   handed over.
