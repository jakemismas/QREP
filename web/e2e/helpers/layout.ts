/**
 * No-horizontal-overflow guard (C10; web-02, ux-04, ux-17). Every UI PR keeps
 * its screens inside 390 and 1440 px with this (plan section 5.C rules).
 *
 * Three checks, because content can leave a screen three ways:
 * - documentElement.scrollWidth > clientWidth: the page scrolls sideways
 *   (ux-17: hidden tooltips made a 1440 px page 1486 px wide).
 * - window.innerWidth > the viewport width the test set: under device
 *   emulation the layout viewport grows to take in the overflow (web-02:
 *   innerWidth 470 on a 390 px phone), and comparing innerWidth with the set
 *   width catches that growth whatever the two scroll measures say. Without
 *   emulation innerWidth always equals the viewport width, so this check
 *   costs nothing there.
 * - an element starts left of x 0: content pushed past the left edge adds no
 *   scroll width, so neither check above sees it, and it cannot be scrolled
 *   to. Ancestors that clip their overflow are applied first, so content
 *   scrolled or animated inside a clipping box does not count, and hidden
 *   elements are skipped: keep closed off-canvas UI hidden.
 *
 * The scroll checks do not see position: fixed boxes past the right edge,
 * which add nothing to the page's scroll width: a spec that opens fixed UI (a
 * tooltip, a toast, a modal) asserts its bounds itself, as layout.spec.ts
 * does for the header tips.
 *
 * The screenshot lands under test-results/spike/, which CI's web-spike job
 * uploads as spike-artifacts. It is a record for review, never compared:
 * web/src/golden-discipline.test.ts bans snapshot assertions.
 */
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, type Page } from "@playwright/test";

const layoutDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
  "test-results",
  "spike",
  "layout",
);

// Element edges are fractional: a sub-pixel spill from layout rounding is not
// overflow. The scroll checks compare whole pixels the browser already rounded.
const TOLERANCE_PX = 0.5;

export async function expectNoHorizontalOverflow(page: Page, name: string): Promise<void> {
  const viewport = page.viewportSize();
  if (!viewport) throw new Error("expectNoHorizontalOverflow needs a fixed viewport");
  const deviceWidth = viewport.width;

  await page.evaluate(() => document.fonts.ready);
  // Screens fade in; disabling animations finishes them, so the record shows
  // the settled screen and the measurement below sees its final layout.
  await page.screenshot({
    path: path.join(layoutDir, `${name}-${deviceWidth}.png`),
    fullPage: true,
    animations: "disabled",
  });

  const measured = await page.evaluate(
    ({ limit, tolerance }) => {
      // The horizontal span an element shows once clipping ancestors apply. A
      // fixed box is placed against the viewport, so its ancestors do not clip it.
      const visibleSpan = (el: Element) => {
        const rect = el.getBoundingClientRect();
        let left = rect.left;
        let right = rect.right;
        if (getComputedStyle(el).position !== "fixed") {
          for (let up = el.parentElement; up && up !== document.body; up = up.parentElement) {
            if (getComputedStyle(up).overflowX === "visible") continue;
            const box = up.getBoundingClientRect();
            left = Math.max(left, box.left);
            right = Math.min(right, box.right);
          }
        }
        return { left, right };
      };
      const shows = (el: Element) =>
        el.getBoundingClientRect().width > 0 && getComputedStyle(el).visibility !== "hidden";
      const pastRight = (el: Element) => {
        const span = visibleSpan(el);
        return el.getBoundingClientRect().width > 0 && span.right > span.left && span.right > limit + tolerance;
      };
      const pastLeft = (el: Element) => {
        const span = visibleSpan(el);
        return shows(el) && span.right > span.left && span.left < -tolerance;
      };
      // Name only the outermost element past an edge, so the message points
      // at the box to fix rather than every descendant inside it.
      const outermost = (past: (el: Element) => boolean) => {
        const found: string[] = [];
        for (const el of document.body.querySelectorAll("*")) {
          if (!past(el)) continue;
          const parent = el.parentElement;
          if (parent && parent !== document.body && past(parent)) continue;
          const testId = el.getAttribute("data-testid");
          const classes = [...el.classList].map((c) => `.${c}`).join("");
          const rect = el.getBoundingClientRect();
          found.push(
            `${el.tagName.toLowerCase()}${testId ? `[data-testid=${testId}]` : ""}${classes} ` +
              `spans ${rect.left.toFixed(1)} to ${rect.right.toFixed(1)}`,
          );
        }
        return found.slice(0, 8);
      };
      const root = document.documentElement;
      return {
        scrollWidth: root.scrollWidth,
        clientWidth: root.clientWidth,
        innerWidth: window.innerWidth,
        pastRight: outermost(pastRight).join("; ") || "none found",
        pastLeft: outermost(pastLeft),
      };
    },
    { limit: deviceWidth, tolerance: TOLERANCE_PX },
  );

  expect(
    measured.scrollWidth,
    `${name} at ${deviceWidth} px: the page is ${measured.scrollWidth} px wide in a ` +
      `${measured.clientWidth} px viewport; past the edge: ${measured.pastRight}`,
  ).toBeLessThanOrEqual(measured.clientWidth);
  expect(
    measured.innerWidth,
    `${name} at ${deviceWidth} px: the layout viewport grew to ${measured.innerWidth} px; ` +
      `past the edge: ${measured.pastRight}`,
  ).toBeLessThanOrEqual(deviceWidth);
  expect(
    measured.pastLeft,
    `${name} at ${deviceWidth} px: content starts left of the viewport`,
  ).toEqual([]);
}
