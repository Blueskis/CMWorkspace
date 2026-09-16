#!/usr/bin/env node
/**
 * Assemble a .pptx from a deck_plan.json, an approved template, and an assets directory
 * — the deck-builder skill's Stage 4. There is no Python assembler: build-pptx.js (moved
 * here from webapp/src/, see its own header) is the only real OOXML-writing pptx builder
 * this repo has ever had — cm-proposal-generator's build_deck.py and training-material-
 * generator's build_training_deck.py both stop at a validated manifest and hand off to
 * the pptx skill's manual template workflow. This is that hand-off, automated: one
 * assembler, called from Python via subprocess exactly as build_docx.py already calls
 * `node` for the docx-js build.
 *
 *     node lib/deck/cli/assemble.mjs \
 *         --plan decks/<run>/deck_plan.json \
 *         --template client.potx \
 *         --profile decks/<run>/intake/template_profile.json \
 *         --assets-dir decks/<run>/intake/assets \
 *         -o decks/<run>/deck.pptx
 *
 * `deck_plan.json` is already in build-pptx.js's native shape —
 * `{modules:[{module_id, slides:[{slide_id, role, title, blocks:[{slot, kind, content,
 * sources, gap, gap_note}], speaker_notes}]}]}` — the same shape plan.js produces in the
 * artifact. plan_deck.py (Python) writes to this same shape rather than inventing a
 * second one, so this CLI needs no adapter step; a Python-authored plan and a browser-
 * authored plan are byte-for-byte interchangeable here.
 *
 * `--profile` is optional: when omitted, the template is profiled fresh via
 * profile-template.js. `--assignment` (a layout-role mapping JSON, from resolveLayoutRoles
 * or a user's override in the artifact review step) is also optional and is recomputed
 * from the profile when absent — always the SAME resolver Stage 1's review step already
 * showed the user, so an omitted --assignment reproduces what they already saw, not a
 * fresh guess.
 */
import { readFileSync, writeFileSync, existsSync, readdirSync } from "node:fs";
import { join, extname, basename } from "node:path";
import { profileTemplate } from "../profile-template.js";
import { resolveLayoutRoles } from "../map-layouts.js";
import { buildPptx } from "../build-pptx.js";

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith("--")) {
      const key = argv[i].slice(2);
      out[key] = argv[i + 1];
      i++;
    } else if (argv[i] === "-o") {
      out.out = argv[i + 1];
      i++;
    }
  }
  return out;
}

const EXT_KIND = { ".png": "png", ".jpg": "jpg", ".jpeg": "jpg", ".gif": "gif", ".bmp": "bmp" };

async function loadAssets(assetsDir, assetIndex) {
  const assets = new Map();
  if (!assetsDir || !existsSync(assetsDir)) return assets;
  const byId = new Map((assetIndex?.assets ?? []).map((a) => [a.asset_id, a]));
  for (const file of readdirSync(assetsDir)) {
    const ext = extname(file).toLowerCase();
    if (!(ext in EXT_KIND)) continue;
    const stem = basename(file, ext);
    const entry = byId.get(stem);
    const bytes = readFileSync(join(assetsDir, file));
    assets.set(entry?.asset_id ?? stem, { bytes, ext: EXT_KIND[ext], alt: entry?.alt_text ?? "" });
  }
  return assets;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.plan || !args.template || !args.out) {
    console.error("usage: assemble.mjs --plan deck_plan.json --template client.potx [--profile template_profile.json] [--assignment assignment.json] [--assets-dir assets/] [--asset-index asset_index.json] -o deck.pptx");
    process.exit(1);
  }

  const plan = JSON.parse(readFileSync(args.plan, "utf8"));
  const templateBytes = readFileSync(args.template);

  const profile = args.profile
    ? JSON.parse(readFileSync(args.profile, "utf8"))
    : await profileTemplate(templateBytes.buffer.slice(templateBytes.byteOffset, templateBytes.byteOffset + templateBytes.byteLength));

  const assignment = args.assignment
    ? JSON.parse(readFileSync(args.assignment, "utf8"))
    : resolveLayoutRoles(profile).assignment;

  const assetIndex = args["asset-index"] ? JSON.parse(readFileSync(args["asset-index"], "utf8")) : null;
  const assets = await loadAssets(args["assets-dir"], assetIndex);

  const { file, warnings, slideCount } = await buildPptx({ templateBytes, profile, assignment, plan, assets });
  const buf = file instanceof Uint8Array ? Buffer.from(file) : Buffer.from(await file.arrayBuffer());
  writeFileSync(args.out, buf);
  console.log(`-> ${args.out} (${slideCount} slide(s))`);
  for (const w of warnings) console.error(`  WARNING ${w}`);
  if (warnings.length) process.exitCode = 0; // warnings don't fail the build; plan_deck.py's gates already ran
}

main().catch((err) => {
  console.error(err.stack ?? err.message ?? err);
  process.exit(1);
});
