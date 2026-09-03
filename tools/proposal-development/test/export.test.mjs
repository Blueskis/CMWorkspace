import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { exportProposal, MAX_BYTES } = require("../src/export.js");

const PLAN = { engagementTitle: "Sample Engagement", slides: [{ title: "Cover", blocks: [] }] };

// Test case 26: downloads.save rejects extension_not_enabled -> offers
// .json (plan schema) + .md fallback with a one-line explanation.
test("case 26: pptx blocked by extension_not_enabled falls back to json+md", async () => {
  const saved = [];
  const downloads = {
    save: async ({ filename }) => {
      if (filename.endsWith(".pptx")) {
        const err = new Error("extended type not enabled");
        err.code = "extension_not_enabled";
        throw err;
      }
      saved.push(filename);
      return { status: "saved" };
    },
  };
  const result = await exportProposal(downloads, {
    pptxBuffer: new Uint8Array([1, 2, 3]).buffer,
    filenameBase: "proposal",
    plan: PLAN,
  });
  assert.equal(result.status, "saved");
  assert.equal(result.format, "json+md");
  assert.ok(/not enabled/.test(result.message));
  assert.deepEqual(saved.sort(), ["proposal.json", "proposal.md"]);
});

// Test case 27: downloads.save rejects declined -> no error state, no
// retry, draft intact.
test("case 27: a declined download reports declined without error or retry", async () => {
  let calls = 0;
  const downloads = {
    save: async () => {
      calls++;
      const err = new Error("viewer declined");
      err.code = "declined";
      throw err;
    },
  };
  const result = await exportProposal(downloads, {
    pptxBuffer: new Uint8Array([1, 2, 3]).buffer,
    filenameBase: "proposal",
    plan: PLAN,
  });
  assert.equal(result.status, "declined");
  assert.equal(calls, 1, "must not retry a declined prompt");
});

// Test case 28: deck over 16 MiB -> caught before the call, message names the cause.
test("case 28: an oversized pptx is caught before calling downloads.save", async () => {
  let called = false;
  const downloads = { save: async () => { called = true; return { status: "saved" }; } };
  const oversized = new ArrayBuffer(MAX_BYTES + 1);
  const result = await exportProposal(downloads, { pptxBuffer: oversized, filenameBase: "proposal", plan: PLAN });
  assert.equal(result.status, "too_large");
  assert.match(result.message, /16 MB/);
  assert.equal(called, false, "downloads.save must not be called for an oversized file");
});

test("a successful pptx save returns saved/pptx and never touches the fallback", async () => {
  const saved = [];
  const downloads = { save: async ({ filename }) => { saved.push(filename); return { status: "saved" }; } };
  const result = await exportProposal(downloads, {
    pptxBuffer: new Uint8Array([1, 2, 3]).buffer,
    filenameBase: "proposal",
    plan: PLAN,
  });
  assert.equal(result.status, "saved");
  assert.equal(result.format, "pptx");
  assert.deepEqual(saved, ["proposal.pptx"]);
});
