#!/usr/bin/env python3
"""
Transcribe interview and workshop recordings into attributed transcripts a CIA can cite.

    python3 transcribe_interview.py --check                    # what's installed, what's missing
    python3 transcribe_interview.py rec.m4a --dry-run          # duration + time estimate
    python3 transcribe_interview.py rec.m4a -o transcripts/
    python3 transcribe_interview.py recordings/ -o transcripts/ --roster roster.txt
    python3 transcribe_interview.py --apply-speakers rec.turns.csv

Built for interview evidence, not for captions. Three things follow from that:

  * **Names and jargon are biased in, not hoped for.** ASR reliably mangles exactly the
    vocabulary a change impact assessment runs on — system names, module names, acronyms
    and the names of people in the room. Pass a roster and a vocabulary file and they are
    fed to the model as context.
  * **Doubt is surfaced, not hidden.** Segments the model was unsure about, and segments
    showing the repetition signature of a whisper hallucination, are flagged inline. A
    quote you are going to put in front of a steering committee needs to be one the model
    was actually confident about.
  * **Attribution is a first-class step.** Machine transcription cannot tell who is
    speaking, and who said something decides whether it is testimony, a claim, design
    intent or hearsay. The tool emits a turn worksheet, you label it while skimming the
    audio, and `--apply-speakers` merges the labels back in.

Output per recording:
    <name>.vtt        speaker-ready transcript — feeds straight into ingest_sources.py
    <name>.md         readable, with confidence flags and a quality summary
    <name>.json       segments with timings and per-segment confidence metrics
    <name>.turns.csv  attribution worksheet — fill the speaker column, then --apply-speakers

Long recordings checkpoint as they go, so a 90-minute interview that fails at minute 80
resumes instead of starting over.

See ../reference/audio-workflow.md for the end-to-end workflow, and
../reference/interview-evidence.md for reading the result as evidence.
"""

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import textwrap
import wave
from datetime import datetime, timedelta

AUDIO_EXT = {".m4a", ".mp3", ".wav", ".mp4", ".aac", ".ogg", ".flac", ".wma", ".opus", ".webm"}

# Whisper quality heuristics. These are the standard thresholds — a segment failing one is
# not necessarily wrong, but it is not something to quote without listening back.
LOW_LOGPROB = -1.0        # model's own average token confidence
HIGH_NO_SPEECH = 0.6      # probably not speech at all
HIGH_COMPRESSION = 2.4    # repetition signature: whisper looping on silence or noise

TURN_GAP_SECONDS = 2.0    # pause long enough to treat as a change of turn
CHECKPOINT_EVERY = 25     # segments between partial writes

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_VOCAB = os.path.join(HERE, "..", "reference", "asr-vocabulary.txt")


# --------------------------------------------------------------------------------------
# Environment
# --------------------------------------------------------------------------------------

def detect_backends():
    """What can actually transcribe on this machine, best first."""
    found = []

    try:
        import faster_whisper  # noqa: F401
        found.append({
            "id": "faster-whisper",
            "detail": f"faster-whisper {getattr(faster_whisper, '__version__', '?')}",
            "quality": "best local option; ~1-2x realtime on CPU",
        })
    except ImportError:
        pass

    try:
        import whisper  # noqa: F401
        found.append({
            "id": "openai-whisper",
            "detail": "openai-whisper (reference implementation)",
            "quality": "slower than faster-whisper, same models",
        })
    except ImportError:
        pass

    for exe in ("whisper-cli", "whisper-cpp", "main"):
        p = shutil.which(exe)
        if p and exe != "main":
            found.append({"id": "whisper.cpp", "detail": f"{exe} at {p}",
                          "quality": "fast, no Python dependencies; needs a .bin model"})
            break
    return found


def detect_decoder():
    """Can we read compressed audio? faster-whisper bundles PyAV; ffmpeg is the fallback."""
    try:
        import av
        return f"PyAV {av.__version__} (bundled — no ffmpeg needed)"
    except ImportError:
        pass
    if shutil.which("ffmpeg"):
        return "ffmpeg on PATH"
    return None


def cmd_check():
    print("\n  Audio transcription environment\n" + "  " + "─" * 58)

    backends = detect_backends()
    if backends:
        print("\n  Transcription backend")
        for b in backends:
            print(f"    ✓ {b['id']:16} {b['detail']}")
            print(f"      {'':16} {b['quality']}")
    else:
        print("\n  Transcription backend")
        print("    ✗ none installed")
        print("\n      Install one:")
        print("        pip install faster-whisper        # recommended")
        print("        pip install openai-whisper        # alternative")

    dec = detect_decoder()
    print("\n  Audio decoding")
    print(f"    {'✓ ' + dec if dec else '✗ none — needed for .m4a/.mp3/.mp4 (pip install av, or install ffmpeg)'}")

    print("\n  Model weights")
    cache = os.environ.get("HF_HOME") or os.path.expanduser("~/.cache/huggingface")
    if os.path.isdir(cache):
        models = []
        for root, dirs, files in os.walk(cache):
            for d in dirs:
                if "whisper" in d.lower():
                    models.append(d)
        if models:
            print(f"    ✓ cached in {cache}")
            for m in sorted(set(models))[:8]:
                print(f"        {m}")
        else:
            print(f"    – cache exists at {cache}, no whisper models yet")
    else:
        print(f"    – no cache yet; the first run downloads the model (~500 MB for `small`)")
    print("      Offline/air-gapped: download once on a connected machine, copy the cache,")
    print("      and set HF_HOME to point at it.")

    ok = bool(backends) and bool(dec)
    print("\n  " + "─" * 58)
    if ok:
        print("  Ready. Try:  transcribe_interview.py <recording> --dry-run\n")
    else:
        print("  Not ready — see above.")
        print("  You may not need any of it: if the interview was recorded on Teams, Zoom or")
        print("  Meet, export the transcript the platform already made. It has speaker labels")
        print("  and correct name spellings, which machine transcription cannot give you.\n")
    return 0 if ok else 1


# --------------------------------------------------------------------------------------
# Audio probing
# --------------------------------------------------------------------------------------

def probe_audio(path):
    """Duration in seconds plus whatever else we can learn, without a full decode."""
    info = {"path": path, "size_mb": os.path.getsize(path) / 1e6, "duration": None,
            "channels": None, "sample_rate": None, "how": None}

    if path.lower().endswith(".wav"):
        try:
            with wave.open(path) as w:
                info.update(duration=w.getnframes() / float(w.getframerate()),
                            channels=w.getnchannels(), sample_rate=w.getframerate(),
                            how="wave (stdlib)")
                return info
        except Exception:
            pass

    try:
        import av
        with av.open(path) as c:
            if c.duration:
                info["duration"] = c.duration / 1_000_000
            st = next((s for s in c.streams if s.type == "audio"), None)
            if st is not None:
                info["channels"] = st.channels
                info["sample_rate"] = st.rate
            info["how"] = "PyAV"
            return info
    except Exception:
        pass

    if shutil.which("ffprobe"):
        try:
            out = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format",
                 "-show_streams", path], capture_output=True, text=True, timeout=60)
            data = json.loads(out.stdout)
            info["duration"] = float(data.get("format", {}).get("duration", 0)) or None
            a = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), {})
            info["channels"] = a.get("channels")
            info["sample_rate"] = int(a["sample_rate"]) if a.get("sample_rate") else None
            info["how"] = "ffprobe"
        except Exception:
            pass
    return info


def fmt_hms(seconds):
    if seconds is None:
        return "unknown"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# Rough CPU multipliers vs. realtime — used only for the estimate shown before a long run.
SPEED = {"tiny": 0.15, "base": 0.25, "small": 0.6, "medium": 1.6, "large-v3": 3.2, "turbo": 0.4}


def estimate_minutes(duration_s, model):
    if not duration_s:
        return None
    return duration_s / 60 * SPEED.get(model, 0.6)


# --------------------------------------------------------------------------------------
# Prompting — bias the model toward the vocabulary this domain actually uses
# --------------------------------------------------------------------------------------

def load_lines(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [l.strip() for l in fh if l.strip() and not l.startswith("#")]


def build_prompt(roster, vocab, extra=None):
    """
    Whisper's initial_prompt conditions decoding. Feeding it the names in the room and the
    programme's own jargon measurably reduces the error class that matters most here —
    mangled system names, module names, acronyms and people's names.

    Kept under ~200 tokens: the model only attends to the last ~224 tokens of prompt, and
    an over-long prompt crowds out the terms you care about.
    """
    parts = []
    if roster:
        parts.append("Speakers: " + ", ".join(roster) + ".")
    if vocab:
        parts.append("Terms: " + ", ".join(vocab) + ".")
    if extra:
        parts.append(extra.strip())
    prompt = " ".join(parts).strip()

    words = prompt.split()
    if len(words) > 180:
        prompt = " ".join(words[:180])
    return prompt or None


# --------------------------------------------------------------------------------------
# Segment quality
# --------------------------------------------------------------------------------------

def flag_segment(seg):
    """Reasons this segment shouldn't be quoted without listening back. Empty = clean."""
    flags = []
    lp = seg.get("avg_logprob")
    ns = seg.get("no_speech_prob")
    cr = seg.get("compression_ratio")
    if lp is not None and lp < LOW_LOGPROB:
        flags.append("low-confidence")
    if ns is not None and ns > HIGH_NO_SPEECH:
        flags.append("maybe-not-speech")
    if cr is not None and cr > HIGH_COMPRESSION:
        flags.append("possible-repetition")
    return flags


# Spoken figures usually arrive as words, not digits — "a hundred and fifty events",
# "nineteen years", "four percent". A digits-only check would miss nearly every number
# actually said out loud, which is the whole class of claim that needs corroborating
# before it drives a headcount or an effort estimate.
NUMBER_WORDS = {
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
    "eighteen", "nineteen", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
    "eighty", "ninety", "hundred", "hundreds", "thousand", "thousands", "million",
    "millions", "billion", "dozen", "half", "quarter", "third", "double", "triple",
    "percent", "percentage", "per cent", "fte", "headcount", "roughly", "approximately",
}
_WORD_RE = None


def has_quantity(text):
    """True if the turn states a figure, in digits or in words."""
    global _WORD_RE
    if any(ch.isdigit() for ch in text):
        return True
    import re as _re
    if _WORD_RE is None:
        _WORD_RE = _re.compile(
            r"\b(" + "|".join(sorted((w.replace(" ", r"\s+") for w in NUMBER_WORDS),
                                     key=len, reverse=True)) + r")\b", _re.I)
    return bool(_WORD_RE.search(text))


# --------------------------------------------------------------------------------------
# Backends
# --------------------------------------------------------------------------------------

def run_faster_whisper(path, model_size, language, prompt, model_dir, on_segment):
    from faster_whisper import WhisperModel
    kwargs = {"device": "cpu", "compute_type": "int8"}
    if model_dir:
        kwargs["download_root"] = model_dir
    model = WhisperModel(model_size, **kwargs)
    segments, info = model.transcribe(
        path, language=language, initial_prompt=prompt, vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=False,  # limits hallucination drift on long recordings
    )
    meta = {"language": info.language, "language_probability": info.language_probability,
            "duration": info.duration, "backend": "faster-whisper", "model": model_size}
    for s in segments:
        on_segment({
            "start": s.start, "end": s.end, "text": (s.text or "").strip(),
            "avg_logprob": getattr(s, "avg_logprob", None),
            "no_speech_prob": getattr(s, "no_speech_prob", None),
            "compression_ratio": getattr(s, "compression_ratio", None),
        })
    return meta


def run_openai_whisper(path, model_size, language, prompt, model_dir, on_segment):
    import whisper
    model = whisper.load_model(model_size, download_root=model_dir or None)
    result = model.transcribe(path, language=language, initial_prompt=prompt, verbose=False)
    for s in result.get("segments", []):
        on_segment({
            "start": s.get("start"), "end": s.get("end"), "text": (s.get("text") or "").strip(),
            "avg_logprob": s.get("avg_logprob"),
            "no_speech_prob": s.get("no_speech_prob"),
            "compression_ratio": s.get("compression_ratio"),
        })
    return {"language": result.get("language"), "language_probability": None,
            "duration": None, "backend": "openai-whisper", "model": model_size}


BACKENDS = {"faster-whisper": run_faster_whisper, "openai-whisper": run_openai_whisper}


# --------------------------------------------------------------------------------------
# Turns and outputs
# --------------------------------------------------------------------------------------

def segments_to_turns(segments, gap=TURN_GAP_SECONDS):
    """
    Group segments into speaking turns on pause length.

    This is not diarization — it cannot tell you *who* is speaking, only where one stretch
    of speech probably ends and another begins. That is exactly what the attribution
    worksheet needs: a list of moments to put a name against.
    """
    turns = []
    for seg in segments:
        if not seg.get("text"):
            continue
        if turns and seg["start"] - turns[-1]["end"] < gap:
            t = turns[-1]
            t["end"] = seg["end"]
            t["text"] += " " + seg["text"]
            t["flags"] = sorted(set(t["flags"]) | set(flag_segment(seg)))
        else:
            turns.append({"start": seg["start"], "end": seg["end"], "text": seg["text"],
                          "flags": flag_segment(seg), "speaker": None})
    return turns


def vtt_time(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def write_vtt(path, turns, meta, roster):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("WEBVTT\n\n")
        fh.write("NOTE\n")
        fh.write(f"Machine transcription — {meta.get('backend')} / {meta.get('model')}\n")
        fh.write(f"Generated {datetime.now():%Y-%m-%d %H:%M}\n")
        if roster:
            fh.write(f"Attendees (supplied): {', '.join(roster)}\n")
        fh.write("Speaker labels are NOT machine-derived. Any <v ...> tag below was added by a\n")
        fh.write("person via --apply-speakers; unlabelled turns remain unattributed.\n\n")
        for i, t in enumerate(turns, 1):
            fh.write(f"{i}\n{vtt_time(t['start'])} --> {vtt_time(t['end'])}\n")
            body = t["text"]
            if t.get("speaker"):
                fh.write(f"<v {t['speaker']}>{body}\n\n")
            else:
                fh.write(f"{body}\n\n")


def write_turns_csv(path, turns):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["turn", "start", "end", "speaker", "flags", "text"])
        for i, t in enumerate(turns, 1):
            w.writerow([i, fmt_hms(t["start"]), fmt_hms(t["end"]),
                        t.get("speaker") or "", ";".join(t["flags"]), t["text"]])


def write_markdown(path, turns, meta, roster, probe, quality):
    total_words = sum(len(t["text"].split()) for t in turns)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"# Transcript — {os.path.basename(probe['path'])}\n\n")
        fh.write(f"- **Backend:** {meta.get('backend')} / `{meta.get('model')}`\n")
        lang = meta.get("language")
        lp = meta.get("language_probability")
        fh.write(f"- **Language:** {lang}" + (f" (confidence {lp:.2f})" if lp else "") + "\n")
        fh.write(f"- **Duration:** {fmt_hms(meta.get('duration') or probe.get('duration'))}\n")
        fh.write(f"- **Turns:** {len(turns)}   **Words:** ~{total_words:,}\n")
        fh.write(f"- **Generated:** {datetime.now():%Y-%m-%d %H:%M}\n")
        if roster:
            fh.write(f"- **Attendees (supplied):** {', '.join(roster)}\n")
        fh.write("\n")

        labelled = sum(1 for t in turns if t.get("speaker"))
        if labelled == 0:
            fh.write("> **Not attributed.** Machine transcription cannot tell who is speaking, and\n")
            fh.write("> who said something decides whether it is testimony, a claim, design intent\n")
            fh.write("> or hearsay. Fill the speaker column in the `.turns.csv` and re-run with\n")
            fh.write("> `--apply-speakers` before drawing evidence from this.\n\n")
        elif labelled < len(turns):
            fh.write(f"> **Partly attributed** — {labelled} of {len(turns)} turns carry a speaker.\n")
            fh.write("> Anything drawn from an unattributed turn stays a confidence level lower,\n")
            fh.write("> because you cannot tell testimony from hearsay without knowing who spoke.\n\n")
        else:
            fh.write("> **Attributed by hand** from the turn worksheet — speaker labels are not\n")
            fh.write("> machine-derived. Spot-check any turn you intend to quote.\n\n")
        fh.write("> **Do not bank figures from this transcript.** Numbers, acronyms, system and\n")
        fh.write("> module names are what ASR gets wrong. Corroborate against a document, or\n")
        fh.write("> mark the register row Low confidence.\n\n")

        if quality["flagged"]:
            fh.write(f"## Quality flags — {len(quality['flagged'])} of {len(turns)} turns\n\n")
            fh.write("Listen back before quoting any of these.\n\n")
            fh.write("| Turn | At | Flags | Preview |\n|---:|---|---|---|\n")
            for i, t in quality["flagged"][:40]:
                prev = t["text"][:70].replace("|", "\\|")
                fh.write(f"| {i} | {fmt_hms(t['start'])} | {', '.join(t['flags'])} | {prev}… |\n")
            if len(quality["flagged"]) > 40:
                fh.write(f"\n_… and {len(quality['flagged']) - 40} more; see the JSON._\n")
            fh.write("\n")

        if quality["numeric"]:
            fh.write(f"## Turns containing figures — {len(quality['numeric'])}\n\n")
            fh.write("Every one of these needs corroborating against a document before it drives "
                     "a headcount, an audience size or an effort estimate.\n\n")
            fh.write("| Turn | At | Preview |\n|---:|---|---|\n")
            for i, t in quality["numeric"][:30]:
                prev = t["text"][:80].replace("|", "\\|")
                fh.write(f"| {i} | {fmt_hms(t['start'])} | {prev}… |\n")
            fh.write("\n")

        fh.write("---\n\n## Transcript\n\n")
        for i, t in enumerate(turns, 1):
            who = f"**{t['speaker']}:** " if t.get("speaker") else ""
            flag = f"  `⚠ {', '.join(t['flags'])}`" if t["flags"] else ""
            fh.write(f"**[{fmt_hms(t['start'])}]** {who}{t['text']}{flag}\n\n")


def assess_quality(turns):
    flagged = [(i, t) for i, t in enumerate(turns, 1) if t["flags"]]
    numeric = [(i, t) for i, t in enumerate(turns, 1) if has_quantity(t["text"])]
    return {"flagged": flagged, "numeric": numeric,
            "clean_pct": (100.0 * (len(turns) - len(flagged)) / len(turns)) if turns else 0.0}


def write_json(path, segments, turns, meta, probe, roster):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"source": probe, "meta": meta, "roster": roster,
                   "segments": segments, "turns": turns}, fh, indent=2, ensure_ascii=False)


# --------------------------------------------------------------------------------------
# Attribution merge
# --------------------------------------------------------------------------------------

def cmd_apply_speakers(csv_path, vtt_path=None):
    """Merge the speaker column of a filled-in turn worksheet back into the .vtt and .md."""
    if not os.path.exists(csv_path):
        print(f"✗ No such file: {csv_path}")
        return 1
    stem = csv_path[:-len(".turns.csv")] if csv_path.endswith(".turns.csv") \
        else os.path.splitext(csv_path)[0]
    vtt_path = vtt_path or stem + ".vtt"
    json_path = stem + ".json"
    if not os.path.exists(vtt_path):
        print(f"✗ Expected transcript alongside the worksheet: {vtt_path}")
        return 1

    with open(csv_path, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    # The worksheet is authoritative for attribution, including its blanks: an analyst
    # clearing a cell means "I can't tell who this was", and that has to be undoable.
    # Otherwise a mis-attribution can never be retracted, which is the wrong default when
    # the whole point of the column is separating testimony from hearsay.
    labels = {}
    for r in rows:
        try:
            n = int(str(r.get("turn", "")).strip())
        except (ValueError, TypeError):
            continue
        labels[n] = (r.get("speaker") or "").strip() or None
    named = {n: v for n, v in labels.items() if v}
    if not named:
        print("✗ No speaker labels found in the worksheet — fill the `speaker` column first.")
        return 1

    if not os.path.exists(json_path):
        print(f"✗ Expected {json_path} (written alongside the transcript) to rebuild from.")
        return 1
    with open(json_path, encoding="utf-8") as fh:
        data = json.load(fh)
    turns = data["turns"]
    for n, name in labels.items():
        if 1 <= n <= len(turns):
            turns[n - 1]["speaker"] = name          # None clears a previous label

    roster = sorted(named.values() and set(named.values()))
    write_vtt(vtt_path, turns, data["meta"], roster)
    write_markdown(stem + ".md", turns, data["meta"], roster, data["source"],
                   assess_quality(turns))
    data["turns"] = turns
    data["roster"] = roster
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)

    unlabelled = len(turns) - len([t for t in turns if t.get("speaker")])
    print(f"\n✓ Applied {len(named)} speaker labels across {len(turns)} turns")
    print(f"  Speakers: {', '.join(roster)}")
    if unlabelled:
        print(f"  ⚠  {unlabelled} turns still unattributed — anything drawn from those stays "
              f"lower confidence")
    print(f"  Updated: {os.path.basename(vtt_path)}, {os.path.basename(stem + '.md')}\n")
    print(f"  Next: run ingest_sources.py over the folder containing {os.path.basename(vtt_path)}\n")
    return 0


# --------------------------------------------------------------------------------------
# Transcription driver
# --------------------------------------------------------------------------------------

def transcribe_one(path, out_dir, args, prompt, roster):
    name = os.path.splitext(os.path.basename(path))[0]
    stem = os.path.join(out_dir, name)
    probe = probe_audio(path)

    print(f"\n  {os.path.basename(path)}")
    print(f"    duration {fmt_hms(probe['duration'])}  |  {probe['size_mb']:.1f} MB"
          + (f"  |  probed with {probe['how']}" if probe["how"] else "  |  duration unknown"))
    est = estimate_minutes(probe["duration"], args.model)
    if est:
        print(f"    estimated ~{est:.0f} min on CPU with `{args.model}`")

    if args.dry_run:
        return {"path": path, "status": "dry-run", "duration": probe["duration"]}

    ckpt = stem + ".partial.json"
    segments = []
    if args.resume and os.path.exists(ckpt):
        with open(ckpt, encoding="utf-8") as fh:
            segments = json.load(fh).get("segments", [])
        if segments:
            print(f"    resuming — {len(segments)} segments already transcribed "
                  f"(to {fmt_hms(segments[-1]['end'])})")

    start_wall = datetime.now()
    state = {"n": len(segments), "last_report": 0.0}

    def on_segment(seg):
        segments.append(seg)
        state["n"] += 1
        if state["n"] % CHECKPOINT_EVERY == 0:
            with open(ckpt, "w", encoding="utf-8") as fh:
                json.dump({"segments": segments}, fh)
            pos = seg["end"]
            if probe["duration"]:
                # Clamped: a VBR mp3 can decode longer than its header claims, and a
                # progress bar reading 138% with "-0 min left" just looks broken.
                pct = min(100.0, 100.0 * pos / probe["duration"])
                elapsed = (datetime.now() - start_wall).total_seconds()
                rate = pos / elapsed if elapsed > 0 else 0
                remain = max(0.0, (probe["duration"] - pos) / rate) if rate > 0 else 0
                print(f"    {pct:5.1f}%  at {fmt_hms(pos)}  "
                      f"~{remain/60:.0f} min left", flush=True)
            else:
                print(f"    {state['n']} segments  at {fmt_hms(pos)}", flush=True)

    runner = BACKENDS[args.backend]
    try:
        meta = runner(path, args.model, args.language, prompt, args.model_dir, on_segment)
    except KeyboardInterrupt:
        with open(ckpt, "w", encoding="utf-8") as fh:
            json.dump({"segments": segments}, fh)
        print(f"\n    interrupted — {len(segments)} segments checkpointed. "
              f"Re-run with --resume to continue.")
        return {"path": path, "status": "interrupted", "segments": len(segments)}
    except Exception as e:
        with open(ckpt, "w", encoding="utf-8") as fh:
            json.dump({"segments": segments}, fh)
        print(f"    ✗ {type(e).__name__}: {e}")
        if segments:
            print(f"      {len(segments)} segments checkpointed; --resume to retry from there.")
        return {"path": path, "status": "failed", "error": f"{type(e).__name__}: {e}"}

    meta.setdefault("duration", probe["duration"])
    meta["prompt_used"] = prompt
    turns = segments_to_turns(segments, args.turn_gap)
    quality = assess_quality(turns)

    write_vtt(stem + ".vtt", turns, meta, roster)
    write_turns_csv(stem + ".turns.csv", turns)
    write_json(stem + ".json", segments, turns, meta, probe, roster)
    write_markdown(stem + ".md", turns, meta, roster, probe, quality)
    if os.path.exists(ckpt):
        os.remove(ckpt)

    took = (datetime.now() - start_wall).total_seconds() / 60
    words = sum(len(t["text"].split()) for t in turns)
    print(f"    ✓ {len(turns)} turns, ~{words:,} words, {took:.0f} min")
    print(f"      {quality['clean_pct']:.0f}% of turns clean"
          + (f"  |  {len(quality['flagged'])} flagged" if quality["flagged"] else "")
          + (f"  |  {len(quality['numeric'])} contain figures" if quality["numeric"] else ""))
    return {"path": path, "status": "ok", "turns": len(turns), "words": words,
            "flagged": len(quality["flagged"]), "stem": stem}


# --------------------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Transcribe interview recordings into attributed transcripts for a CIA.",
        epilog=textwrap.dedent("""
            workflow
              1  transcribe_interview.py rec.m4a -o transcripts/
              2  open transcripts/rec.turns.csv, fill the `speaker` column while skimming
                 the audio (roughly 10 min for a 60-min interview at 2x)
              3  transcribe_interview.py --apply-speakers transcripts/rec.turns.csv
              4  ingest_sources.py transcripts/ -o ingested/

            If the session was recorded on Teams, Zoom or Meet, skip all of this and export
            the transcript the platform already made — it has speaker labels and correct
            name spellings, which machine transcription cannot give you.
        """).strip())
    ap.add_argument("input", nargs="?", help="Audio file or a directory of them")
    ap.add_argument("-o", "--out", default="transcripts", help="Output directory")
    ap.add_argument("--check", action="store_true", help="Report what's installed and exit")
    ap.add_argument("--dry-run", action="store_true", help="Probe and estimate; don't transcribe")
    ap.add_argument("--apply-speakers", metavar="TURNS_CSV",
                    help="Merge a filled-in turn worksheet back into the transcript")
    ap.add_argument("--model", default="small",
                    help="tiny | base | small (default) | medium | large-v3 | turbo")
    ap.add_argument("--backend", default=None, help="Force a backend; default is the best available")
    ap.add_argument("--language", default=None, help="ISO code, e.g. en. Default: auto-detect")
    ap.add_argument("--roster", help="File of attendee names, one per line — improves name spelling")
    ap.add_argument("--vocab", default=DEFAULT_VOCAB,
                    help="File of domain terms, one per line (default: reference/asr-vocabulary.txt)")
    ap.add_argument("--context", help="Extra sentence of context for the model, e.g. the topic")
    ap.add_argument("--model-dir", help="Where model weights live (for offline/air-gapped use)")
    ap.add_argument("--turn-gap", type=float, default=TURN_GAP_SECONDS,
                    help=f"Pause in seconds that starts a new turn (default {TURN_GAP_SECONDS})")
    ap.add_argument("--resume", action="store_true", help="Continue from a checkpoint")
    args = ap.parse_args()

    if args.check:
        return cmd_check()
    if args.apply_speakers:
        return cmd_apply_speakers(args.apply_speakers)
    if not args.input:
        ap.print_help()
        return 1
    if not os.path.exists(args.input):
        print(f"✗ No such file or directory: {args.input}")
        return 1

    if os.path.isdir(args.input):
        files = sorted(os.path.join(args.input, f) for f in os.listdir(args.input)
                       if os.path.splitext(f)[1].lower() in AUDIO_EXT)
    else:
        files = [args.input]
    if not files:
        print(f"✗ No audio files in {args.input}")
        print(f"  Looking for: {', '.join(sorted(AUDIO_EXT))}")
        return 1

    if not args.dry_run:
        available = detect_backends()
        ids = [b["id"] for b in available if b["id"] in BACKENDS]
        if not ids:
            print("\n✗ No transcription backend installed.\n")
            print("  pip install faster-whisper\n")
            print("  Or — better, if the session was recorded on Teams, Zoom or Meet — export")
            print("  the transcript the platform already made. It carries speaker labels and")
            print("  correct name spellings, which machine transcription cannot give you.\n")
            print("  Run --check for full detail.\n")
            return 1
        if args.backend and args.backend not in ids:
            print(f"✗ Backend '{args.backend}' not available. Installed: {', '.join(ids)}")
            return 1
        args.backend = args.backend or ids[0]
        if not detect_decoder() and any(not f.lower().endswith(".wav") for f in files):
            print("\n⚠  No audio decoder found (PyAV or ffmpeg). Compressed formats "
                  "(.m4a/.mp3/.mp4) will fail.\n   pip install av\n")

    roster = load_lines(args.roster)
    vocab = load_lines(args.vocab)
    prompt = build_prompt(roster, vocab, args.context)

    print(f"\n  {len(files)} recording(s)  →  {args.out}/")
    if not args.dry_run:
        print(f"  backend {args.backend} / model `{args.model}`")
        if roster:
            print(f"  roster: {len(roster)} names — biases spelling of who's in the room")
        if vocab:
            print(f"  vocabulary: {len(vocab)} terms — biases system and module names")
        if not roster:
            print("  ⚠  no --roster: names will be spelled phonetically")

    os.makedirs(args.out, exist_ok=True)
    results = [transcribe_one(p, args.out, args, prompt, roster) for p in files]

    ok = [r for r in results if r["status"] == "ok"]
    print("\n  " + "─" * 58)
    if args.dry_run:
        total = sum(r.get("duration") or 0 for r in results)
        print(f"  {len(results)} recording(s), {fmt_hms(total)} total audio")
        est = estimate_minutes(total, args.model)
        if est:
            print(f"  Estimated ~{est:.0f} min to transcribe with `{args.model}` on CPU.")
            print(f"  A long batch is best left running rather than watched.")
        print()
        return 0

    print(f"  {len(ok)}/{len(results)} transcribed\n")
    for r in results:
        if r["status"] != "ok":
            print(f"    ✗ {os.path.basename(r['path'])}: {r.get('error', r['status'])}")
    if ok:
        print("  Next — attribute the turns. Machine transcription can't tell who is speaking,")
        print("  and attribution is what separates testimony from hearsay:\n")
        for r in ok:
            print(f"    1. open {r['stem']}.turns.csv, fill the `speaker` column")
            print(f"    2. python3 {os.path.basename(__file__)} --apply-speakers "
                  f"{r['stem']}.turns.csv")
        print(f"\n    3. python3 ingest_sources.py {args.out} -o ingested/\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
