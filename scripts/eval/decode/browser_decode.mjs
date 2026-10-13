// Decode eval images in a headless browser the way the app's stage step does
// (web/src/state/photo.tsx): createImageBitmap on the file's bytes, a canvas at
// targetSize (web/src/model/downscale.ts), drawImage of the whole bitmap, and a
// PNG from canvas.toBlob. Plan D4b; run_decode.py writes the job list and checks
// every sidecar this script writes.
//
//   node browser_decode.mjs --jobs <jobs.json> --out <decoded>/<browser> \
//     --browser chromium|webkit --port <QREP_E2E_PORT> [--min-free-gb 4]
//
// Sources and PNGs travel over a loopback HTTP server rather than through
// page.evaluate, whose JSON transport would copy a 100 MB image several times.
// One browser, one page per image: a page holds a full-size bitmap and canvas, and
// closing it frees both. The run stops, resumable, when free memory falls under
// --min-free-gb, so it never starves the machine.

import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const requireWeb = createRequire(path.resolve(HERE, "../../../web/package.json"));
const playwright = requireWeb("playwright");
const PW_VERSION = requireWeb("playwright/package.json").version;
const SIDECAR_VERSION = 1;
const STEPS =
  "createImageBitmap(blob); canvas at targetSize(width, height, cap); " +
  "drawImage(bitmap, 0, 0, width, height); canvas.toBlob(image/png)";
// Free memory, in GB, under which a decode in flight is abandoned: the 4 GB floor
// checked between images, less the headroom one 40 MP decode takes.
const LOW_MEMORY = 3.5;
const TYPES = { ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png" };

function parse(argv) {
  const args = { minFreeGb: 4 };
  for (let i = 0; i < argv.length; i += 2) {
    const [flag, value] = [argv[i], argv[i + 1]];
    if (flag === "--jobs") args.jobs = value;
    else if (flag === "--out") args.out = value;
    else if (flag === "--browser") args.browser = value;
    else if (flag === "--port") args.port = Number(value);
    else if (flag === "--min-free-gb") args.minFreeGb = Number(value);
    else throw new Error(`unknown argument ${flag}`);
  }
  if (!args.jobs || !args.out || !["chromium", "webkit"].includes(args.browser) || !args.port) {
    throw new Error("need --jobs, --out, --browser chromium|webkit and --port");
  }
  return args;
}

const freeGb = () => os.freemem() / 2 ** 30;
const sha256 = (bytes) => crypto.createHash("sha256").update(bytes).digest("hex");

function writeJson(file, value) {
  fs.writeFileSync(`${file}.part`, JSON.stringify(value, null, 1) + "\n");
  fs.renameSync(`${file}.part`, file);
}

function serve(jobs, out, port) {
  const uploads = new Map();
  const server = http.createServer((req, res) => {
    const [, kind, index] = req.url.split("/");
    const job = jobs[Number(index)];
    if (req.method === "GET" && req.url === "/") {
      res.writeHead(200, { "content-type": "text/html" });
      res.end("<!doctype html><title>decode</title>");
    } else if (req.method === "GET" && kind === "src" && job) {
      // Served bytes are hashed against the job, so a source that changed after
      // run_decode.py hashed it never yields a PNG under the old hash.
      const bytes = fs.readFileSync(job.source);
      if (sha256(bytes) !== job.sha256) {
        res.writeHead(409);
        res.end("source does not match its sha256");
        return;
      }
      res.writeHead(200, { "content-type": TYPES[path.extname(job.source).toLowerCase()] ?? "application/octet-stream" });
      res.end(bytes);
    } else if (req.method === "POST" && kind === "out" && job) {
      const part = path.join(out, `${job.key}.png.part`);
      const hash = crypto.createHash("sha256");
      const file = fs.createWriteStream(part);
      req.on("data", (chunk) => hash.update(chunk));
      req.pipe(file);
      file.on("finish", () => {
        uploads.set(job.key, { part, sha256: hash.digest("hex") });
        res.writeHead(200);
        res.end("ok");
      });
      file.on("error", (error) => {
        res.writeHead(500);
        res.end(String(error));
      });
    } else {
      res.writeHead(404);
      res.end();
    }
  });
  return new Promise((resolve) => server.listen(port, "127.0.0.1", () => resolve({ server, uploads })));
}

// Runs in the page: the app's stage step, with the cap passed in where the app
// derives it from the window width. null is full size: drawn at its own size.
async function decodeInPage({ index, cap }) {
  const blob = await (await fetch(`/src/${index}`)).blob();
  const bitmap = await createImageBitmap(blob);
  const width = bitmap.width;
  const height = bitmap.height;
  const longest = Math.max(width, height);
  let size = { width, height, scaled: false };
  if (cap !== null && longest > cap) {
    const factor = cap / longest;
    size = { width: Math.round(width * factor), height: Math.round(height * factor), scaled: true };
  }
  const canvas = document.createElement("canvas");
  canvas.width = size.width;
  canvas.height = size.height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("no 2d canvas context");
  ctx.drawImage(bitmap, 0, 0, size.width, size.height);
  if (typeof bitmap.close === "function") bitmap.close();
  const png = await new Promise((resolve, reject) => {
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("could not encode the photo"))), "image/png");
  });
  const sent = await fetch(`/out/${index}`, { method: "POST", body: png });
  if (!sent.ok) throw new Error(`upload failed with ${sent.status}`);
  canvas.width = 0;
  canvas.height = 0;
  return { source: [width, height], decoded: [size.width, size.height], scaled: size.scaled };
}

function done(job, out, browserVersion) {
  const side = path.join(out, `${job.key}.json`);
  if (!fs.existsSync(side) || !fs.existsSync(path.join(out, `${job.key}.png`))) return false;
  const sidecar = JSON.parse(fs.readFileSync(side, "utf8"));
  return (
    sidecar.version === SIDECAR_VERSION &&
    sidecar.error == null &&
    sidecar.browser_version === browserVersion &&
    sidecar.source_sha256 === job.sha256 &&
    sidecar.cap === job.cap
  );
}

async function main() {
  const args = parse(process.argv.slice(2));
  const jobs = JSON.parse(fs.readFileSync(args.jobs, "utf8"));
  fs.mkdirSync(args.out, { recursive: true });
  const { server, uploads } = await serve(jobs, args.out, args.port);
  const launch = () => playwright[args.browser].launch({ headless: true });
  let browser = await launch();
  const version = browser.version();
  let decoded = 0;
  let failed = 0;
  let skipped = 0;
  let stopped = null;
  try {
    for (const [index, job] of jobs.entries()) {
      if (done(job, args.out, version)) {
        skipped += 1;
        continue;
      }
      if (freeGb() < args.minFreeGb) {
        stopped = `free memory ${freeGb().toFixed(2)} GB is under ${args.minFreeGb} GB before ${job.key}`;
        break;
      }
      if (!browser.isConnected()) browser = await launch();
      const page = await browser.newPage();
      let starved = false;
      const watch = setInterval(() => {
        if (freeGb() < LOW_MEMORY) {
          starved = true;
          page.close().catch(() => {});
        }
      }, 1000);
      const base = {
        version: SIDECAR_VERSION,
        key: job.key,
        browser: args.browser,
        browser_version: version,
        playwright_version: PW_VERSION,
        source_sha256: job.sha256,
        cap: job.cap,
      };
      const started = Date.now();
      try {
        await page.goto(`http://127.0.0.1:${args.port}/`);
        const result = await page.evaluate(decodeInPage, { index, cap: job.cap });
        const upload = uploads.get(job.key);
        if (!upload) throw new Error("the page reported success but no PNG arrived");
        const png = path.join(args.out, `${job.key}.png`);
        fs.renameSync(upload.part, png);
        const [w, h] = result.source;
        const [dw, dh] = result.decoded;
        writeJson(path.join(args.out, `${job.key}.json`), {
          ...base,
          source_size: result.source,
          decoded_size: result.decoded,
          scale: result.scaled ? job.cap / Math.max(w, h) : 1.0,
          factors: [dw / w, dh / h],
          steps: STEPS,
          png_sha256: upload.sha256,
          seconds: (Date.now() - started) / 1000,
          decoded_at: new Date().toISOString(),
        });
        decoded += 1;
      } catch (error) {
        if (starved) {
          stopped = `free memory fell under ${LOW_MEMORY} GB while decoding ${job.key}`;
          break;
        }
        // A browser failure is a measured outcome: run_eval turns it into error rows.
        writeJson(path.join(args.out, `${job.key}.json`), { ...base, error: String(error.message ?? error) });
        failed += 1;
        console.error(`${job.key}: ${error.message ?? error}`);
      } finally {
        clearInterval(watch);
        uploads.delete(job.key);
        await page.close().catch(() => {});
      }
    }
  } finally {
    await browser.close().catch(() => {});
    server.close();
  }
  console.log(
    JSON.stringify({ browser: args.browser, browser_version: version, decoded, failed, skipped, stopped }),
  );
  process.exitCode = stopped ? 3 : 0;
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
