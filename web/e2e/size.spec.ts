/**
 * Size e2e on Your pattern (C2b, issue #148), re-expressed from the sprint 3
 * size UI (issue #73) as docs/sprint-5/REBASELINE.md records. DOM contract:
 * see-sample on the start screen opens your-pattern for the hand-authored
 * double Irish chain (tests/fixtures/double_irish_chain.json: 45 columns x 55
 * rows of 12 e squares and one 30 e border; e = eighths of an inch). Its size
 * control pattern-size holds pattern-size-line (data-size-kind default, typed
 * or preset), pattern-size-asked when the achieved size misses the request,
 * the chips pattern-size-chip-<name> from bridge.presets(), the typed
 * pattern-size-width and pattern-size-height, the pattern-size-unit toggle
 * and pattern-size-apply.
 *
 * The sample needs no photo, so nothing is rendered before these tests. A
 * size goes through bridge.size_pattern with no re-read and no progress
 * screen (criterion U3-15). The achieved sizes below follow SPEC.md section
 * 6.3 (A10): offered squares s = 6 to 32 e in steps of 2 e; the border scales
 * with the square and snaps to the nearest 1/4 in half-up, so border(s) =
 * 2 x round_div(30 s, 24) with round_div(a, b) = (a + b // 2) // b; W = 45 s
 * + 2 border(s) and H = 55 s + 2 border(s); the smallest combined miss
 * |W - asked W| + |H - asked H| wins, and a tie goes to the larger square.
 */
import { expect, test, type Page } from "@playwright/test";

const READY_TIMEOUT = 300_000;
// Every summary comes from export_pattern, which builds the whole pattern PDF
// in the browser engine, and a size runs size_pattern before it; 60 s is the
// wait the sprint 3 version of these tests gave an applied size.
const SIZE_TIMEOUT = 60_000;
const PHONE_WIDTH = 400;
// Element edges are fractional; the C10 guard (helpers/layout.ts) allows the
// same half pixel of layout rounding.
const TOLERANCE_PX = 0.5;

async function openSamplePattern(page: Page): Promise<void> {
  await page.goto("./");
  await page.getByTestId("see-sample").click();
  await expect(page.getByTestId("your-pattern")).toBeVisible();
  await expect(page.getByTestId("engine-chip")).toHaveAttribute("data-engine-phase", "ready", {
    timeout: READY_TIMEOUT,
  });
}

/** Record every engine method the page sends to the worker, and whether the
 * photo progress screen ever mounts, from before the app's first script. */
async function watchEngineCalls(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const seen = window as unknown as { engineCalls: string[]; sawProgress: boolean };
    seen.engineCalls = [];
    seen.sawProgress = false;
    const post = Worker.prototype.postMessage;
    Worker.prototype.postMessage = function (this: Worker, ...args: unknown[]) {
      const message = args[0] as { type?: string; method?: string } | null;
      if (message?.type === "call" && typeof message.method === "string") {
        seen.engineCalls.push(message.method);
      }
      return (post as (...rest: unknown[]) => void).apply(this, args);
    } as typeof Worker.prototype.postMessage;
    const watch = () => {
      new MutationObserver(() => {
        if (document.querySelector("[data-testid='photo-progress']")) seen.sawProgress = true;
      }).observe(document.documentElement, { childList: true, subtree: true });
    };
    if (document.documentElement) watch();
    else document.addEventListener("DOMContentLoaded", watch);
  });
}

async function typeSize(page: Page, width: string, height: string): Promise<void> {
  await page.getByTestId("pattern-size-width").fill(width);
  await page.getByTestId("pattern-size-height").fill(height);
  await page.getByTestId("pattern-size-apply").click();
}

test("86 x 67.5 entered at crop flows to achieved size, asked-vs-got, and the editor", async ({
  page,
}) => {
  // Re-expressed (REBASELINE.md): the size is typed on Your pattern's size
  // control for the sample instead of at the crop screen, and the editor's
  // Sizing-tab tail leaves with the Sizing tab (C6a).
  await openSamplePattern(page);
  const line = page.getByTestId("pattern-size-line");
  await expect(line).toHaveAttribute("data-size-kind", "default", { timeout: SIZE_TIMEOUT });

  await typeSize(page, "86", "67.5");

  // Asked 86 x 67 1/2 in = 688 x 540 e. With the header's rule:
  // - s = 8: border 2 x round_div(240, 24) = 2 x 10 = 20; W = 360 + 40 = 400,
  //   H = 440 + 40 = 480; miss 288 + 60 = 348.
  // - s = 10: border 2 x round_div(300, 24) = 2 x (312 // 24) = 2 x 13 = 26;
  //   W = 450 + 52 = 502, H = 550 + 52 = 602; miss 186 + 62 = 248.
  // - s = 12: border 2 x round_div(360, 24) = 2 x 15 = 30; W = 540 + 60 = 600,
  //   H = 660 + 60 = 720; miss 88 + 180 = 268.
  // - s = 14: border 2 x round_div(420, 24) = 2 x (432 // 24) = 2 x 18 = 36;
  //   W = 630 + 72 = 702, H = 770 + 72 = 842; miss 14 + 302 = 316.
  // Up to s = 8 both sides fall short (H <= 480 < 540), so the miss is
  // 1228 - (W + H) and falls as s grows: s = 8 is the best of them at 348.
  // For s = 10 and 12, W < 688 and H > 540, so the miss is 148 + (H - W) =
  // 148 + 10 s and rises with s. From s = 14 both sides overshoot, so the miss
  // is W + H - 1228 and rises with s. So s = 10 (1 1/4 in squares) wins:
  // 502 x 602 e = 62 6/8 x 75 2/8 in = 62 3/4 x 75 1/4 in, as SPEC.md section
  // 6.3 states for this request (misses 23 1/4 and 7 3/4 in).
  await expect(line).toHaveAttribute("data-size-kind", "typed", { timeout: SIZE_TIMEOUT });
  await expect(line).toContainText("62 3/4 x 75 1/4 in", { timeout: SIZE_TIMEOUT });

  // Asked and got differ, so the asked-vs-got line shows both.
  const asked = page.getByTestId("pattern-size-asked");
  await expect(asked).toBeVisible();
  await expect(asked).toContainText("86");
  await expect(asked).toContainText("67 1/2");
  await expect(asked).toContainText("62 3/4 x 75 1/4 in");
});

test("inline size edit from results sticks without a re-run", async ({ page }) => {
  // Re-expressed (REBASELINE.md): the size is edited on Your pattern for the
  // sample instead of the results screen; it applies with no re-read and no
  // progress screen (criterion U3-15).
  await watchEngineCalls(page);
  await openSamplePattern(page);

  // A size QREP chose is labeled a default, never a guess printed as fact
  // (HANDOFF 5; PS-09). The fixture as drawn is 45 x 12 + 2 x 30 = 600 e =
  // 75 in wide and 55 x 12 + 2 x 30 = 720 e = 90 in high.
  const control = page.getByTestId("pattern-size");
  const line = page.getByTestId("pattern-size-line");
  await expect(line).toHaveAttribute("data-size-kind", "default", { timeout: SIZE_TIMEOUT });
  await expect(line).toContainText("Default size");
  await expect(line).toContainText("75 x 90 in");
  await expect(control).not.toContainText(/guess/i);

  await typeSize(page, "45", "54");

  // Asked 45 x 54 in = 360 x 432 e. With the header's rule:
  // - s = 6: border 2 x round_div(180, 24) = 2 x (192 // 24) = 2 x 8 = 16;
  //   W = 270 + 32 = 302, H = 330 + 32 = 362; miss 58 + 70 = 128.
  // - s = 8: border 2 x round_div(240, 24) = 2 x 10 = 20; W = 360 + 40 = 400,
  //   H = 440 + 40 = 480; miss 40 + 48 = 88.
  // - s = 10: border 26; W = 502, H = 602; miss 142 + 170 = 312.
  // From s = 8 up both sides overshoot and grow with s, so the miss only
  // grows; s = 6 is the smallest square offered. So s = 8 (1 in squares)
  // wins: 400 x 480 e = 50 x 60 in.
  await expect(line).toHaveAttribute("data-size-kind", "typed", { timeout: SIZE_TIMEOUT });
  await expect(line).toContainText("50 x 60 in", { timeout: SIZE_TIMEOUT });
  await expect(line).toContainText("Your size");
  await expect(page.getByTestId("pattern-size-asked")).toContainText("45 x 54 in");
  await expect(control).not.toContainText(/guess/i);

  // No progress screen at any point, and the size came from size_pattern
  // with no read of a photo.
  await expect(page.getByTestId("photo-progress")).toHaveCount(0);
  const seen = await page.evaluate(() => {
    const w = window as unknown as { engineCalls: string[]; sawProgress: boolean };
    return { calls: w.engineCalls, sawProgress: w.sawProgress };
  });
  expect(seen.sawProgress).toBe(false);
  expect(seen.calls).toContain("size_pattern");
  expect(seen.calls).not.toContain("reverse_photo");
});

test("size block renders usable at phone width", async ({ page }) => {
  // Re-expressed (REBASELINE.md): Your pattern's size control is usable at
  // 400 px.
  await page.setViewportSize({ width: PHONE_WIDTH, height: 800 });
  await openSamplePattern(page);

  const control = page.getByTestId("pattern-size");
  await expect(control).toBeVisible();
  await expect(page.getByTestId("pattern-size-chip-king")).toBeVisible();
  await expect(page.getByTestId("pattern-size-chip-king")).toBeEnabled();
  for (const testId of ["pattern-size-width", "pattern-size-height", "pattern-size-apply"]) {
    await expect(page.getByTestId(testId)).toBeVisible();
    await expect(page.getByTestId(testId)).toBeEnabled();
  }

  // The control and everything in it fit the 400 px viewport.
  const fit = await control.evaluate(
    (root, { limit, tolerance }) => {
      const outside: string[] = [];
      for (const el of [root, ...root.querySelectorAll("*")]) {
        const rect = el.getBoundingClientRect();
        if (rect.width === 0) continue;
        if (rect.left < -tolerance || rect.right > limit + tolerance) {
          const testId = el.getAttribute("data-testid");
          const classes = [...el.classList].map((c) => `.${c}`).join("");
          outside.push(
            `${el.tagName.toLowerCase()}${testId ? `[data-testid=${testId}]` : ""}${classes} ` +
              `spans ${rect.left.toFixed(1)} to ${rect.right.toFixed(1)}`,
          );
        }
      }
      return { outside, scrollWidth: root.scrollWidth, clientWidth: root.clientWidth };
    },
    { limit: PHONE_WIDTH, tolerance: TOLERANCE_PX },
  );
  expect(fit.outside).toEqual([]);
  expect(fit.scrollWidth).toBeLessThanOrEqual(fit.clientWidth);
});
