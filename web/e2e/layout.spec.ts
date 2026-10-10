/**
 * Layout guard (C10; web-02, ux-04, ux-17): the start screen, the dropzone
 * and the crop screen stay inside a 390 x 844 phone (Chromium with the iPhone
 * 13 descriptor, until C7 adds WebKit) and a 1440 x 900 desktop, and the
 * header tooltips open below their controls inside the viewport.
 *
 * The editor screens are excluded: with a quilt open, the header's Open and
 * Save buttons widen it past 390 px (web-02), and C6a removes them along with
 * the editor. Screens added after C10 call expectNoHorizontalOverflow in
 * their own specs.
 *
 * The engine is held on its longest boot label for every check: the header is
 * widest then (ux-04), and a check that raced the boot would pass or fail by
 * timing. web/src/engine/worker.ts posts "Loading the Python engine" (25
 * characters) and then imports pyodide/pyodide.mjs; the other labels are
 * "Starting the engine" (19), "Loading engine packages" (23) and "Loading the
 * qrep engine" (23). Stalling that import holds the chip on the 25-character
 * label. The crop screen needs no engine to render its pins.
 */
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { devices, expect, test, type BrowserContext, type Page } from "@playwright/test";
import { expectNoHorizontalOverflow } from "./helpers/layout";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const photoFixture = path.join(
  repoRoot,
  "tests",
  "fixtures",
  "photoreal",
  "screenshot_composite_1400.png",
);
const LONGEST_BOOT_LABEL = "Loading the Python engine";
const PHONE = { width: 390, height: 844 };
const DESKTOP = { width: 1440, height: 900 };
const iPhone = devices["iPhone 13"];

async function holdEngineBooting(context: BrowserContext, page: Page) {
  // An unanswered route keeps the worker's dynamic import pending for the
  // whole test; the context closes it at teardown.
  await context.route("**/pyodide/pyodide.mjs", () => {});
  await page.goto("./");
  await expect(page.getByTestId("engine-chip")).toHaveText(LONGEST_BOOT_LABEL);
}

async function checkPhotoScreens(context: BrowserContext, page: Page) {
  await holdEngineBooting(context, page);
  await expect(page.getByTestId("start-photo")).toBeVisible();
  await expectNoHorizontalOverflow(page, "start");

  await page.getByTestId("start-photo").click();
  await expect(page.getByTestId("photo-dropzone")).toBeVisible();
  await expectNoHorizontalOverflow(page, "dropzone");

  await page.getByTestId("photo-file-input").setInputFiles(photoFixture);
  await expect(page.getByTestId("crop-screen")).toBeVisible();
  await expect(page.getByTestId("corner-pin-0")).toBeVisible();
  await expectNoHorizontalOverflow(page, "crop");
}

test.describe("layout at 390 x 844 (iPhone emulation)", { tag: "@phone" }, () => {
  test.use({
    viewport: PHONE,
    userAgent: iPhone.userAgent,
    deviceScaleFactor: iPhone.deviceScaleFactor,
    isMobile: iPhone.isMobile,
    hasTouch: iPhone.hasTouch,
  });

  test("start screen, dropzone and crop screen stay inside the phone", async ({
    context,
    page,
  }) => {
    await checkPhotoScreens(context, page);
  });
});

test.describe("layout at 1440 x 900", { tag: "@phone" }, () => {
  test.use({ viewport: DESKTOP });

  test("start screen, dropzone and crop screen stay inside the desktop", async ({
    context,
    page,
  }) => {
    await checkPhotoScreens(context, page);
  });

  test("header tooltips open below their controls, inside the viewport", async ({
    context,
    page,
  }) => {
    await holdEngineBooting(context, page);
    const header = page.locator(".qrep-header");
    const controls = [
      { name: "logo", control: header.getByRole("button", { name: "Back to the start screen" }) },
      { name: "engine", control: page.getByTestId("engine-chip") },
      { name: "theme", control: page.getByTestId("theme-toggle") },
    ];
    for (const { name, control } of controls) {
      await control.hover();
      const tip = page.getByRole("tooltip");
      await expect(tip).toHaveCount(1);
      await expect(tip).toBeVisible();
      if (name === "engine") {
        // MOCK-NOTES.md:603, its em dash replaced (criterion text, issue #159).
        await expect(tip).toHaveText(
          "The Python engine runs in your browser, and it boots in a few seconds on first load.",
        );
      } else {
        await expect(tip).toHaveText((await control.getAttribute("aria-label")) ?? "");
      }
      const controlBox = (await control.boundingBox())!;
      const tipBox = (await tip.boundingBox())!;
      // Below: the tip's top edge is at or under the control's bottom edge.
      expect(tipBox.y, `${name} tip top`).toBeGreaterThanOrEqual(controlBox.y + controlBox.height);
      // Inside: 0 <= left and right <= 1440.
      expect(tipBox.x, `${name} tip left`).toBeGreaterThanOrEqual(0);
      expect(tipBox.x + tipBox.width, `${name} tip right`).toBeLessThanOrEqual(DESKTOP.width);
      await expectNoHorizontalOverflow(page, `tooltip-${name}`);
      // Moving off the control hides the tip again.
      await page.mouse.move(DESKTOP.width / 2, DESKTOP.height - 10);
      await expect(page.getByRole("tooltip")).toHaveCount(0);
    }
  });
});
