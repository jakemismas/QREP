/**
 * The plain-language check (issue #280; RESET.md section 6), run at every
 * quilter journey step at both sizes. It reads the visible screen only and
 * returns one violation per finding:
 *
 * - banned-word: a rule 1 word in the visible text, case-insensitive and
 *   whole words, or an internal id such as f0;
 * - small-text: visible text under 16 px (rule 4);
 * - small-target: an enabled button, a[href], input, select or
 *   [role=button] whose box is under 44 x 44 px (rule 4);
 * - overflow: the screen scrolls or spills sideways (helpers/layout.ts);
 * - contrast: text under 4.5:1 against the background colors its ancestors
 *   composite to, white at the root (rule 4). Text over a background image
 *   is skipped, since its backdrop is not one color; so is text inside a
 *   disabled control, which WCAG 1.4.3 exempts. Element opacity is not
 *   applied.
 *
 * Visible means rendered: not display none, visibility hidden or opacity 0,
 * and wider and taller than 1 px, which leaves out visually hidden labels.
 * Text below the fold counts, since she can scroll to it.
 *
 * A violation's target names the element stably: its test id, or the
 * nearest test id above it with its tag and first class, so new wording
 * keeps the key. Where two visible elements share that, their text (or a
 * control's aria-label) tells them apart, with digit runs as "#" and dashes
 * as "-", so a target holds no measured value and no dash. The measured
 * values go in detail, which no key reads.
 * grandma-allowlist.json lists the violations main has today by key, and
 * compareWithAllowlist fails on anything unlisted and on any listed entry a
 * run did not see, so the list can only shrink.
 */
import { readFileSync } from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import type { Page } from "@playwright/test";
import { expectNoHorizontalOverflow } from "./layout";

export type GrandmaRule = "banned-word" | "small-text" | "small-target" | "overflow" | "contrast";

export interface Violation {
  rule: GrandmaRule;
  step: string;
  viewport: string;
  target: string;
  detail: string;
}

export interface AllowlistEntry {
  rule: GrandmaRule;
  step: string;
  viewport: string;
  target: string;
  /** The open ticket whose change removes this violation, such as "#157". */
  ticket: string;
}

/** RESET.md section 6, rule 1, as written. Internal ids match ID_PATTERN. */
export const BANNED_WORDS = [
  "engine",
  "Python",
  "vision",
  "read",
  "re-read",
  "region",
  "confidence",
  "census",
  "scope",
  "grid fit",
  "pixels",
  "HST",
  "QST",
  "stepper",
  "MB",
  "ms",
  "analyze",
  "reverse",
  "crop",
  "quad",
  "approximation",
];
/** A model fabric id such as f0 or f12. */
const ID_PATTERN = "f\\d+";

export const MIN_TEXT_PX = 16;
export const MIN_TARGET_PX = 44;
export const MIN_CONTRAST = 4.5;

const RULES: readonly GrandmaRule[] = ["banned-word", "small-text", "small-target", "overflow", "contrast"];
const allowlistPath = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "grandma-allowlist.json");

/** The journey's names for its two sizes; any other size names itself. */
export function viewportName(page: Page): string {
  const size = page.viewportSize();
  if (!size) throw new Error("the plain-language check needs a fixed viewport");
  if (size.width === 390 && size.height === 844) return "phone";
  if (size.width === 1280 && size.height === 800) return "desktop";
  return `${size.width}x${size.height}`;
}

export function violationKey(v: Pick<Violation, "rule" | "step" | "viewport" | "target">): string {
  return `${v.rule} | ${v.step} | ${v.viewport} | ${v.target}`;
}

const ANSI = new RegExp(`${String.fromCharCode(27)}\\[[0-9;]*m`, "g");

/** Run every rule on the page as it stands, as the journey's named step. */
export async function check(page: Page, step: string): Promise<Violation[]> {
  const viewport = viewportName(page);
  const found: Violation[] = [];

  // Finish entry fades first, so opacity and color read their settled values.
  // Endless animations (a spinner) never finish and are left running.
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((animation) => Number.isFinite(Number(animation.effect?.getComputedTiming().endTime)))
        .map((animation) => animation.finished.catch(() => undefined)),
    ),
  );

  try {
    await expectNoHorizontalOverflow(page, `journey-${step}`);
  } catch (error) {
    const message = (error instanceof Error ? error.message : String(error)).replace(ANSI, "");
    found.push({ rule: "overflow", step, viewport, target: "page", detail: message.split("\n")[0] });
  }

  const measured = await page.evaluate(
    ({ words, idPattern, minText, minTarget, minContrast }) => {
      type Finding = { rule: string; target: string; detail: string };
      const out: Finding[] = [];

      const shows = (el: Element) => {
        if (!el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) return false;
        const rect = el.getBoundingClientRect();
        return rect.width > 1 && rect.height > 1;
      };
      const clean = (text: string) => text.replace(/\s+/g, " ").trim();
      const mask = (text: string) =>
        clean(text)
          .replace(/[\u2010-\u2015\u2212]/g, "-")
          .replace(/\d+/g, "#")
          .slice(0, 40)
          .trim();
      const ownText = (el: Element) => {
        let text = "";
        for (const node of el.childNodes) if (node.nodeType === Node.TEXT_NODE) text += node.textContent ?? "";
        if (el instanceof HTMLInputElement) {
          const shownValue = ["button", "submit", "reset"].includes(el.type) ? el.value : "";
          text += ` ${el.placeholder} ${shownValue}`;
        }
        return clean(text);
      };
      const base = (el: Element) => {
        const own = el.getAttribute("data-testid");
        if (own) return `[data-testid=${own}]`;
        const holder = el.parentElement?.closest("[data-testid]")?.getAttribute("data-testid");
        const cls = el.classList.length > 0 ? `.${el.classList[0]}` : "";
        return `${holder ? `[data-testid=${holder}] ` : ""}${el.tagName.toLowerCase()}${cls}`;
      };

      // Colors: computed sRGB values parse directly; anything else (oklch,
      // color()) is painted on a 1 px canvas and read back.
      const probe = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
      const rgba = (color: string): [number, number, number, number] => {
        const match = /^rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:\s*[,/]\s*([\d.]+%?))?\s*\)$/.exec(color);
        if (match) {
          const alphaText = match[4];
          const alpha =
            alphaText === undefined ? 1 : alphaText.endsWith("%") ? parseFloat(alphaText) / 100 : parseFloat(alphaText);
          return [Number(match[1]), Number(match[2]), Number(match[3]), alpha];
        }
        if (!probe) return [0, 0, 0, 1];
        probe.clearRect(0, 0, 1, 1);
        probe.fillStyle = "#000";
        probe.fillStyle = color;
        probe.fillRect(0, 0, 1, 1);
        const d = probe.getImageData(0, 0, 1, 1).data;
        return [d[0], d[1], d[2], d[3] / 255];
      };
      const over = (top: [number, number, number, number], base: number[]) =>
        [0, 1, 2].map((i) => top[i] * top[3] + base[i] * (1 - top[3]));
      const backdrop = (el: Element): number[] | null => {
        const layers: [number, number, number, number][] = [];
        for (let up: Element | null = el; up; up = up.parentElement) {
          const style = getComputedStyle(up);
          if (style.backgroundImage !== "none") return null;
          const color = rgba(style.backgroundColor);
          if (color[3] > 0) layers.push(color);
          if (color[3] >= 1) break;
        }
        let base = [255, 255, 255];
        for (let i = layers.length - 1; i >= 0; i--) base = over(layers[i], base);
        return base;
      };
      const luminance = (rgb: number[]) => {
        const [r, g, b] = rgb.map((v) => {
          const c = v / 255;
          return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
        });
        return 0.2126 * r + 0.7152 * g + 0.0722 * b;
      };

      const alternatives = [...words]
        .sort((a, b) => b.length - a.length)
        .map((word) => word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/ /g, "\\s+"));
      const banned = new RegExp(`(?<![\\p{L}\\p{N}])(${alternatives.join("|")}|${idPattern})(?![\\p{L}\\p{N}])`, "giu");

      const texts: [Element, string][] = [];
      for (const el of document.body.querySelectorAll("*")) {
        if (["SCRIPT", "STYLE", "NOSCRIPT", "TEMPLATE"].includes(el.tagName)) continue;
        const text = ownText(el);
        if (text && shows(el)) texts.push([el, text]);
      }
      const controls: [Element, string][] = [];
      for (const el of document.body.querySelectorAll("button, a[href], input, select, [role=button]")) {
        if (el instanceof HTMLInputElement && el.type === "hidden") continue;
        if (el.matches(":disabled") || el.getAttribute("aria-disabled") === "true") continue;
        if (!shows(el)) continue;
        controls.push([el, el.getAttribute("aria-label") || ownText(el) || el.textContent || ""]);
      }
      // A target is its test id or holder, tag and class alone, so rewording
      // keeps its key; only where two visible elements share that does the
      // text tell them apart.
      const shared = new Map<string, number>();
      for (const el of new Set([...texts, ...controls].map(([el]) => el))) {
        shared.set(base(el), (shared.get(base(el)) ?? 0) + 1);
      }
      const describe = (el: Element, label: string) => {
        const text = mask(label);
        return (shared.get(base(el)) ?? 0) > 1 && text ? `${base(el)} "${text}"` : base(el);
      };

      for (const [el, text] of texts) {
        const target = describe(el, text);
        const style = getComputedStyle(el);

        for (const match of text.matchAll(banned)) {
          out.push({
            rule: "banned-word",
            target: `"${clean(match[1]).toLowerCase()}" in ${target}`,
            detail: text.slice(0, 120),
          });
        }

        const size = parseFloat(style.fontSize);
        if (size < minText - 0.01) {
          out.push({ rule: "small-text", target, detail: `${size} px: ${text.slice(0, 80)}` });
        }

        if (el.closest(":disabled, [aria-disabled='true']")) continue;
        const back = backdrop(el);
        if (back === null) continue;
        const ink = rgba(el instanceof SVGElement ? style.fill : style.color);
        if (ink[3] === 0) continue;
        const fore = over(ink, back);
        const [light, dark] = [luminance(fore), luminance(back)].sort((a, b) => b - a);
        const ratio = (light + 0.05) / (dark + 0.05);
        if (ratio < minContrast) {
          out.push({
            rule: "contrast",
            target,
            detail: `${ratio.toFixed(2)}:1, rgb(${fore.map(Math.round).join(", ")}) on rgb(${back.map(Math.round).join(", ")})`,
          });
        }
      }

      for (const [el, label] of controls) {
        const rect = el.getBoundingClientRect();
        if (rect.width + 0.5 >= minTarget && rect.height + 0.5 >= minTarget) continue;
        out.push({
          rule: "small-target",
          target: describe(el, label),
          detail: `${rect.width.toFixed(1)} x ${rect.height.toFixed(1)} px`,
        });
      }
      return out;
    },
    {
      words: BANNED_WORDS,
      idPattern: ID_PATTERN,
      minText: MIN_TEXT_PX,
      minTarget: MIN_TARGET_PX,
      minContrast: MIN_CONTRAST,
    },
  );
  for (const finding of measured) {
    found.push({ rule: finding.rule as GrandmaRule, step, viewport, target: finding.target, detail: finding.detail });
  }

  // One violation per key: the same label twice on a screen is one fix.
  const unique = new Map<string, Violation>();
  for (const violation of found) if (!unique.has(violationKey(violation))) unique.set(violationKey(violation), violation);
  return [...unique.values()];
}

/** The listed violations, refusing a malformed or duplicated entry. */
export function loadAllowlist(): AllowlistEntry[] {
  const raw = JSON.parse(readFileSync(allowlistPath, "utf8")) as { entries?: unknown };
  if (!Array.isArray(raw.entries)) throw new Error(`${allowlistPath} needs an "entries" array`);
  const seen = new Set<string>();
  return raw.entries.map((value: unknown, index: number) => {
    const entry = value as Partial<AllowlistEntry>;
    const where = `${allowlistPath} entry ${index}`;
    if (!entry.rule || !RULES.includes(entry.rule)) throw new Error(`${where}: unknown rule ${String(entry.rule)}`);
    for (const field of ["step", "viewport", "target"] as const) {
      if (typeof entry[field] !== "string" || entry[field] === "") throw new Error(`${where}: needs ${field}`);
    }
    if (typeof entry.ticket !== "string" || !/^#\d+$/.test(entry.ticket)) {
      throw new Error(`${where}: needs the open ticket that removes it, such as "#157"`);
    }
    const key = violationKey(entry as AllowlistEntry);
    if (seen.has(key)) throw new Error(`${where}: duplicates ${key}`);
    seen.add(key);
    return entry as AllowlistEntry;
  });
}

/** What a run found that the list does not hold, and what the list holds that the run did not find. */
export function compareWithAllowlist(
  violations: Violation[],
  allowlist: AllowlistEntry[],
): { unlisted: string[]; stale: string[] } {
  const listed = new Set(allowlist.map(violationKey));
  const occurred = new Set(violations.map(violationKey));
  return {
    unlisted: violations
      .filter((v) => !listed.has(violationKey(v)))
      .map((v) => `${violationKey(v)} (${v.detail})`),
    stale: allowlist
      .filter((entry) => !occurred.has(violationKey(entry)))
      .map((entry) => `${violationKey(entry)} (listed for ${entry.ticket}; fixed, so remove the entry)`),
  };
}
