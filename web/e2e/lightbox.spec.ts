/**
 * Photo-flow components in the editor (C1b; web-03). The lightbox's and the
 * round-trip panel's rules used to live in a style string that PhotoFlow
 * injected only while it was mounted, so the editor's "Compare with your
 * photo" rendered the lightbox unstyled (position static and a transparent
 * scrim at 834d8be, inline under the canvas) and the Pattern tab's
 * round-trip panel unstyled too. Their stylesheets now ship with the
 * components, so both are styled wherever they mount.
 *
 * The lightbox spec starts from the synthetic sample photo, which skips the
 * crop screen and still reaches the results screen's Open in the editor
 * until C6a removes the editor (REBASELINE.md moves photo.spec.ts's
 * session-only test to the same entry in C3c).
 *
 * Desktop only, as in layout.spec.ts: at 390 px the editor's header already
 * overflows (web-02, excluded until C6a), so the overflow guard would fail on
 * the header rather than on these components.
 */
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import { expectNoHorizontalOverflow } from "./helpers/layout";

// Beside the guard's own screenshots, which CI uploads as spike-artifacts.
const layoutDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "test-results",
  "spike",
  "layout",
);
const REVERSE_TIMEOUT = 300_000;
const READY_TIMEOUT = 300_000;

test.describe("photo-flow components in the editor at 1440 x 900", { tag: "@phone" }, () => {
  test.use({ viewport: { width: 1440, height: 900 }, isMobile: false, hasTouch: false });

  test("the compare lightbox overlays the viewport with a tinted scrim", async ({ page }) => {
    await page.goto("./");
    await page.getByTestId("start-photo").click();
    await page.getByTestId("photo-sample").click();
    await expect(page.getByTestId("photo-results")).toBeVisible({ timeout: REVERSE_TIMEOUT });
    await page.getByTestId("open-in-editor").click();
    await expect(page.getByTestId("editor")).toBeVisible();

    await page.getByTestId("open-lightbox").click();
    const lightbox = page.getByTestId("lightbox");
    await expect(lightbox).toBeVisible();

    // Source: Lightbox.css .pf-lb { position: fixed; inset: 0 }. A fixed box
    // with all four insets 0 spans the viewport less any scrollbar, which is
    // the root element's client box: x 0, y 0, width clientWidth, height
    // clientHeight.
    await expect(lightbox).toHaveCSS("position", "fixed");
    const client = await page.evaluate(() => ({
      width: document.documentElement.clientWidth,
      height: document.documentElement.clientHeight,
    }));
    const box = await lightbox.boundingBox();
    expect(box).toEqual({ x: 0, y: 0, width: client.width, height: client.height });

    // Source: web/src/ui/tokens.css:33, --modal-backdrop: rgba(18, 12, 6, 0.6),
    // set once for both themes. Its alpha 0.6 is above 0, so the scrim tints
    // the editor instead of the rgba(0, 0, 0, 0) web-03 measured.
    const scrim = lightbox.locator(".pf-lb-scrim");
    await expect(scrim).toHaveCSS("background-color", "rgba(18, 12, 6, 0.6)");
    // Source: Lightbox.css .pf-lb-scrim { position: absolute; inset: 0 }
    // inside the fixed root, so the scrim covers the same box as the root.
    await expect(scrim).toHaveCSS("position", "absolute");
    expect(await scrim.boundingBox()).toEqual(box);

    // web-03's other half: unstyled, the lightbox rendered inline and widened
    // the page. The guard's scroll checks cannot see a fixed box, so this
    // proves the editor underneath stays inside 1440 px with it open.
    await expectNoHorizontalOverflow(page, "editor-lightbox");

    // Escape closes it (Lightbox's keydown handler), back to the editor.
    await page.keyboard.press("Escape");
    await expect(lightbox).toHaveCount(0);
    await expect(page.getByTestId("editor")).toBeVisible();
  });

  test("the Pattern tab's round-trip panel is styled and holds its content", async ({ page }) => {
    await page.goto("./");
    await page.getByTestId("open-demo").click();
    await expect(page.getByTestId("editor")).toBeVisible();
    await expect(page.getByTestId("engine-chip")).toHaveAttribute("data-engine-phase", "ready", {
      timeout: READY_TIMEOUT,
    });
    await page.getByRole("tab", { name: "Pattern" }).click();
    let passed = false;
    try {
      const panel = page.getByTestId("roundtrip-panel");
      await expect(panel).toBeVisible();
      // Source: RoundTripPanel.css .pf-rt { display: flex; ... }. Unstyled, the
      // section element computes its default, block.
      await expect(panel).toHaveCSS("display", "flex");

      // Measure the tab once it settles. The strategy cards and the yardage
      // table above the panel fill in from bridge calls; that moves the panel
      // down, not sideways, so the horizontal checks below hold either way,
      // but the measurement and the record then show the tab a quilter sees.
      // Source: PatternPanel.tsx, each card's Metric values read "…" while
      // plans[k] is unset, and the yardage rows render only once the selected
      // plan's yardage and the summary arrive.
      for (const strategy of ["historical", "strip", "modern"]) {
        const card = page.getByTestId(`strategy-card-${strategy}`);
        await expect(card).toBeVisible();
        await expect(card).not.toContainText("…");
      }
      for (const row of ["binding", "backing", "batting"]) {
        await expect(page.getByTestId(`yardage-row-${row}`)).toBeVisible();
      }
      await page.evaluate(() => document.fonts.ready);

      // The page-level guard cannot pass on this tab yet: once its amounts fill
      // in, the yardage table runs past the side panel and the page (web-01,
      // fixed by C2b), with or without the round-trip rules. So this checks what
      // the panel holds: the panel stretches to the side panel's width, so its
      // own box always fits, but a control that does not wrap spills past its
      // right edge. Every descendant stays inside the panel, the panel's
      // content is no wider than the panel, and the panel ends inside 1440 px.
      // One evaluate re-checks the settled tab and measures the panel in a
      // single task, so no re-render can swap it out mid-measure. A missing or
      // doubled panel (the locator's strict mode), an unsettled card or a
      // zero-width panel fails at once instead of leaving a locator waiting
      // out the test timeout (#232) or measuring nothing.
      const fit = await page.evaluate(() => {
        const cards = Array.from(document.querySelectorAll('[data-testid^="strategy-card-"]'));
        const pending = cards.filter((card) => card.textContent?.includes("…")).length;
        if (cards.length !== 3 || pending > 0) {
          throw new Error(`expected three settled strategy cards, found ${cards.length} with ${pending} still pending`);
        }
        const found = document.querySelectorAll('[data-testid="roundtrip-panel"]');
        if (found.length !== 1) throw new Error(`expected one round-trip panel to measure, found ${found.length}`);
        const root = found[0];
        const box = root.getBoundingClientRect();
        if (box.width === 0) throw new Error("the round-trip panel has no width to measure");
        // Sub-pixel spill from layout rounding is not overflow (as in
        // helpers/layout.ts).
        const tolerance = 0.5;
        const spill = Array.from(root.querySelectorAll("*"))
          .map((el) => ({ el, r: el.getBoundingClientRect() }))
          .filter(({ r }) => r.width > 0 && (r.left < box.left - tolerance || r.right > box.right + tolerance))
          .map(({ el, r }) => `${el.tagName.toLowerCase()}.${el.getAttribute("class") ?? ""} spans ${r.left.toFixed(1)} to ${r.right.toFixed(1)}`);
        return { spill, scrollWidth: root.scrollWidth, clientWidth: root.clientWidth, right: box.right };
      });
      expect(fit.spill, "round-trip panel content past its edges").toEqual([]);
      expect(fit.scrollWidth).toBeLessThanOrEqual(fit.clientWidth);
      expect(fit.right).toBeLessThanOrEqual(1440);
      passed = true;
    } finally {
      // The record comes after the measurement, and on a failure too, when a
      // reviewer needs it most. It shows the viewport with the panel scrolled
      // into it, never a full-page capture: one of those can report a 1 x 1
      // window for a moment, which swaps in the phone editor and back and
      // reopens the desktop editor on its Fabrics tab (#232). Neither call
      // waits for an element, so a missing panel cannot hang it.
      const record = async (): Promise<void> => {
        await page.evaluate(() =>
          document.querySelector('[data-testid="roundtrip-panel"]')?.scrollIntoView({ block: "center" }),
        );
        await page.screenshot({
          path: path.join(layoutDir, "editor-pattern-roundtrip-1440.png"),
          animations: "disabled",
        });
      };
      // A failed record must not hide the failure that brought the test here.
      if (passed) await record();
      else await record().catch(() => undefined);
    }
  });
});
