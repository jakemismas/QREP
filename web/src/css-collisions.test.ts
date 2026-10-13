/**
 * One home per class (C1b; web-24, web-01). Every stylesheet a component
 * imports is bundled into the one page stylesheet, so a class that two sheets
 * both style is styled wherever it appears, whichever component mounts it.
 * That is web-01's shape: the hidden PalettePanel's .pp-* rules restyle the
 * Pattern panel, which uses the same class names. Six components still
 * inject style strings (PalettePanel, PatternPanel, SizingPanel,
 * EditorToolbar, FabricsPanel and QuiltCanvas), and this scan does not read
 * them until they move to .css files; the test guards the stylesheets.
 *
 * A sheet defines the class that leads a selector: its first class once
 * attribute conditions and the arguments of :not() and :has() are dropped.
 * `.x`, `.x:hover`, `.x[data-on]`, `div.x`, `:is(.x)` and `.x .y` all define
 * .x, including inside @media, @supports, @container, @layer and @scope. The
 * test fails when two component stylesheets (every .css file under web/src
 * except ui/tokens.css and index.css) define the same class, or a component
 * stylesheet defines a class that one of those two global sheets defines.
 * A sheet may still style another sheet's class inside a selector led by its
 * own class (`.pf-rt .pf-btn--secondary`), because that rule applies only
 * inside its own component.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

type Sheet = { name: string; css: string; global?: boolean };

const srcRoot = path.dirname(fileURLToPath(import.meta.url));
const GLOBAL_SHEETS = ["index.css", "ui/tokens.css"];

function sheetName(file: string): string {
  return path.relative(srcRoot, file).split(path.sep).join("/");
}

function cssFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry);
    if (statSync(full).isDirectory()) {
      out.push(...cssFiles(full));
    } else if (entry.endsWith(".css")) {
      out.push(full);
    }
  }
  return out;
}

// Splits on commas outside parentheses, so :is(.a, .b) stays one selector.
function splitSelectorList(list: string): string[] {
  const parts: string[] = [];
  let depth = 0;
  let current = "";
  for (const ch of list) {
    if (ch === "(") depth += 1;
    if (ch === ")") depth -= 1;
    if (ch === "," && depth === 0) {
      parts.push(current);
      current = "";
    } else {
      current += ch;
    }
  }
  parts.push(current);
  return parts.map((part) => part.trim()).filter(Boolean);
}

/** Every rule selector in a sheet, including those inside grouping at-rules. */
function ruleSelectors(css: string): string[] {
  const text = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const selectors: string[] = [];
  // A block is a group (its children are rules), a rule (declarations, whose
  // nested blocks hang off the rule's own selector) or skipped (keyframes,
  // font-face and anything inside them).
  const stack: ("group" | "rule" | "skip")[] = [];
  let prelude = "";
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (ch === '"' || ch === "'") {
      // A brace inside a string (content: "{") is not a block.
      let j = i + 1;
      while (j < text.length && text[j] !== ch) j += text[j] === "\\" ? 2 : 1;
      prelude += text.slice(i, j + 1);
      i = j;
    } else if (ch === "{") {
      const head = prelude.trim();
      prelude = "";
      const parent = stack[stack.length - 1];
      if (parent === "rule" || parent === "skip") {
        stack.push("skip");
      } else if (head.startsWith("@")) {
        stack.push(/^@(media|supports|container|layer|scope)\b/.test(head) ? "group" : "skip");
      } else {
        selectors.push(...splitSelectorList(head));
        stack.push("rule");
      }
    } else if (ch === "}") {
      stack.pop();
      prelude = "";
    } else if (ch === ";") {
      prelude = "";
    } else {
      prelude += ch;
    }
  }
  return selectors;
}

const ATTRIBUTE = /\[[^\]]*\]/g;
const NEGATION = /:(not|has)\((?:[^()]|\([^()]*\))*\)/g;
const CLASS = /\.(-?[_a-zA-Z][\w-]*)/;

/** The class a selector defines, or null for a selector with no class. */
function leadingClass(selector: string): string | null {
  const match = CLASS.exec(selector.replace(ATTRIBUTE, "").replace(NEGATION, ""));
  return match ? `.${match[1]}` : null;
}

/** Classes that a component sheet defines along with another sheet. */
function collisions(sheets: Sheet[]): Map<string, string[]> {
  const homes = new Map<string, Set<string>>();
  for (const sheet of sheets) {
    for (const selector of ruleSelectors(sheet.css)) {
      const name = leadingClass(selector);
      if (name === null) continue;
      const owners = homes.get(name) ?? new Set<string>();
      owners.add(sheet.name);
      homes.set(name, owners);
    }
  }
  const globals = new Set(sheets.filter((sheet) => sheet.global).map((sheet) => sheet.name));
  const out = new Map<string, string[]>();
  for (const [name, owners] of homes) {
    const local = [...owners].filter((owner) => !globals.has(owner));
    if (local.length > 0 && owners.size > 1) out.set(name, [...owners].sort());
  }
  return out;
}

describe("collision detector", () => {
  it("flags one class defined in two sheets (the web-01 .pp-* shape)", () => {
    const found = collisions([
      { name: "PalettePanel.css", css: ".pp-row { display: flex; }" },
      { name: "PatternPanel.css", css: ".pp-row { display: grid; }" },
    ]);
    expect([...found.entries()]).toEqual([[".pp-row", ["PalettePanel.css", "PatternPanel.css"]]]);
  });

  it("flags state, attribute, element, :is() and nested-rule forms of a class", () => {
    const found = collisions([
      { name: "a.css", css: ".x { color: red; }" },
      { name: "b.css", css: "@media (max-width: 400px) { .x:hover, .y { color: blue; } }" },
      { name: "c.css", css: ".y[data-on] { color: green; }" },
      { name: "d.css", css: "div.z { color: red; } @layer base { .w { color: red; } }" },
      { name: "e.css", css: ":is(.z) span { color: blue; }" },
      { name: "f.css", css: "@container (min-width: 1px) { .w .v { color: blue; } }" },
    ]);
    expect(Object.fromEntries(found)).toEqual({
      ".x": ["a.css", "b.css"],
      ".y": ["b.css", "c.css"],
      ".z": ["d.css", "e.css"],
      ".w": ["d.css", "f.css"],
    });
  });

  it("flags a component sheet that restyles a global class", () => {
    const found = collisions([
      { name: "index.css", css: ".btn { padding: 8px; }", global: true },
      { name: "panel.css", css: ".btn:hover { padding: 0; }" },
    ]);
    expect([...found.keys()]).toEqual([".btn"]);
  });

  it("passes a class at home, scoped overrides, keyframes and braces in strings", () => {
    const panel =
      "/* .btn { } */ .panel .btn { width: auto; } .panel.btn { margin: 0; } " +
      ".item:not(.btn) { color: red; } @keyframes spin { from { opacity: 0; } to { opacity: 1; } } " +
      '.label::before { content: "{"; } .after { color: red; }';
    const found = collisions([
      { name: "shared.css", css: ".btn { width: 100%; } .btn:disabled { opacity: 0.6; }" },
      { name: "panel.css", css: panel },
      { name: "index.css", css: ".q { color: red; }", global: true },
      { name: "ui/tokens.css", css: ".q:hover { color: blue; }", global: true },
    ]);
    expect([...found.keys()]).toEqual([]);
    // The brace inside the string does not swallow the rule after it.
    expect(ruleSelectors(panel).map(leadingClass)).toEqual([
      ".panel",
      ".panel",
      ".item",
      ".label",
      ".after",
    ]);
  });
});

describe("component stylesheets under web/src", () => {
  const sheets: Sheet[] = cssFiles(srcRoot).map((file) => ({
    name: sheetName(file),
    css: readFileSync(file, "utf8"),
    global: GLOBAL_SHEETS.includes(sheetName(file)),
  }));
  const components = sheets.filter((sheet) => !sheet.global);

  it("include the photo-flow sheets, and every one defines a class", () => {
    expect(components.map((sheet) => sheet.name)).toContain("shell/photo/shared.css");
    expect(sheets.filter((sheet) => sheet.global).map((sheet) => sheet.name).sort()).toEqual(
      [...GLOBAL_SHEETS].sort(),
    );
    // A sheet the parser read as empty would pass the next test vacuously.
    for (const sheet of components) {
      const defined = ruleSelectors(sheet.css).map(leadingClass).filter(Boolean);
      expect(defined.length, sheet.name).toBeGreaterThan(0);
    }
  });

  it("define each class in one sheet only", () => {
    expect(Object.fromEntries(collisions(sheets))).toEqual({});
  });
});
