/**
 * Composes the GitHub Pages artifact (S7, issue #47): the app at the ROOT,
 * the legacy product URLs preserved (the sprint-1 viewer.html and its demo/
 * artifacts), and an /app/ redirect stub so every sprint-2 URL keeps working.
 * Sprint plans, orchestrator prompts, design notes and research stay in the
 * repository and out of the product site, so only the allowlist below is
 * published. CI and the vitest composition suite both run this exact script.
 *
 * Usage: node scripts/compose-site.mjs <output-dir>
 */
import { cpSync, mkdirSync, writeFileSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(webRoot, "..");
const PUBLISHED_DOCS = ["viewer.html", "demo"];
const outDir = process.argv[2];
if (!outDir) {
  console.error("usage: node scripts/compose-site.mjs <output-dir>");
  process.exit(1);
}

mkdirSync(outDir, { recursive: true });

// 1. The app owns the root.
cpSync(path.join(webRoot, "dist"), outDir, { recursive: true });

// 2. Legacy product pages keep their URLs. The old docs landing index.html is
//    superseded by the app and is not in the list.
const docsDir = path.join(repoRoot, "docs");
for (const entry of PUBLISHED_DOCS) {
  cpSync(path.join(docsDir, entry), path.join(outDir, entry), { recursive: true });
}

// 3. Sprint-2 URLs pointed at /app/: redirect home.
mkdirSync(path.join(outDir, "app"), { recursive: true });
writeFileSync(
  path.join(outDir, "app", "index.html"),
  `<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta http-equiv="refresh" content="0; url=../" />
    <title>QREP</title>
    <script>location.replace("../");</script>
  </head>
  <body>
    <p>QREP moved to the site root. <a href="../">Open the app</a>.</p>
  </body>
</html>
`,
);

// 4. Pages hygiene.
writeFileSync(path.join(outDir, ".nojekyll"), "");
console.log(`composed site at ${outDir}`);
