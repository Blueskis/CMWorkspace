# Comms Tone

Voice and style rules — the house voice, per-client voice, plain-language rules, and
terminology. Read by `cm-comms-generator` at Stage 2.

## What belongs here

- The firm's own house voice for change comms
- A named client's voice, where it differs and where we have their guidance in writing
- Plain-language rules and reading-age targets
- Terminology: the words a given organisation uses for its own things, and the ones it avoids

## What does not belong here

**Anything the brand profile enforces mechanically.** `banned_words` and `preferred_terms`
live in `brand_profile.json`, where `qa_comms.py` can check them. This folder is for the
guidance a script cannot apply — rhythm, register, what a good opening sounds like, when to
use the second person.

Duplicating a banned-word list here does not make it enforced, and creates two places to
maintain it. Keep the list in the profile and the *reasoning* here.

## Tagging

Tag with `tone` plus the scope: `house-voice`, a client slug, `plain-language`, or a channel
where the guidance is channel-specific.

```bash
python skills/cm-proposal-generator/scripts/retrieve.py kb_index.json \
    --section comms-tone --tags house-voice,email --strict-section --top 3
```
