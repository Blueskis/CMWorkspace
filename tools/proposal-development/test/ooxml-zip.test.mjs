import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { unzipAll, zipPackage, crc32 } = require("../src/ooxml-zip.js");
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const FIX = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures");

test("crc32 is stable and matches a known value", () => {
  const bytes = new TextEncoder().encode("123456789");
  assert.equal(crc32(bytes), 0xcbf43926);
});

test("round trip: unzip a real .potx, rezip unchanged, reread identically", async () => {
  const buf = await readFile(path.join(FIX, "sample-template.potx"));
  const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
  const { entries, names } = await unzipAll(ab);
  assert.ok(names.length > 5, "expected multiple parts in the package");

  const order = [...entries.keys()];
  const rebuilt = await zipPackage(order.map(name => ({ name, data: entries.get(name) })));

  const reread = await unzipAll(rebuilt.buffer.slice(rebuilt.byteOffset, rebuilt.byteOffset + rebuilt.byteLength));
  assert.equal(reread.names.length, order.length);
  for (const name of order) {
    assert.ok(reread.entries.has(name), `missing ${name} after round trip`);
    assert.deepEqual([...reread.entries.get(name)], [...entries.get(name)]);
  }
});

test("not-a-zip file throws a named error, not a crash", async () => {
  const buf = await readFile(path.join(FIX, "not-a-template.potx"));
  const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
  await assert.rejects(() => unzipAll(ab), /does not look like/);
});
