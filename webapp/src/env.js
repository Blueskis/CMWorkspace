/**
 * Environment shims so every other module runs unchanged in both the browser (where
 * libraries arrive as globals from <script src>) and Node (where the same modules are
 * imported by test/run.js).
 *
 * This split is the whole reason the shipped artifact can be trusted: the code the tests
 * exercise in Node is byte-identical to the code esbuild bundles into the page.
 */

/** JSZip: a cdnjs <script src> global in the browser, an npm import under Node. */
export async function getJSZip() {
  if (globalThis.JSZip) return globalThis.JSZip;
  const mod = await import("jszip");
  return mod.default ?? mod;
}

/**
 * pdf.js, loaded the CSP-safe way.
 *
 * The artifact CSP permits <script src> from cdnjs but blocks fetch/XHR to it, so pdf.js
 * cannot load its worker normally. Verified in pdf.js 3.11.174's source: PDFWorker reads
 * `globalThis.pdfjsWorker` first, and when that is set it skips `new Worker(...)` and the
 * loadScript fetch entirely. The page therefore loads pdf.worker.min.js as a second
 * <script src> to populate that global; Node mirrors it with require. Confirmed working
 * end-to-end (text + embedded images) by test/spike-pdf.js.
 */
export async function getPdfJs() {
  if (globalThis.pdfjsLib) {
    // workerSrc must be set or pdf.js throws, but it is never fetched: the
    // globalThis.pdfjsWorker main-thread handler wins before any load is attempted.
    if (!globalThis.pdfjsLib.GlobalWorkerOptions.workerSrc) {
      globalThis.pdfjsLib.GlobalWorkerOptions.workerSrc = "pdf.worker.min.js";
    }
    return globalThis.pdfjsLib;
  }
  const { createRequire } = await import("node:module");
  const require = createRequire(import.meta.url);
  globalThis.pdfjsWorker = require("pdfjs-dist/legacy/build/pdf.worker.js");
  const pdfjsLib = require("pdfjs-dist/legacy/build/pdf.js");
  pdfjsLib.GlobalWorkerOptions.workerSrc = "pdf.worker.min.js";
  return pdfjsLib;
}

/**
 * XML parsing, deliberately the SAME implementation in both environments.
 *
 * The browser has a native DOMParser and Node does not, but using each environment's own
 * parser would mean the Node tests and the shipped page could diverge on exactly the
 * namespace and entity edge cases OOXML is full of — which would quietly void the
 * guarantee that testing in Node says anything about the artifact. @xmldom/xmldom is
 * bundled by esbuild and used everywhere instead, so parsing behaviour is identical.
 * It is only used for READING; every part this app writes is built as a string.
 */
export async function parseXml(text) {
  const { DOMParser } = await import("@xmldom/xmldom");
  return new DOMParser({
    // OOXML from real templates is noisy; surface only genuine fatal errors.
    onError: (level, msg) => {
      if (level === "error" || level === "fatalError") {
        throw new Error(`XML parse ${level}: ${msg}`);
      }
    },
  }).parseFromString(text, "text/xml");
}

export const IS_NODE =
  typeof process !== "undefined" && process.versions != null && process.versions.node != null;
