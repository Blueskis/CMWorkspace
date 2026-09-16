/**
 * Bundle src/entry.js into a single IIFE and splice it into index.template.html to
 * produce dist/index.html — the file published as the artifact. Same pattern as
 * webapp/build.js (see that file's own comment for why canvas/jszip/pdfjs-dist/node:module
 * are left external — env.js's Node-only branches are dead code in the browser bundle).
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
  if (!template.includes(marker)) throw new Error(`index.template.html is missing the inline marker ${marker}`);
  const html = template.replace(marker, () => bundle);

  mkdirSync(path.join(__dirname, "dist"), { recursive: true });
  const outPath = path.join(__dirname, "dist/index.html");
  writeFileSync(outPath, html);
  console.log(`wrote ${outPath} (${(html.length / 1024).toFixed(1)} KiB)`);
}

main().catch((err) => { console.error(err); process.exit(1); });
