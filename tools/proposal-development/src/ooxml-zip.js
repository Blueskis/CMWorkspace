"use strict";

/* =================================================================
   Minimal ZIP reader and writer for OOXML (.potx/.pptx) packages.

   Shared between the browser artifact and the Node test suite: no
   npm dependencies, DecompressionStream/CompressionStream cover both
   inflate and deflate, and CRC32 is hand-rolled (it is the one piece
   neither runtime gives you for free).

   Read side generalises the Proposal Reference Tool's existing
   `unzip()` helper (which keeps only entries a predicate wants) to
   read an entire package, since profiling a template needs every
   slideLayout, the theme, and the slide masters, not one named part.
   ================================================================= */

async function inflateRaw(bytes) {
  const stream = new Blob([bytes]).stream()
    .pipeThrough(new DecompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

async function deflateRaw(bytes) {
  const stream = new Blob([bytes]).stream()
    .pipeThrough(new CompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

/* Read every entry in a ZIP (a .potx/.pptx is a ZIP of XML parts).
   `wanted(name)` filters which entries are actually inflated — the
   central directory is always walked in full so callers can inspect
   every part name before deciding, but skipping inflation on parts
   nobody asked for keeps a full-package read cheap. */
async function unzipAll(buffer, wanted = () => true) {
  const dv = new DataView(buffer);
  let eocd = -1;
  const floor = Math.max(0, buffer.byteLength - 66000);
  for (let i = buffer.byteLength - 22; i >= floor; i--) {
    if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error("This does not look like a .docx, .pptx, or .potx file.");

  const count = dv.getUint16(eocd + 10, true);
  let at = dv.getUint32(eocd + 16, true);
  const decoder = new TextDecoder();
  const out = new Map();
  const allNames = [];

  for (let n = 0; n < count; n++) {
    if (dv.getUint32(at, true) !== 0x02014b50) break;
    const method = dv.getUint16(at + 10, true);
    const compSize = dv.getUint32(at + 20, true);
    const nameLen = dv.getUint16(at + 28, true);
    const extraLen = dv.getUint16(at + 30, true);
    const commentLen = dv.getUint16(at + 32, true);
    const localAt = dv.getUint32(at + 42, true);
    const name = decoder.decode(new Uint8Array(buffer, at + 46, nameLen));
    at += 46 + nameLen + extraLen + commentLen;
    allNames.push(name);
    if (!wanted(name)) continue;

    const start = localAt + 30 + dv.getUint16(localAt + 26, true)
                            + dv.getUint16(localAt + 28, true);
    const raw = new Uint8Array(buffer, start, compSize);
    out.set(name, method === 0 ? raw : await inflateRaw(raw));
  }
  return { entries: out, names: allNames };
}

/* --- CRC32 (table-driven) -------------------------------------- */

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
    table[n] = c >>> 0;
  }
  return table;
})();

function crc32(bytes) {
  let crc = 0xffffffff;
  for (let i = 0; i < bytes.length; i++) {
    crc = CRC_TABLE[(crc ^ bytes[i]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

/* --- ZIP writer --------------------------------------------------
   Deflates each entry (falling back to stored/method-0 if deflate
   somehow produces nothing useful — it never does in practice, but
   the fallback keeps this from ever emitting a corrupt part), then
   assembles local headers, central directory, and EOCD. No zip64:
   fine for a proposal deck, which will never near 4GB or 65535 parts.
   ------------------------------------------------------------------ */

function dosDateTime(date = new Date()) {
  const dosTime = ((date.getHours() & 0x1f) << 11)
    | ((date.getMinutes() & 0x3f) << 5)
    | ((date.getSeconds() >> 1) & 0x1f);
  const dosDate = (((date.getFullYear() - 1980) & 0x7f) << 9)
    | ((date.getMonth() + 1) << 5)
    | (date.getDate() & 0x1f);
  return { dosTime, dosDate };
}

async function zipPackage(entries) {
  // entries: Array<{ name: string, data: Uint8Array }>, in write order.
  const { dosTime, dosDate } = dosDateTime();
  const encoder = new TextEncoder();
  const localChunks = [];
  const centralChunks = [];
  let offset = 0;

  for (const { name, data } of entries) {
    const nameBytes = encoder.encode(name);
    const crc = crc32(data);
    let method = 8;
    let compressed = await deflateRaw(data);
    if (!compressed || !compressed.length) {
      // Only an empty source produces an empty deflate stream; store raw.
      method = 0;
      compressed = data;
    } else if (data.length === 0) {
      method = 0;
      compressed = data;
    }

    const local = new Uint8Array(30 + nameBytes.length);
    const ldv = new DataView(local.buffer);
    ldv.setUint32(0, 0x04034b50, true);
    ldv.setUint16(4, 20, true);           // version needed
    ldv.setUint16(6, 0, true);            // flags
    ldv.setUint16(8, method, true);
    ldv.setUint16(10, dosTime, true);
    ldv.setUint16(12, dosDate, true);
    ldv.setUint32(14, crc, true);
    ldv.setUint32(18, compressed.length, true);
    ldv.setUint32(22, data.length, true);
    ldv.setUint16(26, nameBytes.length, true);
    ldv.setUint16(28, 0, true);           // extra length
    local.set(nameBytes, 30);

    localChunks.push(local, compressed);
    const localOffset = offset;
    offset += local.length + compressed.length;

    const central = new Uint8Array(46 + nameBytes.length);
    const cdv = new DataView(central.buffer);
    cdv.setUint32(0, 0x02014b50, true);
    cdv.setUint16(4, 20, true);           // version made by
    cdv.setUint16(6, 20, true);           // version needed
    cdv.setUint16(8, 0, true);            // flags
    cdv.setUint16(10, method, true);
    cdv.setUint16(12, dosTime, true);
    cdv.setUint16(14, dosDate, true);
    cdv.setUint32(16, crc, true);
    cdv.setUint32(20, compressed.length, true);
    cdv.setUint32(24, data.length, true);
    cdv.setUint16(28, nameBytes.length, true);
    cdv.setUint16(30, 0, true);           // extra length
    cdv.setUint16(32, 0, true);           // comment length
    cdv.setUint16(34, 0, true);           // disk number
    cdv.setUint16(36, 0, true);           // internal attrs
    cdv.setUint32(38, 0, true);           // external attrs
    cdv.setUint32(42, localOffset, true);
    central.set(nameBytes, 46);
    centralChunks.push(central);
  }

  const centralOffset = offset;
  let centralSize = 0;
  for (const c of centralChunks) centralSize += c.length;

  const eocd = new Uint8Array(22);
  const edv = new DataView(eocd.buffer);
  edv.setUint32(0, 0x06054b50, true);
  edv.setUint16(4, 0, true);
  edv.setUint16(6, 0, true);
  edv.setUint16(8, entries.length, true);
  edv.setUint16(10, entries.length, true);
  edv.setUint32(12, centralSize, true);
  edv.setUint32(16, centralOffset, true);
  edv.setUint16(20, 0, true);

  const totalSize = offset + centralSize + eocd.length;
  const out = new Uint8Array(totalSize);
  let pos = 0;
  for (const chunk of localChunks) { out.set(chunk, pos); pos += chunk.length; }
  for (const chunk of centralChunks) { out.set(chunk, pos); pos += chunk.length; }
  out.set(eocd, pos);
  return out;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { inflateRaw, deflateRaw, unzipAll, crc32, zipPackage };
}
