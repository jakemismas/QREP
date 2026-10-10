/**
 * No-horizontal-overflow guard (C10; web-02, ux-04, ux-17). Every UI PR keeps
 * its screens inside 390 and 1440 px with this (plan section 5.C rules).
 *
 * Two checks, because a phone hides overflow differently from a desktop:
 * - documentElement.scrollWidth > clientWidth: the page scrolls sideways
 *   (ux-17: hidden tooltips made a 1440 px page 1486 px wide).
 * - window.innerWidth > the viewport width the test set: under device
 *   emulation the layout viewport grows to fit the overflow, so scrollWidth
 *   and clientWidth both report the grown width and agree (web-02: innerWidth
 *   470 on a 390 px phone). Without emulation innerWidth always equals the
 *   viewport width, so this check costs nothing there.
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

// Sub-pixel layout rounding is not overflow.
const TOLERANCE_PX = 0.5;

export async function expectNoHorizontalOverflow(page: Page, name: string): Promise<void> {
  const viewport = page.viewportSize();
  if (!viewport) throw new Error("expectNoHorizontalOverflow needs a fixed viewport");
  const deviceWidth = viewport.width;

  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: path.join(layoutDir, `${name}-${deviceWidth}.png`),
    fullPage: true,
  });

  const measured = await page.evaluate(
    ({ limit, tolerance }) => {
      const pastEdge = (el: Element) => {
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.right > limit + tolerance;
      };
      // Name only the outermost element past the edge, so the message points
      // at the box to fix rather than every descendant inside it.
      const offenders: string[] = [];
      for (const el of document.body.querySelectorAll("*")) {
        if (!pastEdge(el)) continue;
        const parent = el.parentElement;
        if (parent && parent !== document.body && pastEdge(parent)) continue;
        const testId = el.getAttribute("data-testid");
        const classes = [...el.classList].map((c) => `.${c}`).join("");
        const right = el.getBoundingClientRect().right.toFixed(1);
        offenders.push(
          `${el.tagName.toLowerCase()}${testId ? `[data-testid=${testId}]` : ""}${classes} ends at ${right}`,
        );
      }
      const root = document.documentElement;
      return {
        scrollWidth: root.scrollWidth,
        clientWidth: root.clientWidth,
        innerWidth: window.innerWidth,
        offenders: offenders.slice(0, 8).join("; ") || "none found",
      };
    },
    { limit: deviceWidth, tolerance: TOLERANCE_PX },
  );

  expect(
    measured.scrollWidth,
    `${name} at ${deviceWidth} px: the page is ${measured.scrollWidth} px wide in a ` +
      `${measured.clientWidth} px viewport; past the edge: ${measured.offenders}`,
  ).toBeLessThanOrEqual(measured.clientWidth);
  expect(
    measured.innerWidth,
    `${name} at ${deviceWidth} px: the layout viewport grew to ${measured.innerWidth} px; ` +
      `past the edge: ${measured.offenders}`,
  ).toBeLessThanOrEqual(deviceWidth);
}
