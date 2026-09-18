#!/usr/bin/env node
/**
 * Runs every self-contained unit test in test/, in order, as a subprocess each — so one
 * suite crashing (a missing fixture, a missing external file) can't take the rest of the
 * run down with it. `npm test` has pointed at this file since package.json was written;
 * it did not exist until now.
 *
 * Deliberately excludes the *-e2e / real-browser-only suites some CI setups add later —
 * everything listed here runs in plain Node with no server and no browser.
 *
 *   node test/run.js
 */
import { spawnSync } from "node:child_process";
import { readdirSync } from "node:fs";

const SUITES = readdirSync(new URL(".", import.meta.url))
  .filter((f) => f.endsWith(".mjs") && f !== "run.js" && !f.startsWith("gen-"))
  .sort();

let failures = 0;
for (const suite of SUITES) {
  console.log(`\n=== ${suite} ===`);
  const result = spawnSync(process.execPath, [new URL(suite, import.meta.url).pathname], {
    stdio: "inherit", cwd: new URL("..", import.meta.url).pathname,
  });
  if (result.status !== 0) {
    failures++;
    console.log(`--- ${suite}: FAILED (exit ${result.status}) ---`);
  }
}

console.log(failures
  ? `\n${failures} of ${SUITES.length} suite(s) FAILED.`
  : `\nAll ${SUITES.length} suites passed.`);
process.exit(failures ? 1 : 0);
