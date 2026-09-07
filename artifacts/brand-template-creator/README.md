# Brand Vault

A published claude.ai Artifact for capturing a client's brand once (colours, fonts, visual style,
logo, voice and tone, core messaging) and exporting it as a `.json` (machine contract) and a `.md`
(readable brand guide). Both files can be uploaded into any other Claude session to style slides,
banners, newsletters or training material for that client, without re-explaining the brand each time.

## Why it exists

Working across Singapore government and GLC clients, the same brand context otherwise gets
re-explained every session and drifts between deliverables. This tool makes the capture a one-time
job: pick a style preset or describe the client and let Claude propose a starting point, adjust
colours and copy by hand, check contrast in the picker, watch the live preview update, then export.

## Files

```
artifacts/brand-template-creator/
├── index.html                        # the artifact (single file, published to claude.ai)
├── schemas/brand_profile.schema.json # the export contract
├── tests/test_export.mjs             # node --test over the pure export functions
└── README.md                         # this file
```

## Publishing or updating it

The page is a single self-contained HTML file with no build step. Publish it with the Artifact tool
(pass `capabilities: {db: {}, sample: {}, downloads: true}`), or update an existing published copy by
passing its URL. There is nothing to compile or bundle.

## Running the tests

Pure functions (hex normalisation, contrast ratio, filename slugs, export/import, the AI-merge logic)
live in one script block in `index.html`, between `// ---8<--- export-core start` and
`// ---8<--- export-core end` markers. The test file reads `index.html`, extracts that block, and
evaluates it with node's built-in test runner — no dependencies, no build step:

```bash
node --test artifacts/brand-template-creator/tests/test_export.mjs
```

If you change the export or import logic, edit the code inside those markers directly in
`index.html` (there is no separate source file to keep in sync) and re-run the tests.

## How the page behaves

- **No saved storage in this view** (`db` capability unavailable or declined): the page still works
  fully as a single-session editor — pick a preset, fill it in, export. Nothing survives a reload
  unless you've exported it.
- **With saved storage**: every brand you create is kept server-side under `brands/<id>`, with the
  logo kept separately under `brands/<id>/assets/logo` so the library list stays light. Every viewer
  who can edit the artifact can read and write every brand in the library — this is meant to work as
  a shared library for a firm's CoE, not a private workspace, so be aware of that before you share the
  link with a wider group. Each brand in the library has its own delete (×) button, with a confirm
  prompt — deleting the brand currently open in the editor drops back to a fresh blank profile rather
  than leaving the editor pointed at something that no longer exists.
- **Theme**: the topbar's Theme button toggles light/dark for the session (same behaviour as the
  Change Comms Console artifact) — it isn't remembered between visits, so it starts from the browser's
  own preference each time. **Reset all** clears every field on the currently open brand back to
  blank, after a confirm prompt; it doesn't remove the brand from the library, only its contents.
- **AI generation** (`sample` capability): describe the client in a couple of sentences and Claude
  proposes a full profile. By default it only fills in fields that are still empty — a manual edit is
  never silently overwritten — with an explicit toggle to overwrite everything instead. A malformed
  or partial response leaves your existing values untouched and surfaces an error rather than
  crashing. The button is hidden entirely when generation isn't available in the current view.
- **Export** (`downloads` capability): both files go through `downloads.save`. The viewer sees a
  confirmation and can decline it; a decline is treated as a normal outcome, not an error.
- **Logos**: there is no file-hosting capability available on this account, so an uploaded logo is
  downscaled client-side (512px on its longest edge) and embedded as a base64 data URI, both in the
  live preview and in the exported files.

## Using the exported files

Upload either file into a new Claude session:

- The `.json` carries a `usage` field at the top explaining exactly how to apply the rest of the file
  — colours by role, fonts with fallback stacks, voice and tone, and the approved messaging — so a
  receiving session can use it correctly without a companion skill.
- The `.md` is written to hand to the client as-is: a colour swatch table, the embedded logo, and
  readable voice and messaging sections. It deliberately does not include an accessibility or
  do's-and-don'ts section — that was cut by design, not by oversight.
