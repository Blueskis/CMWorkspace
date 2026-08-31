import type { SheetRef, Table } from "./types";

/**
 * A minimal, dependency-free .xlsx reader — the full SheetJS package pulls in
 * ODS/XLSB support, a formula engine and legacy codepage tables (its main
 * bundle alone is ~800KB minified) for a page that only needs plain rows out
 * of a worksheet. This reads exactly that: workbook.xml for sheet names,
 * sharedStrings.xml for interned text, and each worksheet's cell grid.
 */

export interface Workbook {
  sheets: SheetRef[];
  readSheet: (index: number) => string[][];
}

async function inflateRaw(bytes: Uint8Array): Promise<Uint8Array> {
  if (typeof DecompressionStream === "undefined") {
    throw new Error("This browser cannot unzip .xlsx files. Save the sheet as CSV and load that instead.");
  }
  const ds = new DecompressionStream("deflate-raw");
  const stream = new Blob([bytes as unknown as BlobPart]).stream().pipeThrough(ds);
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

interface ZipEntry {
  method: number;
  bytes: Uint8Array;
}

/** Minimal ZIP central-directory reader — enough for the parts of an .xlsx we need. */
function readZipDirectory(buffer: ArrayBuffer): Record<string, ZipEntry> {
  const dv = new DataView(buffer);
  const u8 = new Uint8Array(buffer);
  let eocd = -1;
  for (let i = u8.length - 22; i >= Math.max(0, u8.length - 66000); i--) {
    if (dv.getUint32(i, true) === 0x06054b50) {
      eocd = i;
      break;
    }
  }
  if (eocd < 0) throw new Error("That file is not a readable .xlsx (no zip directory found).");
  const count = dv.getUint16(eocd + 10, true);
  let p = dv.getUint32(eocd + 16, true);
  const files: Record<string, ZipEntry> = {};
  for (let i = 0; i < count; i++) {
    if (dv.getUint32(p, true) !== 0x02014b50) break;
    const method = dv.getUint16(p + 10, true);
    const compSize = dv.getUint32(p + 20, true);
    const nameLen = dv.getUint16(p + 28, true);
    const extraLen = dv.getUint16(p + 30, true);
    const cmtLen = dv.getUint16(p + 32, true);
    const localAt = dv.getUint32(p + 42, true);
    const name = new TextDecoder().decode(u8.subarray(p + 46, p + 46 + nameLen));
    const lNameLen = dv.getUint16(localAt + 26, true);
    const lExtraLen = dv.getUint16(localAt + 28, true);
    const start = localAt + 30 + lNameLen + lExtraLen;
    files[name] = { method, bytes: u8.subarray(start, start + compSize) };
    p += 46 + nameLen + extraLen + cmtLen;
  }
  return files;
}

const xml = (s: string) => new DOMParser().parseFromString(s, "application/xml");

function colIndex(ref: string): number {
  let n = 0;
  for (const ch of ref) {
    const c = ch.charCodeAt(0);
    if (c < 65 || c > 90) break;
    n = n * 26 + (c - 64);
  }
  return n - 1;
}

export async function readWorkbook(buffer: ArrayBuffer): Promise<Workbook> {
  const zip = readZipDirectory(buffer);
  const readText = async (name: string): Promise<string> => {
    const entry = zip[name];
    if (!entry) throw new Error(`That .xlsx is missing ${name} — it may be an unusual export. Try saving it as CSV.`);
    const raw = entry.method === 0 ? entry.bytes : await inflateRaw(entry.bytes);
    return new TextDecoder().decode(raw);
  };

  let shared: string[] = [];
  if (zip["xl/sharedStrings.xml"]) {
    const doc = xml(await readText("xl/sharedStrings.xml"));
    shared = [...doc.getElementsByTagName("si")].map((si) =>
      [...si.getElementsByTagName("t")].map((t) => t.textContent ?? "").join(""),
    );
  }

  const wb = xml(await readText("xl/workbook.xml"));
  const rels: Record<string, string> = {};
  if (zip["xl/_rels/workbook.xml.rels"]) {
    const rd = xml(await readText("xl/_rels/workbook.xml.rels"));
    for (const r of [...rd.getElementsByTagName("Relationship")]) {
      const target = r.getAttribute("Target") ?? "";
      rels[r.getAttribute("Id") ?? ""] = target.replace(/^\/?xl\//, "").replace(/^\.\//, "");
    }
  }
  const sheets: (SheetRef & { path: string })[] = [...wb.getElementsByTagName("sheet")]
    .map((s, i) => {
      const rid =
        s.getAttribute("r:id") ??
        s.getAttributeNS("http://schemas.openxmlformats.org/officeDocument/2006/relationships", "id");
      const target = (rid && rels[rid]) || `worksheets/sheet${i + 1}.xml`;
      return { name: s.getAttribute("name") || `Sheet ${i + 1}`, index: i, path: "xl/" + target };
    })
    .filter((s) => zip[s.path]);
  if (!sheets.length) throw new Error("No worksheets found in that file.");

  const cache = new Map<number, string[][]>();
  const readSheetAsync = async (index: number): Promise<string[][]> => {
    const path = sheets[index].path;
    const doc = xml(await readText(path));
    const rows: string[][] = [];
    for (const row of [...doc.getElementsByTagName("row")]) {
      const cells: string[] = [];
      for (const c of [...row.getElementsByTagName("c")]) {
        const idx = colIndex(c.getAttribute("r") || "");
        const t = c.getAttribute("t");
        let v = "";
        if (t === "inlineStr") {
          v = [...c.getElementsByTagName("t")].map((n) => n.textContent ?? "").join("");
        } else {
          const vn = c.getElementsByTagName("v")[0];
          const raw = vn ? (vn.textContent ?? "") : "";
          v = t === "s" ? (shared[+raw] ?? "") : raw;
        }
        if (idx >= 0) cells[idx] = v;
      }
      rows.push(cells);
    }
    return rows.map((r) => Array.from({ length: Math.max(r.length, 0) }, (_, i) => r[i] ?? ""));
  };

  // All sheets are read up front so sheet switching in the UI stays synchronous.
  for (let i = 0; i < sheets.length; i++) cache.set(i, await readSheetAsync(i));

  return {
    sheets: sheets.map(({ name, index }) => ({ name, index })),
    readSheet: (index) => cache.get(index) ?? [],
  };
}

export function parseDelimited(text: string): string[][] {
  const firstLine = text.split("\n")[0] ?? "";
  const delim = (firstLine.match(/\t/g) || []).length > (firstLine.match(/,/g) || []).length ? "\t" : ",";
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let q = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (q) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else q = false;
      } else field += ch;
    } else if (ch === '"') q = true;
    else if (ch === delim) {
      row.push(field);
      field = "";
    } else if (ch === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else if (ch !== "\r") field += ch;
  }
  if (field.length || row.length) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

/** Drops leading blank rows and pads every row to the header's width. */
export function toTable(rows: string[][]): Table {
  const first = rows.findIndex((r) => r && r.some((c) => String(c ?? "").trim() !== ""));
  if (first < 0) throw new Error("That sheet looks empty.");
  const header = (rows[first] || []).map((h, i) => String(h ?? "").trim() || `Column ${i + 1}`);
  const body = rows
    .slice(first + 1)
    .map((r) => header.map((_, i) => String((r || [])[i] ?? "").trim()))
    .filter((r) => r.some((c) => c !== ""));
  return { header, body };
}
