# Prompt Engineer — self-hosted version

The [claude.ai artifact version](../prompt-engineer.html) can't have both a public
link and live "Polish with Claude" / tailored-questions calls at the same time —
claude.ai bills those calls to whoever's signed in, so a fully public link (no
login) disables them. This folder is the same tool, deployed as a small web app
instead, so the AI calls run through your own Anthropic API key on a backend
you control. Anyone with the link gets the full tool, including Polish.

**What changes vs. the artifact:** nothing in the questionnaire or prompt
assembly. `public/pe-logic.js` is a byte-for-byte copy of the artifact's tested
logic block (see [`../tests/run_tests.mjs`](../tests/run_tests.mjs), which runs
the same 19 cases against both files so they can't silently drift apart).

## What you're accepting by doing this

- **You pay per call, not the viewer.** Every click of Polish or "Get tailored
  questions" bills your Anthropic API key, however many people have the link.
- **Basic rate limiting only.** `api/_lib/rateLimit.js` caps each visitor to 5
  calls/hour per endpoint. It's an in-memory counter local to one serverless
  instance, a soft cap that resets on cold start, not a hard guarantee under
  real concurrent load. If the link gets forwarded widely, consider a shared
  Vercel KV / Upstash Redis-backed limiter instead (same call sites, swap the
  module).
- **The model is `claude-haiku-4-5`**, the cheapest current Claude tier,
  chosen to keep a public-facing feature's cost down. It doesn't accept the
  `output_config.effort` parameter (Opus/Sonnet 5 do), so neither endpoint
  sends one — this model has no "quality dial" of that kind. Change the
  `model` value in `api/polish.js` / `api/tailor.js` if you want higher
  output quality at a higher per-call cost.

## Deploy (Vercel)

1. **Get an Anthropic API key**: console.anthropic.com → Settings → API Keys.
   This is separate, pay-per-token billing from any Claude.ai subscription.
2. **Push this repo to GitHub** (or use the Vercel CLI directly from this
   folder without pushing anywhere — `vercel` handles either).
3. **Import the project in Vercel** (vercel.com/new). When it asks for the
   project's root directory, set it to `prompt-engineer/webapp` — this app
   lives in a subfolder of the CMWorkspace repo, not the repo root.
4. **Add the environment variable**: Project Settings → Environment Variables
   → `ANTHROPIC_API_KEY` → paste the key from step 1. Apply it to Production
   (and Preview if you want preview deploys to work too).
5. **Deploy.** Vercel auto-detects `public/` as static files and `api/*.js` as
   serverless functions — no build step, no framework config needed.
6. You now have one URL. Share it as a plain link; no Claude account needed
   on the visitor's end, and Polish with Claude works for everyone.

## Local development

```bash
npm install
vercel dev   # requires the Vercel CLI: npm i -g vercel
```

`vercel dev` reads `.env` for `ANTHROPIC_API_KEY` (copy `.env.example` to
`.env` and fill it in) and serves `public/` + `api/` exactly as production
does.

## Layout

```
webapp/
├── public/
│   ├── index.html      # markup + CIA-theme styling (matches the artifact)
│   ├── pe-logic.js      # classifier, question bank, prompt assembly — tested, shared
│   └── app.js           # DOM wiring; calls /api/tailor and /api/polish
├── api/
│   ├── tailor.js        # POST { brief, archetypeLabel } -> { questions: string[] }
│   ├── polish.js        # POST { prompt } -> { text }
│   └── _lib/
│       ├── anthropic.js       # lazy Anthropic client from ANTHROPIC_API_KEY
│       ├── anthropicError.js  # maps SDK errors to HTTP responses
│       └── rateLimit.js       # per-IP fixed-window limiter
├── package.json
├── .env.example
└── .gitignore
```
