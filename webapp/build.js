/**
 * Bundle src/entry.js into a single IIFE and splice it into index.template.html to
 * produce dist/index.html — the file that gets published as the artifact.
 *
 * Four packages are marked external — left as literal `import(...)` calls rather than
 * bundled — because each is reached only through a branch that is dead code in the
 * browser: `canvas` (parse-pdf.js's Node image-rasterization fallback, guarded by a
 * try/catch, unreachable once OffscreenCanvas/document exist), `node:module`,
 * `jszip` and `pdfjs-dist` (env.js's Node-only branches, taken only when the cdnjs
 * globals `JSZip`/`pdfjsLib` are absent — never true in the shipped page, where the
 * three <script src> tags set them before this bundle runs). Bundling them anyway
 * would just be dead weight; `@xmldom/xmldom` is NOT in this list because env.js's
 * parseXml() imports it unconditionally in both environments, so the browser needs
 * the real bundled code, not a literal import it can never resolve.
 */
import { build } from "esbuild";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

async function main() {
  const result = await build({
    entryPoints: [path.join(__dirname, "src/entry.js")],
    bundle: true,
    format: "iife",
    target: "es2020",
    external: ["canvas", "node:module", "jszip", "pdfjs-dist"],
    write: false,
    logLevel: "warning",
  });

  const bundle = result.outputFiles[0].text;

  const template = readFileSync(path.join(__dirname, "index.template.html"), "utf8");
  const marker = "<!--INLINE:dist/bundle.js-->";
  if (!template.includes(marker)) {
    throw new Error(`index.template.html is missing the inline marker ${marker}`);
  }
  // A function replacer, not a string one: the bundle contains literal "$&"-style
  // regex-escaping idioms (from @xmldom/xmldom) that String.replace would otherwise
  // interpret as substitution patterns and silently corrupt.
  const html = template.replace(marker, () => bundle);

  mkdirSync(path.join(__dirname, "dist"), { recursive: true });
  const outPath = path.join(__dirname, "dist/index.html");
  writeFileSync(outPath, html);
  console.log(`wrote ${outPath} (${(html.length / 1024).toFixed(1)} KiB)`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
