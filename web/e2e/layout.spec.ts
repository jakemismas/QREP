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
 * The engine is held on its longest boot label for every screen check: the
 * header is widest then (ux-04), and a check that raced the boot would pass or
 * fail by timing. web/src/engine/worker.ts posts "Loading the Python engine"
 * (25 characters) and then imports pyodide/pyodide.mjs; the other labels are
 * "Starting the engine" (19), "Loading engine packages" (23), "Loading the
 * qrep engine" (23) and rpc.ts's fallback "Loading the engine" (18). Stalling
 * that import holds the chip on the 25-character label. The crop screen needs
 * no engine to render its pins, so it is checked while it looks for the quilt.
 * Aborting the same import instead fails the boot, which shows the failed
 * chip with its message and a Retry button.
 *
 * The 1440 tests pin isMobile and hasTouch off, because C7's iPhone project
 * runs every @phone spec with both on, and tips are desktop-only (hidden under
 * 720 px and on coarse pointers).
 */
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import {
  devices,
  expect,
  test,
  type BrowserContext,
  type Locator,
  type Page,
} from "@playwright/test";
import { expectNoHorizontalOverflow } from "./helpers/layout";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const photoFixture = path.join(
  repoRoot,
  "tests",
  "fixtures",
  "photoreal",
  "screenshot_composite_1400.png",
);
const ENGINE_IMPORT = "**/pyodide/pyodide.mjs";
const LONGEST_BOOT_LABEL = "Loading the Python engine";
const FAILED_TIMEOUT = 120_000;
const PHONE = { width: 390, height: 844 };
const DESKTOP = { width: 1440, height: 900 };
const DESKTOP_OPTIONS = { viewport: DESKTOP, isMobile: false, hasTouch: false };
const iPhone = devices["iPhone 13"];

async function holdEngineBooting(context: BrowserContext, page: Page) {
  // An unanswered route keeps the worker's dynamic import pending for the
  // whole test; the context closes it at teardown.
  await context.route(ENGINE_IMPORT, () => {});
  await page.goto("./");
  await expect(page.getByTestId("engine-chip")).toHaveText(LONGEST_BOOT_LABEL);
}

async function failEngineBoot(context: BrowserContext, page: Page) {
  await context.route(ENGINE_IMPORT, (route) => route.abort());
  await page.goto("./");
  await expect(page.getByTestId("engine-chip")).toHaveAttribute("data-engine-phase", "failed", {
    timeout: FAILED_TIMEOUT,
  });
}

async function expectHeaderInside(page: Page, name: string) {
  await expectNoHorizontalOverflow(page, name);
  // ux-04's symptom directly: a header that clipped its own overflow would
  // keep the page narrow and still cut the theme toggle off.
  await expect(page.getByTestId("theme-toggle")).toBeInViewport({ ratio: 1 });
}

async function expectBootScreenInside(page: Page, name: string) {
  // Criterion 4 holds the header in while the chip shows its boot label, so
  // the label must be on screen, not hidden or squeezed to nothing.
  const chip = page.getByTestId("engine-chip");
  const label = chip.locator(".q-chip__label");
  await expect(chip).toHaveText(LONGEST_BOOT_LABEL);
  await expect(label).toBeVisible();
  expect((await label.boundingBox())!.width, `${name}: boot label width`).toBeGreaterThan(0);
  await expectHeaderInside(page, name);
}

async function checkPhotoScreens(context: BrowserContext, page: Page) {
  await holdEngineBooting(context, page);
  await expect(page.getByTestId("start-photo")).toBeVisible();
  await expectBootScreenInside(page, "start");

  await page.getByTestId("start-photo").click();
  await expect(page.getByTestId("photo-dropzone")).toBeVisible();
  await expectBootScreenInside(page, "dropzone");

  await page.getByTestId("photo-file-input").setInputFiles(photoFixture);
  await expect(page.getByTestId("crop-screen")).toBeVisible();
  await expect(page.getByTestId("corner-pin-0")).toBeVisible();
  await expectBootScreenInside(page, "crop");
}

/** Hovers or focuses `control`, then checks its one open tip against the criterion. */
async function expectTipBelow(page: Page, control: Locator, name: string, tips: string[]) {
  const tip = page.locator('[role="tooltip"]');
  await expect(tip).toHaveCount(1);
  await expect(tip).toBeVisible();
  expect(tips).toContain(await tip.textContent());
  const controlBox = (await control.boundingBox())!;
  const tipBox = (await tip.boundingBox())!;
  // Below: the tip's top edge is at or under the control's bottom edge.
  expect(tipBox.y, `${name} tip top`).toBeGreaterThanOrEqual(controlBox.y + controlBox.height);
  // Inside: 0 <= left and right <= 1440.
  expect(tipBox.x, `${name} tip left`).toBeGreaterThanOrEqual(0);
  expect(tipBox.x + tipBox.width, `${name} tip right`).toBeLessThanOrEqual(DESKTOP.width);
}

async function moveOffEveryControl(page: Page) {
  await page.mouse.move(DESKTOP.width / 2, DESKTOP.height - 10);
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

  test("a failed engine shows its whole message and Retry inside the phone", async ({
    context,
    page,
  }) => {
    await failEngineBoot(context, page);
    const label = page.getByTestId("engine-chip").locator(".q-chip__label");
    for (const screen of ["start", "dropzone"]) {
      if (screen === "dropzone") {
        await page.getByTestId("start-photo").click();
        await expect(page.getByTestId("photo-dropzone")).toBeVisible();
      }
      await expect(label).toBeVisible();
      // The message is never cut: the label's content fits inside its box.
      const cut = await label.evaluate(
        (el) => el.scrollWidth > el.clientWidth || el.scrollHeight > el.clientHeight,
      );
      expect(cut, `${screen}: failure message cut`).toBe(false);
      await expect(page.getByTestId("engine-retry")).toBeInViewport({ ratio: 1 });
      await expectHeaderInside(page, `failed-${screen}`);
    }
  });
});

test.describe("layout at 1440 x 900", { tag: "@phone" }, () => {
  test.use(DESKTOP_OPTIONS);

  test("start screen, dropzone and crop screen stay inside the desktop", async ({
    context,
    page,
  }) => {
    await checkPhotoScreens(context, page);
  });
});

test.describe("header tooltips at 1440 x 900", { tag: "@phone" }, () => {
  test.use(DESKTOP_OPTIONS);

  test("header tooltips open below their controls, inside the viewport", async ({
    context,
    page,
  }) => {
    await holdEngineBooting(context, page);
    const header = page.locator(".qrep-header");
    // Counted with hidden ones included: a closed tip is not in the DOM at all.
    const anyTip = page.locator('[role="tooltip"]');
    await moveOffEveryControl(page);
    await expect(anyTip).toHaveCount(0);
    // Tip copy: MOCK-NOTES.md:603 (logo; engine chip, its em dash replaced as
    // issue #159 words it) and MOCK-NOTES.md:373 (the theme toggle, by skin).
    const controls = [
      {
        name: "logo",
        control: header.getByRole("button", { name: "Back to the start screen" }),
        tips: ["Back to the start screen"],
      },
      {
        name: "engine",
        control: page.getByTestId("engine-chip"),
        tips: ["The Python engine runs in your browser, and it boots in a few seconds on first load."],
      },
      {
        name: "theme",
        control: page.getByTestId("theme-toggle"),
        tips: ["Switch to evening mode", "Switch to daylight mode"],
      },
    ];
    for (const { name, control, tips } of controls) {
      await control.hover();
      await expectTipBelow(page, control, name, tips);
      await expectNoHorizontalOverflow(page, `tooltip-${name}`);
      await moveOffEveryControl(page);
      await expect(anyTip).toHaveCount(0);
    }
  });

  test("the project-name tip opens below the name, inside the viewport", async ({
    context,
    page,
  }) => {
    // The name shows only with a quilt open; the demo opens without the engine.
    await holdEngineBooting(context, page);
    await page.getByTestId("open-demo").click();
    await expect(page.getByTestId("editor")).toBeVisible();
    const name = page.getByTestId("project-name");
    await name.hover();
    // MOCK-NOTES.md:603 lists this copy with a dash between its two parts;
    // the house text rules replace that dash with a colon.
    await expectTipBelow(page, name, "project-name", ["Project name: click to rename"]);
  });

  test("a tip closes when its focused control goes away", async ({ context, page }) => {
    // Retry is focusable and unmounts when pressed: the chip goes back to
    // booting. The first boot fails; the retried one is held booting.
    let failBoot = true;
    await context.route(ENGINE_IMPORT, (route) => (failBoot ? route.abort() : undefined));
    await page.goto("./");
    const chip = page.getByTestId("engine-chip");
    await expect(chip).toHaveAttribute("data-engine-phase", "failed", { timeout: FAILED_TIMEOUT });
    failBoot = false;
    await moveOffEveryControl(page);
    const anyTip = page.locator('[role="tooltip"]');
    await page.getByTestId("engine-retry").focus();
    await expect(anyTip).toHaveCount(1);
    await page.keyboard.press("Enter");
    await expect(chip).toHaveAttribute("data-engine-phase", "booting");
    await expect(page.getByTestId("engine-retry")).toHaveCount(0);
    await expect(anyTip).toHaveCount(0);
  });
});
