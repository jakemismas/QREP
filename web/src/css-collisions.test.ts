/**
 * One home per class (C1b; web-24, web-01). Every component stylesheet is
 * bundled into the one page stylesheet, so a class selector that two sheets
 * both define styles whatever carries that class, wherever it mounts: the
 * hidden PalettePanel's .pp-* rules restyle the Pattern panel that way
 * (web-01). This test fails when two component stylesheets (every .css file
 * under web/src except ui/tokens.css and index.css, which are the global
 * layer) define the same class selector.
 *
 * Selectors are compared after dropping pseudo-classes, pseudo-elements and
 * attribute conditions, so `.x` in one sheet and `.x:hover` or `.x[data-on]`
 * in another collide: both style the element that carries .x. A selector
 * scoped by another class (`.a .x`, `.a.x`) is a different selector and does
 * not collide with `.x`. Rules inside @media and @supports count; @keyframes
 * steps are not selectors.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const srcRoot = path.dirname(fileURLToPath(import.meta.url));
const GLOBAL_SHEETS = new Set([path.join("ui", "tokens.css"), "index.css"]);

function componentSheets(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry);
    if (statSync(full).isDirectory()) {
      out.push(...componentSheets(full));
    } else if (entry.endsWith(".css") && !GLOBAL_SHEETS.has(path.relative(srcRoot, full))) {
      out.push(full);
    }
  }
  return out;
}

// Splits on commas outside parentheses, so :not(.a, .b) stays one selector.
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

/** Every rule selector in a sheet, including those nested in @media. */
function ruleSelectors(css: string): string[] {
  const text = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const selectors: string[] = [];
  // A block is a group (its children are rules), a rule (declarations) or
  // skipped (keyframes, font-face, and anything nested in those).
  const stack: ("group" | "rule" | "skip")[] = [];
  let prelude = "";
  for (const ch of text) {
    if (ch === "{") {
      const head = prelude.trim();
      prelude = "";
      const parent = stack[stack.length - 1];
      if (parent === "rule" || parent === "skip") {
        stack.push("skip");
      } else if (head.startsWith("@")) {
        stack.push(/^@(media|supports)\b/.test(head) ? "group" : "skip");
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

const PSEUDO = /::?[\w-]+(\((?:[^()]|\([^()]*\))*\))?/g;
const ATTRIBUTE = /\[[^\]]*\]/g;

/** The selector with its state and attribute conditions dropped, or null
 * when no class is left in it. */
function classSelectorKey(selector: string): string | null {
  const key = selector
    .replace(ATTRIBUTE, "")
    .replace(PSEUDO, "")
    .replace(/\s*([>+~])\s*/g, " $1 ")
    .replace(/\s+/g, " ")
    .trim();
  return /\.[A-Za-z_-]/.test(key) ? key : null;
}

/** Class selectors defined by more than one sheet, with the sheets. */
function collisions(sheets: { name: string; css: string }[]): Map<string, string[]> {
  const owners = new Map<string, Set<string>>();
  for (const sheet of sheets) {
    for (const selector of ruleSelectors(sheet.css)) {
      const key = classSelectorKey(selector);
      if (key === null) continue;
      const names = owners.get(key) ?? new Set<string>();
      names.add(sheet.name);
      owners.set(key, names);
    }
  }
  const out = new Map<string, string[]>();
  for (const [key, names] of owners) {
    if (names.size > 1) out.set(key, [...names].sort());
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

  it("flags a state or attribute variant of another sheet's class", () => {
    const found = collisions([
      { name: "a.css", css: ".x { color: red; }" },
      { name: "b.css", css: "@media (max-width: 400px) { .x:hover, .y { color: blue; } }" },
      { name: "c.css", css: ".y[data-on] { color: green; }" },
    ]);
    expect([...found.keys()].sort()).toEqual([".x", ".y"]);
  });

  it("passes one class in one sheet, scoped selectors, and keyframe steps", () => {
    const found = collisions([
      { name: "shared.css", css: ".btn { width: 100%; } .btn:disabled { opacity: 0.6; }" },
      {
        name: "panel.css",
        css: "/* .btn { } */ .panel .btn { width: auto; } .panel.btn { margin: 0; } @keyframes spin { from { opacity: 0; } to { opacity: 1; } }",
      },
    ]);
    expect([...found.keys()]).toEqual([]);
  });

  it("keeps a :not() list as one selector", () => {
    expect(ruleSelectors(".a:not(.b, .c), .d { color: red; }")).toEqual([".a:not(.b, .c)", ".d"]);
    expect(classSelectorKey(".a:not(.b, .c)")).toBe(".a");
  });
});

describe("component stylesheets under web/src", () => {
  const files = componentSheets(srcRoot);

  it("include the photo-flow sheets", () => {
    const names = files.map((file) => path.relative(srcRoot, file).split(path.sep).join("/"));
    expect(names).toContain("shell/photo/shared.css");
    expect(names).not.toContain("index.css");
    expect(names).not.toContain("ui/tokens.css");
  });

  it("define each class selector in one sheet only", () => {
    const sheets = files.map((file) => ({
      name: path.relative(srcRoot, file).split(path.sep).join("/"),
      css: readFileSync(file, "utf8"),
    }));
    expect(Object.fromEntries(collisions(sheets))).toEqual({});
  });
});
