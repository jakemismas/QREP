/**
 * Composes the GitHub Pages artifact (S7, issue #47): the app at the ROOT,
 * legacy docs URLs preserved (viewer.html, demo/, sprint notes - everything
 * except the superseded docs landing index.html), and an /app/ redirect stub
 * so every sprint-2 URL keeps working. CI and the vitest composition suite
 * both run this exact script.
 *
 * Usage: node scripts/compose-site.mjs <output-dir>
 */
import { cpSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(webRoot, "..");
const outDir = process.argv[2];
if (!outDir) {
  console.error("usage: node scripts/compose-site.mjs <output-dir>");
  process.exit(1);
}

mkdirSync(outDir, { recursive: true });

// 1. The app owns the root.
cpSync(path.join(webRoot, "dist"), outDir, { recursive: true });

// 2. Docs content keeps its URLs; the old landing index.html is superseded
//    by the app and must not overwrite it.
const docsDir = path.join(repoRoot, "docs");
for (const entry of readdirSync(docsDir)) {
  if (entry === "index.html") continue;
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
