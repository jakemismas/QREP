// Browser driver for the calculator conformance harness. It types each job row into a
// third-party quilting calculator the way a person would and records exactly what the
// page returned, so parsers and comparisons can run later, offline, from the raw JSON.
//
//   node scripts/eval/calculators/drive.mjs --jobs <jobs.json> --out <raw.json> --shots <dir>
//        [--pages <pages.json>] [--probe <key>[,<key>]] [--url-map <map.json>]
//
// jobs.json: [{"calculator": key, "row_id": str, "inputs": {field: str}, "bands"?: int}]
// A row with more border bands than the calculator has ("bands", or an input key such as
// border2_width) is recorded with skipped = "not applicable: ..." and never typed.
// pages.json (default <out>.pages.json) holds what each page offered: fields, defaults,
// options, result elements, discovered regions, page text and run notes.
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// These are other people's websites; an unattended runner must never hit them.
if (process.env.CI) {
  console.error("drive.mjs: refusing to run because CI is set. This harness drives third-party websites and only runs by hand on a local machine.");
  process.exit(1);
}

const HERE = path.dirname(fileURLToPath(import.meta.url));
// Reuse the web app's Playwright so the harness adds no dependency of its own.
const requireWeb = createRequire(path.resolve(HERE, "../../../web/package.json"));
const { chromium } = requireWeb("playwright");
const PW_VERSION = requireWeb("playwright/package.json").version;

const USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36 QREP-calc-baseline/1";
const MIN_GAP_MS = 2000;
const KEY_DELAY_MS = 90;
const CTL_SEL = "input, select, textarea, [role=combobox]";
const QP = "https://www.quiltersparadiseesc.com/Calculators/";
const STITCH = "https://thestitchdesk.com/calculators/";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const firstLine = (e) => String(e && e.message ? e.message : e).split("\n")[0];
const cssq = (s) => String(s).replace(/["\\]/g, "\\$&");
const NUMERIC = /^[\d\s./-]+$/;

const byName = (key, extra = {}) => ({ key, kind: "auto", sel: [`[name="${key}"]`], ...extra });
const byId = (key, extra = {}) => ({ key, kind: "auto", inForm: false, sel: [`[id="${key}"]`], ...extra });
const byPh = (key, ph, stem, extra = {}) => ({ key, kind: "auto", inForm: false, sel: [`input[placeholder="${ph}"]`, `input[placeholder*="${stem}" i]`], ...extra });
const formi = (key, extra = {}) => ({ key, kind: "auto", inForm: false, sel: [`[name="${key}"]`, `[id^="forminator-field-${key}_"]`, `[id="${key}"]`], ...extra });
// Field roles for pages whose markup is only known at run time: [match, exclude].
const ROLE = {
  // A quilt-size caption may say "(before borders)", so only a border's own width is excluded.
  width: [/quilt width|width of (the |your )?quilt|\bwidth\b|\bwide\b/i, /fabric|bolt|border\s*(strip\s*)?(width|size)|width of (each |the |your )?border|strip|binding|batting|backing|block|seam|wof|usable|sashing/i],
  length: [/quilt length|length of (the |your )?quilt|\blength\b|\bheight\b|\blong\b|\btall\b/i, /fabric|bolt|border\s*(length|size)|strip|binding|batting|backing|block|seam|sashing/i],
  fabric_width: [/fabric width|bolt width|width of (the )?(fabric|bolt)|\bwof\b|usable (fabric )?width|fabric_?width|\bbolt\b/i, /strip/i],
  border_width: [/border\s*(strip\s*)?(width|size)|width of (each |the |your )?border|^\W*borders?\b/i, /before|without|excluding|including|fabric|bolt|number|how many|count|\bwof\b|length/i],
  overage: [/overage|overhang|extra (fabric|backing|inches|on each)|margin|each side|per side/i, /seam/i],
  directional: [/directional|direction|\bnap\b|one[- ]way/i, null],
};
const byRole = (key, role, extra = {}) => ({ key, kind: "auto", match: ROLE[role][0], not: ROLE[role][1], ...extra });

// submit: css = explicit button; find = a visible "Calculate" button; generic = a plain form
// submit button may stand in; liveOk = no button means the page updates as you type;
// live = never click (the only button posts the form to the site).
const CALCULATORS = {
  qp_backing: {
    url: QP + "Backing%20and%20Batting%20Calculator.php",
    form: "YardageForm",
    fields: ["Fabric_Width", "Width", "Length", "Overage"].map((k) => byName(k)),
    submit: { find: true },
    results: { ids: ["yardage1", "yardage2"] },
  },
  qp_binding: {
    url: QP + "Binding%20Calculator.php",
    form: "BindingForm",
    fields: ["Fabric_Width", "Width", "Length", "Strip_Width"].map((k) => byName(k)),
    submit: { find: true },
    results: { ids: ["binding length", "yardage", "number strips"] },
  },
  qp_border: {
    url: QP + "Border%20Calculator.php",
    form: "BorderForm",
    fields: [
      ...["Fabric_Width", "Width", "Length"].map((k) => byName(k)),
      // Border fields left over from the previous row would leak into this one.
      ...[1, 2, 3, 4, 5].map((i) => byName(`Border${i}Width`, { set: "" })),
      { key: "mitre", kind: "radio", sel: ['input[type="radio"][name="mitre" i]'], set: /non/i },
    ],
    submit: { find: true },
    results: { ids: [...[1, 2, 3, 4, 5].flatMap((i) => [`StripWidth${i}`, `Border${i}Yardage`, `NumStrips${i}`]), "OverallWidth", "OverallLength"], pattern: "StripWidth|Yardage|NumStrips|Overall|Mitre" },
    bands: 5,
  },
  mfqs_backing: {
    url: "https://myfavoritequiltstore.com/toolbox/backing-calculator",
    fields: [
      byPh("length", "Quilt length in inches", "Quilt length"),
      byPh("width", "Quilt width in inches", "Quilt width"),
      byPh("overage", "4 for longarm, 2 for domestic", "for longarm"),
      byPh("fabric_width", "Usable fabric width (e.g. 42, 54, 108)", "Usable fabric width"),
      { key: "batting", kind: "select", inForm: false, sel: ["select"], pickByOption: /cotton/i, set: /cotton/i },
    ],
    submit: { find: true, generic: true },
    region: true,
  },
  nqc: {
    url: "https://www.nebraskaquiltcompany.com/pages/backing-binding-calculator",
    fields: [byId("width"), byId("length"), byId("fabricWidth")],
    submit: { css: "#calcBtn" },
    results: { ids: ["bindingValue", "bindingDetails", "verticalBacking", "verticalPanels", "verticalCoverage", "verticalMessage", "horizontalBacking", "horizontalPanels", "horizontalCoverage", "horizontalMessage"] },
    // Rocket Loader binds the click handler late, so early clicks can do nothing.
    maxClicks: 4,
  },
  stitchdesk_backing: {
    url: STITCH + "backing-calculator",
    fields: [byId("w"), byId("l"), byId("oh", { set: "4" }), byId("bo", { set: "4" }), byId("fw", { set: "42" }), byId("sa", { set: "1/2" }), byId("price", { set: "" })],
    submit: { find: true, liveOk: true },
    region: true,
    tab: true,
  },
  stitchdesk_binding: {
    url: STITCH + "binding-calculator",
    fields: [byId("bqW"), byId("bqL"), byId("btype", { set: /straight/i }), byId("bsw", { set: "2.5" }), byId("bfw", { set: "42" }), byId("bprice", { set: "" })],
    submit: { find: true, liveOk: true },
    region: true,
    tab: true,
  },
  quiltkeeper_binding: {
    url: "https://quiltkeeperstudio.com/calculators/binding",
    fields: [byId("quilt-width"), byId("quilt-height"), byId("strip-width", { set: "2.5" }), byId("fabric-width", { set: "40" }), byId("overage", { set: "10" })],
    submit: { find: true, liveOk: true },
    region: true,
    tab: true,
  },
  omni_backing: {
    url: "https://www.omnicalculator.com/everyday-life/quilt",
    fields: [
      byRole("fabric_width", "fabric_width"),
      byRole("overage", "overage", { set: "4" }),
      byRole("directional", "directional", { set: /non|^no\b/i }),
      byRole("width", "width"),
      byRole("length", "length"),
    ],
    submit: { find: true, liveOk: true },
    region: true,
    tab: true,
    inches: true,
  },
  dtq_border: {
    url: "https://designedtoquilt.com/quilt-border-calculator/",
    fields: [formi("number-1"), formi("number-2"), formi("number-4", { set: "40" }), formi("number-5")],
    submit: { live: true },
    results: { ids: [], pattern: "calculation-" },
    bands: 1,
    tab: true,
  },
  sewbecca_border: {
    url: "https://sewbecca.com/border-calc",
    fields: [byId("quiltWidth"), byId("quiltLength"), byId("borderWidth"), byId("fabricWidth", { set: "40" })],
    submit: { css: '[onclick*="calculateFabric"]', find: true },
    results: { ids: ["result"] },
    bands: 1,
  },
  qc_border: {
    discoverUrl: { from: "https://quiltcalculator.com/", link: /border/i },
    fields: [byRole("fabric_width", "fabric_width", { set: "40" }), byRole("border_width", "border_width"), byRole("width", "width"), byRole("length", "length")],
    submit: { find: true, liveOk: true },
    region: true,
    bands: 1,
    tab: true,
  },
};
const PROBES = { qp_piece_count: QP + "Piece%20Count%20Calculator.php" };

const USAGE = "usage: node scripts/eval/calculators/drive.mjs --jobs <jobs.json> --out <raw.json> --shots <dir> [--pages <pages.json>] [--probe qp_piece_count] [--url-map <map.json>]";

function parseArgs(argv) {
  const a = { probe: [] };
  const flags = { "--jobs": "jobs", "--out": "out", "--shots": "shots", "--pages": "pages", "--url-map": "urlMap" };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (k === "-h" || k === "--help") return { help: true };
    const v = argv[i + 1];
    if (v === undefined) throw new Error(`missing value for ${k}`);
    if (k === "--probe") a.probe.push(...v.split(",").filter(Boolean));
    else if (flags[k]) a[flags[k]] = v;
    else throw new Error(`unknown argument: ${k}`);
    i++;
  }
  if (!a.jobs || !a.out || !a.shots) throw new Error("--jobs, --out and --shots are required");
  for (const p of a.probe) if (!PROBES[p]) throw new Error(`unknown probe: ${p}`);
  return a;
}

function writeJson(file, data) {
  // Write then rename so a crash mid-write never leaves a truncated file behind.
  const tmp = `${file}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(data, (k, v) => (v instanceof RegExp ? String(v) : v), 2) + "\n");
  fs.renameSync(tmp, file);
}

const sites = new Map();
function siteFor(url) {
  const host = (() => { try { return new URL(url).host || url; } catch { return url; } })();
  if (!sites.has(host)) {
    sites.set(host, {
      last: 0,
      async pace() {
        const wait = this.last + MIN_GAP_MS + Math.floor(Math.random() * 400) - Date.now();
        if (wait > 0) await sleep(wait);
      },
      mark() { this.last = Date.now(); },
    });
  }
  return sites.get(host);
}

function parseQty(s) {
  const t = String(s).replace(/½/g, " 1/2").replace(/¼/g, " 1/4").replace(/¾/g, " 3/4").replace(/⅛/g, " 1/8").replace(/⅜/g, " 3/8").replace(/⅝/g, " 5/8").replace(/⅞/g, " 7/8");
  const m = t.match(/(\d+)[\s-]+(\d+)\/(\d+)|(\d+)\/(\d+)|(\d+(?:\.\d+)?|\.\d+)/);
  if (!m) return NaN;
  if (m[1]) return Number(m[1]) + Number(m[2]) / Number(m[3]);
  if (m[4]) return Number(m[4]) / Number(m[5]);
  return Number(m[6]);
}

const equivalent = (cur, want) => cur === want || (NUMERIC.test(want) && want.trim() !== "" && Math.abs(parseQty(cur) - parseQty(want)) < 1e-9);

function matchOption(opts, want) {
  if (want instanceof RegExp) return opts.findIndex((o) => want.test(o.text) || want.test(o.value));
  const w = String(want).trim();
  const lw = w.toLowerCase();
  let i = opts.findIndex((o) => o.value === w || o.text === w);
  if (i < 0) i = opts.findIndex((o) => o.text.toLowerCase() === lw || o.value.toLowerCase() === lw);
  if (i >= 0) return i;
  if (NUMERIC.test(w)) {
    const n = parseQty(w);
    return opts.findIndex((o) => Math.abs(parseQty(o.value) - n) < 1e-9 || Math.abs(parseQty(o.text) - n) < 1e-9);
  }
  return opts.findIndex((o) => o.text.toLowerCase().includes(lw) || o.value.toLowerCase().includes(lw));
}

const stripHtml = (h) => String(h ?? "").replace(/<[^>]*>/g, "").replace(/&nbsp;|\u00a0/g, "").trim();
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

// Only refusal or close controls: consent is never granted on the user's behalf.
async function clearOverlay(page, notes) {
  await page.keyboard.press("Escape").catch(() => {});
  await sleep(800);
  const cands = [
    page.getByRole("button", { name: /^(reject all|reject|decline|deny|close|dismiss|no,? thanks|only necessary|necessary only|continue without accepting)$/i }),
    page.locator('[role="dialog"] [aria-label*="close" i], [aria-modal="true"] [aria-label*="close" i], button[aria-label*="close" i]'),
  ];
  for (const c of cands) {
    const l = c.filter({ visible: true }).first();
    if (await l.count()) {
      const what = (await l.getAttribute("aria-label").catch(() => null)) || (await l.innerText().catch(() => "")).trim();
      await l.click({ timeout: 3000 }).catch(() => {});
      if (notes) notes.push(`cleared an overlay by clicking "${what}"`);
      await sleep(500);
      return;
    }
  }
}

async function safeClick(page, loc, notes) {
  try {
    await loc.click({ timeout: 8000 });
    return;
  } catch (e) {
    if (page.isClosed()) throw e;
  }
  await clearOverlay(page, notes);
  await loc.click({ timeout: 10000 });
}

async function typeInto(page, loc, value, tab, notes) {
  await safeClick(page, loc, notes);
  await loc.press("ControlOrMeta+A");
  await loc.press("Backspace");
  if (value !== "") await loc.pressSequentially(value, { delay: KEY_DELAY_MS });
  if (tab) await loc.press("Tab");
}

async function chooseCustom(page, frame, loc, want, notes) {
  await safeClick(page, loc, notes);
  await sleep(600);
  const re = want instanceof RegExp ? want : new RegExp(String(want).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i");
  const opt = frame.getByRole("option", { name: re }).filter({ visible: true }).first();
  if (!(await opt.count())) {
    await page.keyboard.press("Escape");
    return false;
  }
  await opt.click({ timeout: 8000 });
  return true;
}

// Old table-layout pages often put a radio's caption in the text after it, not in a <label>.
async function readOptions(loc, kind) {
  if (kind === "select") return loc.evaluate((s) => [...s.options].map((o) => ({ value: o.value, text: o.textContent.replace(/\s+/g, " ").trim(), selected: o.selected })));
  return loc.evaluateAll((rs) => rs.map((r) => {
    const own = r.labels && r.labels.length ? r.labels[0].textContent : null;
    let t = own ?? "";
    for (let n = r.nextSibling; own === null && n && t.length < 80; n = n.nextSibling) {
      if (n.nodeType === 1 && n.matches("input, select, br, textarea")) break;
      t += n.textContent;
    }
    return { value: r.value, text: t.replace(/\s+/g, " ").trim(), checked: r.checked };
  }));
}

async function readHeld(ctx) {
  const held = {};
  for (const f of ctx.order) {
    const loc = ctx.fieldLoc[f.key];
    const kind = ctx.fieldKind[f.key];
    if (!loc) continue;
    if (kind === "text") held[f.key] = await loc.inputValue();
    else if (kind === "choice") {
      const t = (await loc.innerText()).replace(/\s+/g, " ").trim();
      held[f.key] = { value: t, text: t };
    } else {
      const o = (await readOptions(loc, kind)).find((x) => x.selected || x.checked);
      held[f.key] = o ? { value: o.value, text: o.text } : null;
    }
  }
  return held;
}

// Every control with the text a person would read as its caption. Kept as one inline
// function because eval-style helpers are blocked by strict page CSPs.
const CONTROLS = (sel) => {
  const tx = (n) => (n ? (n.textContent || "").replace(/\s+/g, " ").trim() : "");
  const labelOf = (e) => {
    if (e.labels && e.labels.length) return tx(e.labels[0]);
    const lab = e.closest("label");
    if (lab) return tx(lab);
    const ids = e.getAttribute("aria-labelledby");
    return ids ? ids.split(/\s+/).map((i) => tx(document.getElementById(i))).join(" ").trim() : "";
  };
  const before = (e) => {
    for (let x = e, d = 0; x && d < 4; x = x.parentElement, d++) {
      for (let s = x.previousSibling; s; s = s.previousSibling) {
        if (s.nodeType === 1 && (s.matches("input, select, textarea") || s.querySelector("input, select, textarea"))) return "";
        const t = (s.textContent || "").replace(/\s+/g, " ").trim();
        if (t) return t.slice(-100);
      }
    }
    return "";
  };
  const unitNear = (e) => {
    const re = /^(in|in\.|inch|inches|cm|mm|m|ft|feet|yd|yds|yards?)$/i;
    for (let row = e.parentElement, d = 0; row && d < 3; row = row.parentElement, d++) {
      if (row.querySelectorAll("input:not([type=hidden])").length > 1) break;
      for (const n of row.querySelectorAll("button, select, span, div, abbr")) {
        if (n === e) continue;
        const t = n.tagName === "SELECT" ? tx(n.options[n.selectedIndex]) : n.childElementCount === 0 ? tx(n) : "";
        if (re.test(t)) return t;
      }
    }
    return null;
  };
  const seen = new Map();
  return [...document.querySelectorAll(sel)].map((e, rawIndex) => {
    const tag = e.tagName.toLowerCase();
    const type = (e.getAttribute("type") || "").toLowerCase();
    const isSel = tag === "select";
    const r = e.getBoundingClientRect();
    const label = labelOf(e);
    let key = e.id || e.getAttribute("name") || e.getAttribute("aria-label") || label || `#${rawIndex}`;
    seen.set(key, (seen.get(key) || 0) + 1);
    if (seen.get(key) > 1) key = `${key}~${seen.get(key)}`;
    return {
      rawIndex, key, tag, type, id: e.id || null, name: e.getAttribute("name"),
      placeholder: e.getAttribute("placeholder"), aria: e.getAttribute("aria-label"), title: e.getAttribute("title"),
      maxlength: e.getAttribute("maxlength"), step: e.getAttribute("step"),
      label, before: before(e), unit: unitNear(e),
      combo: !isSel && tag !== "input" && tag !== "textarea" && e.getAttribute("role") === "combobox",
      value: isSel ? (e.selectedIndex >= 0 ? `${e.value}|${tx(e.options[e.selectedIndex])}` : "") : tag === "input" || tag === "textarea" ? e.value : tx(e),
      checked: type === "radio" || type === "checkbox" ? e.checked : undefined,
      skip: ["hidden", "password", "submit", "button", "reset", "image", "file", "search"].includes(type),
      visible: r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== "hidden",
    };
  });
};
const controlList = (frame) => frame.evaluate(CONTROLS, CTL_SEL);
const haystack = (c) => [c.label, c.aria, c.placeholder, c.title, c.before, c.name, c.id].filter(Boolean).join(" | ");

const PAGE_INFO = () => {
  const tx = (n) => (n ? (n.textContent || "").replace(/\s+/g, " ").trim() : "");
  const ctl = (e) => {
    const d = { tag: e.tagName.toLowerCase(), type: e.getAttribute("type"), name: e.getAttribute("name"), id: e.id || null };
    for (const a of ["maxlength", "placeholder", "step", "min", "max", "aria-label", "onclick"]) if (e.getAttribute(a) !== null) d[a] = e.getAttribute(a);
    if (e.tagName === "SELECT") d.options = [...e.options].map((o) => ({ value: o.value, text: tx(o), selected: o.selected }));
    else if (!["hidden", "password"].includes(e.type)) d.value = e.value;
    if (e.type === "radio" || e.type === "checkbox") d.checked = e.checked;
    if (e.tagName === "BUTTON") d.text = tx(e).slice(0, 80);
    if (e.labels && e.labels.length) d.label = tx(e.labels[0]).slice(0, 120);
    return d;
  };
  const forms = [...document.forms].map((f) => ({ name: f.getAttribute("name"), id: f.id || null, action: f.getAttribute("action"), fields: [...f.elements].map(ctl) }));
  const loose = [...document.querySelectorAll("input, select, textarea, button")].filter((e) => !e.form).slice(0, 80).map(ctl);
  const skip = new Set(["INPUT", "SELECT", "TEXTAREA", "BUTTON", "FORM", "OPTION", "SCRIPT", "STYLE", "LINK", "META"]);
  const ids = [...document.querySelectorAll("body [id]")]
    .filter((e) => !skip.has(e.tagName) && !e.closest("nav, header, footer, svg"))
    .slice(0, 250)
    .map((e) => ({ id: e.id, tag: e.tagName.toLowerCase(), html: e.innerHTML.length > 160 ? e.innerHTML.slice(0, 160) + "..." : e.innerHTML }));
  const main = document.querySelector("main, article, [role=main], #content, .content") || document.body;
  const text = (main.innerText || "").replace(/[ \t]+/g, " ").replace(/\n\s*\n+/g, "\n").slice(0, 6000);
  return { title: document.title, frames: window.frames.length, forms, loose_controls: loose, ids, text };
};

async function newPage(context) {
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  const st = { rowDialogs: null, pageDialogs: [], bound: false, regions: [], outputCtl: new Map(), descs: [], missing: [] };
  page.on("dialog", (d) => {
    const text = d.type() === "alert" ? d.message() : `${d.type()}: ${d.message()}`;
    (st.rowDialogs ?? st.pageDialogs).push(text);
    d.dismiss().catch(() => {});
  });
  return { page, st };
}

async function loadUrl(page, url, site) {
  await site.pace();
  let status = null;
  let error = null;
  try {
    const resp = await page.goto(url, { waitUntil: "load", timeout: 60000 });
    status = resp ? resp.status() : null;
    await page.waitForLoadState("networkidle", { timeout: 10000 }).catch(() => {});
    await sleep(1000);
    if (status && status >= 400) error = `HTTP ${status}`;
  } catch (e) {
    error = `load failed: ${firstLine(e)}`;
  }
  site.mark();
  return { status, error };
}

async function lcaHandle(frame, a, b) {
  return (await frame.evaluateHandle(([x, y]) => {
    const up = (e) => { const c = []; for (let n = e; n; n = n.parentElement) c.unshift(n); return c; };
    const cx = up(x), cy = up(y);
    let i = 0;
    while (i < cx.length && i < cy.length && cx[i] === cy[i]) i++;
    return cx[i - 1];
  }, [a, b])).asElement();
}

async function resolveContext(page, calc, meta) {
  let frame = page.mainFrame();
  let form = null;
  if (calc.form) {
    const fsel = `form[name="${calc.form}" i], form#${calc.form}`;
    frame = null;
    for (const fr of page.frames()) if (await fr.locator(fsel).count()) { frame = fr; break; }
    if (!frame) throw new Error(`form "${calc.form}" not found`);
    form = frame.locator(fsel).first();
  }
  const scopeOf = (f) => (f.inForm === false || !form ? frame : form);
  const first = calc.fields.find((f) => f.sel);
  if (first) await scopeOf(first).locator(first.sel.join(", ")).first().waitFor({ state: "visible", timeout: 20000 });
  else await frame.locator("input:visible").first().waitFor({ timeout: 20000 });
  const controls = await controlList(frame);
  const allCtl = frame.locator(CTL_SEL);
  const ctx = { frame, form, fieldLoc: {}, fieldKind: {}, fieldKeys: new Set(), raw: {}, unitErrors: [], live: false, submit: null };
  meta.fields = {};
  for (const f of calc.fields) {
    let loc = null;
    let info = null;
    if (f.sel) {
      const all = scopeOf(f).locator(f.sel.join(", "));
      if (f.pickByOption) {
        for (let i = 0, n = await all.count(); i < n; i++) {
          const texts = await all.nth(i).locator("option").allTextContents();
          if (texts.some((t) => f.pickByOption.test(t))) { loc = all.nth(i); break; }
        }
      } else if (await all.count()) loc = all.first();
      if (loc) {
        const raw = await loc.evaluate((e, s) => [...document.querySelectorAll(s)].indexOf(e), CTL_SEL);
        info = controls.find((c) => c.rawIndex === raw) ?? null;
        if (f.kind === "radio") loc = all;
      }
    } else {
      const used = new Set(Object.values(ctx.raw));
      info = controls.find((c) => c.visible && !c.skip && c.type !== "checkbox" && c.type !== "radio" && !used.has(c.rawIndex) && f.match.test(haystack(c)) && !(f.not && f.not.test(haystack(c)))) ?? null;
      if (info) {
        loc = info.id ? frame.locator(`[id="${cssq(info.id)}"]`).first()
          : info.label ? frame.getByLabel(info.label, { exact: true }).first()
          : info.placeholder ? frame.getByPlaceholder(info.placeholder, { exact: true }).first()
          : allCtl.nth(info.rawIndex);
      }
    }
    let kind = f.kind;
    if (kind === "auto") kind = !info ? "text" : info.tag === "select" ? "select" : info.type === "radio" ? "radio" : info.combo ? "choice" : "text";
    ctx.fieldLoc[f.key] = loc;
    ctx.fieldKind[f.key] = kind;
    if (info) { ctx.raw[f.key] = info.rawIndex; ctx.fieldKeys.add(info.key); }
    if (info && calc.inches && kind === "text" && info.unit && !/^in/i.test(info.unit)) ctx.unitErrors.push(`unit for ${f.key} is "${info.unit}", not inches`);
    meta.fields[f.key] = info
      ? { found: true, kind, id: info.id, name: info.name, type: info.type, label: info.label, before: info.before, placeholder: info.placeholder, maxlength: info.maxlength, step: info.step, unit: info.unit, default: info.value }
      : { found: !!loc, kind };
    if (loc && kind === "radio") meta.fields[f.key].options = await readOptions(loc, "radio");
    if (loc && kind === "select") meta.fields[f.key].options = await readOptions(loc, "select");
  }
  // People fill a form top to bottom; the job's key order says nothing about the page.
  ctx.order = calc.fields.slice().sort((x, y) => (ctx.raw[x.key] ?? 1e9) - (ctx.raw[y.key] ?? 1e9));
  const found = ctx.order.filter((f) => ctx.fieldLoc[f.key]);
  if (!found.length) throw new Error("none of the calculator's fields were found");
  const firstLoc = ctx.fieldKind[found[0].key] === "radio" ? ctx.fieldLoc[found[0].key].first() : ctx.fieldLoc[found[0].key];
  const lastF = found[found.length - 1];
  const lastLoc = ctx.fieldKind[lastF.key] === "radio" ? ctx.fieldLoc[lastF.key].first() : ctx.fieldLoc[lastF.key];

  const s = calc.submit;
  if (s.live) ctx.live = true;
  else {
    if (s.css && (await frame.locator(s.css).count())) ctx.submit = frame.locator(s.css).first();
    if (!ctx.submit && s.find) {
      const btns = (form ?? frame).getByRole("button", { name: /calculate|compute/i });
      const fh = await firstLoc.elementHandle();
      let best = -1;
      let bestDepth = -1;
      for (let i = 0, n = Math.min(await btns.count(), 10); i < n; i++) {
        if (!(await btns.nth(i).isVisible())) continue;
        const d = await btns.nth(i).evaluate((b, f) => {
          const up = (e) => { const c = []; for (let x = e; x; x = x.parentElement) c.unshift(x); return c; };
          const cb = up(b), cf = up(f);
          let k = 0;
          while (k < cb.length && k < cf.length && cb[k] === cf[k]) k++;
          return k;
        }, fh);
        if (d > bestDepth) { bestDepth = d; best = i; }
      }
      if (best >= 0) ctx.submit = btns.nth(best);
      // Old pages sometimes use a javascript: link or an image as the Calculate control.
      if (!ctx.submit && form) {
        const alt = form.getByRole("link", { name: /calculate/i }).or(form.locator('input[type="image"][alt*="calc" i], input[type="image"][src*="calc" i]')).first();
        if (await alt.count()) ctx.submit = alt;
      }
    }
    if (!ctx.submit && s.generic) {
      const g = firstLoc.locator("xpath=ancestor::form[1]").locator('button[type="submit"], input[type="submit"], button:not([type])').first();
      if (await g.count()) ctx.submit = g;
    }
    if (!ctx.submit) {
      if (s.liveOk) ctx.live = true;
      else throw new Error("submit button not found");
    }
  }
  meta.submit = ctx.live ? { mode: "live" } : { mode: "click", text: (await ctx.submit.evaluate((e) => (e.value || e.textContent || "").replace(/\s+/g, " ").trim())) };
  ctx.anchor = async () => {
    if (form) return form.elementHandle();
    const fh = await firstLoc.elementHandle();
    const fe = (await fh.evaluateHandle((e) => e.closest("form"))).asElement();
    if (fe) return fe;
    const other = ctx.submit ? await ctx.submit.elementHandle() : await lastLoc.elementHandle();
    return lcaHandle(frame, fh, other);
  };
  return ctx;
}

async function resolveResults(frame, calc) {
  return frame.evaluate(({ ids, pattern, exclude }) => {
    const out = [];
    const missing = [];
    const seen = new Set();
    const isCtl = (e) => /^(INPUT|TEXTAREA|SELECT)$/.test(e.tagName);
    const add = (e, key) => {
      if (seen.has(e)) return;
      seen.add(e);
      let k = key;
      for (let n = 2; out.some((o) => o.key === k); n++) k = `${key}#${n}`;
      out.push({ key: k, id: e.id || null, name: e.getAttribute("name"), tag: e.tagName.toLowerCase(), type: e.getAttribute("type") });
    };
    for (const id of ids) {
      const e = document.getElementById(id) || [...document.querySelectorAll("[id]")].find((x) => x.id.toLowerCase() === id.toLowerCase()) || document.getElementsByName(id)[0];
      if (e) add(e, e.id || e.getAttribute("name"));
      else missing.push(id);
    }
    if (pattern) {
      const re = new RegExp(pattern, "i");
      for (const e of document.querySelectorAll("body [id], body [name]")) {
        const name = e.getAttribute("name");
        if (exclude.includes(e.id) || exclude.includes(name)) continue;
        if (e.matches("form, option, script, style, a, meta, input[type=radio], input[type=button], input[type=submit], button")) continue;
        // Form-control results are values, not markup; the prefix keeps that visible to parsers.
        const hit = isCtl(e) ? (re.test(name || "") ? name : re.test(e.id) ? e.id : null) : re.test(e.id) ? e.id : null;
        if (hit) add(e, isCtl(e) ? `value:${hit}` : hit);
      }
    }
    return { out, missing };
  }, { ids: calc.results.ids, pattern: calc.results.pattern ?? null, exclude: calc.fields.map((f) => f.key) });
}

async function readResults(frame, descs) {
  return frame.evaluate((ds) => Object.fromEntries(ds.map((d) => {
    const e = (d.id && document.getElementById(d.id)) || (d.name && document.getElementsByName(d.name)[0]);
    return [d.key, e ? (/^(INPUT|TEXTAREA|SELECT)$/.test(e.tagName) ? e.value : e.innerHTML) : null];
  })), descs);
}

async function waitForChange(frame, descs, baseline, dialogs, maxMs) {
  const base = JSON.stringify(baseline);
  const t0 = Date.now();
  let last = base;
  let lastChange = t0;
  while (Date.now() - t0 < maxMs) {
    const s = JSON.stringify(await readResults(frame, descs));
    if (s !== last) { last = s; lastChange = Date.now(); }
    if (s !== base && Date.now() - lastChange >= 600) break;
    if (s === base && dialogs.length && Date.now() - t0 > 1000) break;
    await sleep(200);
  }
  return JSON.parse(last);
}

async function installObserver(frame) {
  await frame.evaluate(() => {
    const st = (window.__qrepObs ||= {});
    if (st.obs) st.obs.disconnect();
    st.nodes = [];
    st.count = 0;
    st.last = performance.now();
    st.obs = new MutationObserver((list) => {
      for (const m of list) {
        if (m.type === "characterData") st.nodes.push(m.target.parentElement);
        else if (m.addedNodes.length) for (const n of m.addedNodes) st.nodes.push(n.nodeType === 1 ? n : n.parentElement);
        else st.nodes.push(m.target);
      }
      st.count += list.length;
      st.last = performance.now();
    });
    st.obs.observe(document.body, { childList: true, subtree: true, characterData: true });
  });
}

// A navigation wipes the observer; report it as quiet so the caller falls back cleanly.
const obsState = (frame) => frame.evaluate(() => {
  const o = window.__qrepObs;
  return o ? { count: o.count, since: performance.now() - o.last } : { count: -1, since: 1e9 };
});

async function waitQuiet(frame, countBase) {
  const t0 = Date.now();
  while (Date.now() - t0 < 10000) {
    const s = await obsState(frame);
    const el = Date.now() - t0;
    if (el >= 1500 && s.since >= 800 && (s.count > countBase || el >= 5000)) return s;
    await sleep(150);
  }
  return obsState(frame);
}

// Finds the blocks that changed near the form, so the capture is the results and not the
// page. Ads and banners hang off <body>, so changes that only meet the form there are noise.
async function discoverRegions(frame, anchor) {
  return frame.evaluate((a) => {
    const st = window.__qrepObs;
    if (!st) return [];
    const SKIP = "script, style, noscript, iframe, head, template, button, [role=button], label, option, select, nav, header, footer";
    const up = (e) => { const c = []; for (let x = e; x; x = x.parentElement) c.unshift(x); return c; };
    const lca = (x, y) => { const cx = up(x), cy = up(y); let i = 0; while (i < cx.length && i < cy.length && cx[i] === cy[i]) i++; return cx[i - 1]; };
    let all = [...new Set(st.nodes)].filter((e) => e && e.nodeType === 1 && e.isConnected && !e.closest(SKIP) && (e.textContent || "").trim() !== "");
    if (a) {
      const near = all.filter((e) => { const l = lca(e, a); return l !== document.body && l !== document.documentElement; });
      if (near.length) all = near;
    }
    const noCtl = all.filter((e) => !e.matches("input, textarea") && !e.querySelector("input, select, textarea, button"));
    if (noCtl.length) all = noCtl;
    const digit = all.filter((e) => /\d/.test(e.textContent));
    if (digit.length) all = digit;
    all = all.filter((e) => !all.some((o) => o !== e && o.contains(e)));
    if (!all.length) return [];
    const expand = (r) => {
      let x = r;
      while (x.parentElement && x.parentElement !== document.body && !(a && x.parentElement.contains(a)) && (x.parentElement.textContent || "").length <= 1000) x = x.parentElement;
      return x;
    };
    let regions = [];
    const place = (cands) => {
      const r = cands.reduce((x, y) => lca(x, y));
      if (!a || !r.contains(a)) { regions.push(expand(r)); return; }
      if (cands.length === 1 || cands.includes(r)) { regions.push(r); return; }
      const d = up(r).length;
      const groups = new Map();
      for (const e of cands) { const k = up(e)[d]; groups.set(k, [...(groups.get(k) || []), e]); }
      for (const g of groups.values()) place(g);
    };
    place(all);
    regions = [...new Set(regions)].filter((r) => !regions.some((o) => o !== r && o.contains(r)));
    if (regions.length > 8) regions = [all.reduce((x, y) => lca(x, y))];
    regions.sort((x, y) => (x.compareDocumentPosition(y) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1));
    const pathOf = (el) => {
      const parts = [];
      for (let x = el; x && x !== document.body; x = x.parentElement) {
        if (x.id) { parts.unshift(`#${CSS.escape(x.id)}`); return parts.join(" > "); }
        const sib = x.parentElement ? [...x.parentElement.children].filter((c) => c.tagName === x.tagName) : [x];
        parts.unshift(x.tagName.toLowerCase() + (sib.length > 1 ? `:nth-of-type(${sib.indexOf(x) + 1})` : ""));
      }
      return ["body", ...parts].join(" > ");
    };
    return regions.map((r, i) => ({ key: regions.length > 1 ? `results_${i + 1}` : "results", path: pathOf(r), tag: r.tagName.toLowerCase(), id: r.id || null, class: r.getAttribute("class"), contains_form: !!a && r.contains(a) }));
  }, anchor);
}

const regionHtml = (frame, p) => frame.evaluate((q) => { const e = document.querySelector(q); return e ? e.innerHTML : null; }, p);

async function snapshot(ctx, st, calc) {
  if (!calc.region) return readResults(ctx.frame, st.descs);
  const out = {};
  for (const r of st.regions) out[r.key] = await regionHtml(ctx.frame, r.path);
  if (st.outputCtl.size) {
    const list = await controlList(ctx.frame);
    for (const k of st.outputCtl.keys()) out[`value:${k}`] = list.find((c) => c.key === k)?.value ?? null;
  }
  return out;
}

async function settle(ctx, st, calc, meta, countBase, baseline, dialogs, ctlStart) {
  if (!calc.region) return waitForChange(ctx.frame, st.descs, baseline, dialogs, 5000);
  await waitQuiet(ctx.frame, countBase);
  if (!st.regions.length || (await regionHtml(ctx.frame, st.regions[0].path)) === null) {
    st.regions = await discoverRegions(ctx.frame, await ctx.anchor());
    meta.regions = st.regions;
  }
  // Some calculators (React ones especially) show results in read-only inputs, which never
  // show up as DOM mutations; a value that moved without being typed is an output.
  for (const c of await controlList(ctx.frame)) {
    if (c.skip || c.type === "radio" || c.type === "checkbox" || ctx.fieldKeys.has(c.key) || st.outputCtl.has(c.key)) continue;
    const was = ctlStart.find((x) => x.key === c.key);
    if (was ? was.value !== c.value : c.value !== "") st.outputCtl.set(c.key, c.label || c.aria || c.placeholder || "");
  }
  meta.output_controls = Object.fromEntries(st.outputCtl);
  return snapshot(ctx, st, calc);
}

async function mainText(frame, anchor) {
  return frame.evaluate((a) => {
    const box = (a && a.closest("main, article, section")) || document.querySelector("main, article") || document.body;
    return (box.innerText || "").replace(/[ \t]+/g, " ").replace(/\n\s*\n+/g, "\n").slice(0, 3000);
  }, anchor);
}

async function shoot(page, ctx, st, file) {
  try {
    if (!ctx) throw new Error("no form context");
    const anchor = await ctx.anchor();
    const d = st.descs[0];
    const rsel = st.regions.length ? st.regions[0].path : d ? (d.id ? `[id="${cssq(d.id)}"]` : `[name="${cssq(d.name)}"]`) : null;
    const target = (await ctx.frame.evaluateHandle(([a, sel]) => {
      const r = sel ? document.querySelector(sel) : null;
      if (!a) return r || document.body;
      if (!r || a.contains(r)) return a;
      const up = (e) => { const c = []; for (let x = e; x; x = x.parentElement) c.unshift(x); return c; };
      const ca = up(a), cb = up(r);
      let i = 0;
      while (i < ca.length && i < cb.length && ca[i] === cb[i]) i++;
      const l = ca[i - 1];
      const b = l.getBoundingClientRect();
      return l === document.body || l === document.documentElement || b.width * b.height > 2.5e6 ? a : l;
    }, [anchor, rsel])).asElement();
    await target.screenshot({ path: file, timeout: 15000 });
    return null;
  } catch (e) {
    // No form area to frame (page failed or form missing): the viewport is the best evidence left.
    await page.screenshot({ path: file, timeout: 15000 });
    return `viewport screenshot (element screenshot failed: ${firstLine(e)})`;
  }
}

function newRecord(key, url, job) {
  return { calculator: key, url, row_id: job?.row_id ?? null, inputs: job?.inputs ?? null, held: {}, html: {}, dialogs: [], timestamp: null, error: null, skipped: null, screenshot: null };
}

function skipReason(calc, job) {
  if (!calc.bands) return null;
  const extra = Object.keys(job.inputs).filter((k) => !calc.fields.some((f) => f.key === k) && /border|band/i.test(k) && /[2-9]/.test(k));
  if ((job.bands ?? 1) <= calc.bands && !extra.length) return null;
  return `not applicable: ${calc.bands === 1 ? "one border field" : `${calc.bands} border fields`}`;
}

async function runRow(page, st, ctx, calc, key, job, site, meta, out) {
  const rec = newRecord(key, page.url(), job);
  const errors = [];
  st.rowDialogs = rec.dialogs;
  try {
    if (!ctx) throw new Error(meta.error || "calculator form not available");
    const inputs = job.inputs;
    const unknown = Object.keys(inputs).filter((k) => !calc.fields.some((f) => f.key === k));
    if (unknown.length) errors.push(`unknown input field(s): ${unknown.join(", ")}`);
    errors.push(...ctx.unitErrors);
    let ctlStart = [];
    if (calc.region) {
      await installObserver(ctx.frame);
      ctlStart = await controlList(ctx.frame);
    }
    const rowStart = await snapshot(ctx, st, calc);
    const c0 = calc.region ? (await obsState(ctx.frame)).count : 0;
    const chosen = {};
    const wants = {};
    for (const f of ctx.order) {
      const loc = ctx.fieldLoc[f.key];
      const kind = ctx.fieldKind[f.key];
      const given = Object.hasOwn(inputs, f.key);
      const want = given ? inputs[f.key] : f.set;
      if (want === undefined) continue;
      if (!loc) {
        if (given) errors.push(`field ${f.key} not found on page`);
        else meta.notes.push(`${job.row_id}: field ${f.key} not found, left as the page has it`);
        continue;
      }
      wants[f.key] = want;
      if (kind === "text") {
        if (given || !equivalent(await loc.inputValue(), want)) {
          await site.pace();
          await typeInto(page, loc, want, calc.tab, meta.notes);
          site.mark();
        }
      } else if (kind === "choice") {
        const t = (await loc.innerText()).trim();
        const ok = want instanceof RegExp ? want.test(t) : t.toLowerCase().includes(String(want).toLowerCase());
        if (!ok) {
          await site.pace();
          if (!(await chooseCustom(page, ctx.frame, loc, want, meta.notes))) errors.push(`no option for ${f.key} matches ${String(want)}`);
          site.mark();
        }
      } else {
        const opts = await readOptions(loc, kind);
        const idx = matchOption(opts, want);
        if (idx < 0) {
          errors.push(`no ${kind} option for ${f.key} matches ${String(want)} (options: ${opts.map((o) => `${o.value}|${o.text}`).join(", ")})`);
          continue;
        }
        chosen[f.key] = opts[idx];
        if (!(opts[idx].selected || opts[idx].checked)) {
          await site.pace();
          if (kind === "select") await loc.selectOption({ index: idx });
          else await safeClick(page, loc.nth(idx), meta.notes);
          site.mark();
        }
      }
    }
    rec.held = await readHeld(ctx);
    for (const [k, want] of Object.entries(wants)) {
      const h = rec.held[k];
      const kind = ctx.fieldKind[k];
      if (kind === "text") {
        const given = Object.hasOwn(inputs, k);
        if (given ? h === want : equivalent(h, want)) continue;
        const ml = await ctx.fieldLoc[k].getAttribute("maxlength");
        const limited = ml !== null && want.startsWith(h) && h.length === Number(ml);
        errors.push(`${limited ? "input limit" : "held value differs"}: ${k} held "${h}" for typed "${want}"${ml !== null ? ` (maxlength ${ml})` : ""}`);
      } else if (kind === "choice") {
        const t = h?.text ?? "";
        if (!(want instanceof RegExp ? want.test(t) : t.toLowerCase().includes(String(want).toLowerCase()))) errors.push(`held value differs: ${k} shows "${t}" for ${String(want)}`);
      } else if (chosen[k] && (!h || h.value !== chosen[k].value)) {
        errors.push(`held value differs: ${k} held ${JSON.stringify(h)}, wanted option ${JSON.stringify(chosen[k])}`);
      }
    }
    let after;
    if (ctx.live) {
      rec.timestamp = new Date().toISOString();
      after = await settle(ctx, st, calc, meta, c0, rowStart, rec.dialogs, ctlStart);
    } else {
      const preClick = await snapshot(ctx, st, calc);
      for (let clicks = 1; ; clicks++) {
        await site.pace();
        rec.timestamp ??= new Date().toISOString();
        const cb = calc.region ? (await obsState(ctx.frame)).count : 0;
        await safeClick(page, ctx.submit, meta.notes);
        site.mark();
        after = await settle(ctx, st, calc, meta, cb, preClick, rec.dialogs, ctlStart);
        if (!same(after, preClick) || !same(after, rowStart)) break;
        if (st.bound || rec.dialogs.length || clicks >= (calc.maxClicks ?? 1)) break;
        meta.notes.push(`${job.row_id}: click ${clicks} changed nothing, clicking again in case the page script was not bound yet`);
      }
    }
    if (!same(after, rowStart)) st.bound = true;
    rec.html = after;
    const heldAfter = await readHeld(ctx);
    for (const k of Object.keys(heldAfter)) if (!same(heldAfter[k], rec.held[k])) meta.notes.push(`${job.row_id}: ${k} changed from ${JSON.stringify(rec.held[k])} to ${JSON.stringify(heldAfter[k])} after submit`);
    if (st.missing.length) errors.push(`missing result element(s): ${st.missing.join(", ")}`);
    if (calc.region && !Object.keys(after).length) {
      errors.push("no results region found");
      rec.html = { main_text: await mainText(ctx.frame, await ctx.anchor()) };
    } else if (Object.values(after).filter((v) => v !== null).every((v) => stripHtml(v) === "")) errors.push("empty result");
    else if (same(after, rowStart)) errors.push("result unchanged after submit");
  } catch (e) {
    errors.push(`exception: ${firstLine(e)}`);
  }
  if (rec.dialogs.length) errors.push(`dialog: ${rec.dialogs.join(" | ")}`);
  if (errors.length) {
    rec.error = errors.join("; ");
    const base = `${key}__${String(job.row_id).replace(/[^A-Za-z0-9._-]+/g, "_")}`;
    let name = `${base}.png`;
    for (let n = 2; out.shotNames.has(name); n++) name = `${base}__${n}.png`;
    out.shotNames.add(name);
    try {
      const note = await shoot(page, ctx, st, path.join(out.shots, name));
      rec.screenshot = name;
      if (note) meta.notes.push(`${job.row_id}: ${note}`);
    } catch (e) {
      meta.notes.push(`${job.row_id}: screenshot failed: ${firstLine(e)}`);
    }
  }
  st.rowDialogs = null;
  return rec;
}

async function accountHint(page) {
  const hit = await page.evaluate(() => !!document.querySelector("input[type=password]") || /\b(sign in|log in|login|sign up|create (an |your )?account|members only)\b/i.test(document.body ? document.body.innerText : "")).catch(() => false);
  return hit ? "; the page shows login or sign-up wording, so the calculator may need an account" : "";
}

async function openCalculator(context, calc, startUrl, site, meta, out) {
  const { page, st } = await newPage(context);
  let { status, error } = await loadUrl(page, startUrl, site);
  if (!error && calc.discoverUrl) {
    const found = await page.evaluate((src) => {
      const re = new RegExp(src, "i");
      const cands = [...document.querySelectorAll("a[href]")]
        .map((a) => ({ href: a.href, text: (a.textContent || "").replace(/\s+/g, " ").trim().slice(0, 80) }))
        .filter((a) => /^(https?|file):/.test(a.href) && (re.test(a.text) || re.test(a.href)));
      const score = (a) => (re.test(a.text) ? 2 : 0) + (re.test(a.href) ? 1 : 0) + (/calc/i.test(a.href + a.text) ? 2 : 0) + (a.href.startsWith(location.origin) ? 1 : 0);
      cands.sort((x, y) => score(y) - score(x));
      return { href: cands.length ? cands[0].href : null, cands: cands.slice(0, 8) };
    }, calc.discoverUrl.link.source);
    meta.discovered_from = startUrl;
    meta.link_candidates = found.cands;
    if (found.href) {
      ({ status, error } = await loadUrl(page, found.href, site));
      meta.url = found.href;
    } else error = `no link matching ${calc.discoverUrl.link} on ${startUrl}`;
  }
  Object.assign(meta, { status, final_url: page.url() });
  let ctx = null;
  if (error) meta.error = error;
  else {
    try {
      ctx = await resolveContext(page, calc, meta);
      meta.loaded = true;
    } catch (e) {
      meta.error = `form: ${firstLine(e)}${await accountHint(page)}`;
    }
  }
  try {
    meta.title = await page.title();
    meta.info = await page.evaluate(PAGE_INFO);
  } catch (e) {
    meta.notes.push(`page info failed: ${firstLine(e)}`);
  }
  if (ctx && calc.results) {
    const r = await resolveResults(ctx.frame, calc);
    st.descs = r.out;
    st.missing = r.missing;
    meta.results = r.out;
    meta.missing_results = r.missing;
  }
  meta.page_dialogs = st.pageDialogs;
  out.writePages();
  return { page, st, ctx };
}

async function runCalculator(context, key, calc, rows, out, startUrl) {
  const site = siteFor(startUrl);
  const meta = { url: startUrl, loaded: false, notes: [] };
  out.pages[key] = meta;
  let opened = null;
  for (const job of rows) {
    let rec;
    const reason = skipReason(calc, job);
    if (reason) {
      rec = newRecord(key, meta.url, job);
      rec.skipped = reason;
    } else {
      // Loaded lazily so a calculator whose rows are all skipped is never visited.
      if (!opened) opened = await openCalculator(context, calc, startUrl, site, meta, out);
      try {
        rec = await runRow(opened.page, opened.st, opened.ctx, calc, key, job, site, meta, out);
      } catch (e) {
        rec = newRecord(key, meta.url, job);
        rec.error = `exception: ${firstLine(e)}`;
      }
    }
    out.records.push(rec);
    out.writeRecords();
    console.log(`${key} ${job.row_id}: ${rec.skipped ?? rec.error ?? "ok"}`);
  }
  out.writePages();
  if (opened) await opened.page.close().catch(() => {});
}

async function runProbe(context, key, url, out) {
  const { page, st } = await newPage(context);
  const { status, error } = await loadUrl(page, url, siteFor(url));
  const meta = { url, probe: true, status, final_url: page.url(), loaded: !error, error };
  try {
    meta.title = await page.title();
    meta.info = await page.evaluate(PAGE_INFO);
  } catch (e) {
    meta.error ??= `page info failed: ${firstLine(e)}`;
  }
  meta.page_dialogs = st.pageDialogs;
  out.pages[key] = meta;
  out.writePages();
  console.log(`probe ${key}: ${meta.error ?? "loaded"}`);
  await page.close().catch(() => {});
}

function jobProblem(job) {
  if (!job || typeof job !== "object") return "job is not an object";
  if (!CALCULATORS[job.calculator]) return `unknown calculator: ${job.calculator}`;
  if (typeof job.row_id !== "string") return "row_id must be a string";
  if (!job.inputs || typeof job.inputs !== "object" || Object.values(job.inputs).some((v) => typeof v !== "string")) return "inputs must map field names to strings";
  if (job.bands !== undefined && !(Number.isInteger(job.bands) && job.bands > 0)) return "bands must be a positive integer";
  return null;
}

async function main() {
  let args;
  try {
    args = parseArgs(process.argv.slice(2));
  } catch (e) {
    console.error(`${firstLine(e)}\n${USAGE}`);
    return 2;
  }
  if (args.help) { console.log(USAGE); return 0; }
  const jobs = JSON.parse(fs.readFileSync(args.jobs, "utf8"));
  if (!Array.isArray(jobs)) { console.error("jobs file must hold a JSON list"); return 2; }
  const urlMap = args.urlMap ? JSON.parse(fs.readFileSync(args.urlMap, "utf8")) : {};
  const outFile = path.resolve(args.out);
  const pagesFile = path.resolve(args.pages ?? outFile.replace(/\.json$/i, "") + ".pages.json");
  fs.mkdirSync(path.resolve(args.shots), { recursive: true });
  fs.mkdirSync(path.dirname(outFile), { recursive: true });

  const out = {
    records: [],
    pages: { _run: { playwright: PW_VERSION, user_agent: USER_AGENT, started: new Date().toISOString() } },
    shots: path.resolve(args.shots),
    shotNames: new Set(),
    writeRecords() { writeJson(outFile, this.records); },
    writePages() { writeJson(pagesFile, this.pages); },
  };
  const groups = new Map();
  for (const job of jobs) {
    const bad = jobProblem(job);
    if (bad) {
      const rec = newRecord(job?.calculator ?? null, null, job);
      rec.error = `bad job: ${bad}`;
      out.records.push(rec);
      continue;
    }
    if (!groups.has(job.calculator)) groups.set(job.calculator, []);
    groups.get(job.calculator).push(job);
  }
  out.writeRecords();

  if (!fs.existsSync(chromium.executablePath())) {
    console.error(`Chromium for Playwright ${PW_VERSION} is not installed (${chromium.executablePath()} missing). Not installing anything; stopping.`);
    return 3;
  }
  let browser;
  try {
    browser = await chromium.launch();
  } catch (e) {
    console.error(`Chromium for Playwright ${PW_VERSION} could not start (${firstLine(e)}). Not installing anything; stopping.`);
    return 3;
  }
  try {
    const context = await browser.newContext({ userAgent: USER_AGENT, viewport: { width: 1280, height: 900 }, locale: "en-US" });
    for (const [key, rows] of groups) {
      const calc = CALCULATORS[key];
      await runCalculator(context, key, calc, rows, out, urlMap[key] ?? calc.url ?? calc.discoverUrl.from);
    }
    for (const key of args.probe) await runProbe(context, key, urlMap[key] ?? PROBES[key], out);
    await context.close();
  } finally {
    await browser.close();
    out.pages._run.finished = new Date().toISOString();
    out.writePages();
  }
  const failed = out.records.filter((r) => r.error).length;
  const skipped = out.records.filter((r) => r.skipped).length;
  console.log(`${out.records.length} record(s), ${failed} with errors, ${skipped} skipped -> ${outFile}`);
  return 0;
}

process.exitCode = await main();
