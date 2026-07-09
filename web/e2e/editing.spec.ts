/**
 * S3 editing e2e (issue #43). Defines the editing DOM contract:
 *  - toolbar: mode-paint / mode-move, quick swatches swatch-<fabricId>
 *  - canvas exposes its live transform as data attributes so tests can
 *    compute cell coordinates: data-view-scale (px per eighth),
 *    data-view-origin-x / data-view-origin-y (canvas-relative px of the
 *    quilt's top-left corner)
 *  - undo / redo buttons; palette rows fabric-rename-<id>, fabric-color-<id>,
 *    delete-fabric-<id>, add-fabric; save-project; start-blank;
 *    resume-banner / resume-accept / autosave-error
 *
 * Paint verification goes through the ENGINE: every mutation commit
 * re-validates via the bridge, so the fabric census in the panel is the
 * ground truth (PARITY item 1). Census literals: 1246 blue / 1229 cream.
 * Autosave localStorage key: qrep-autosave.
 */
import { expect, test, type Page } from "@playwright/test";

const READY_TIMEOUT = 300_000;

interface CellPoint {
  x: number;
  y: number;
}

async function cellPoint(page: Page, row: number, col: number): Promise<CellPoint> {
  const canvas = page.getByTestId("quilt-canvas");
  const box = (await canvas.boundingBox())!;
  const scale = Number(await canvas.getAttribute("data-view-scale"));
  const originX = Number(await canvas.getAttribute("data-view-origin-x"));
  const originY = Number(await canvas.getAttribute("data-view-origin-y"));
  const cell = Number(await canvas.getAttribute("data-cell-size"));
  const border = Number(await canvas.getAttribute("data-border-total"));
  // Quilt-space eighths of the cell centre, then into canvas px.
  const qx = border + (col + 0.5) * cell;
  const qy = border + (row + 0.5) * cell;
  return { x: box.x + originX + qx * scale, y: box.y + originY + qy * scale };
}

async function openDemoReady(page: Page): Promise<void> {
  await page.goto("./");
  await page.getByTestId("open-demo").click();
  await expect(page.getByTestId("editor")).toBeVisible();
  await expect(page.getByTestId("engine-chip")).toHaveAttribute("data-engine-phase", "ready", {
    timeout: READY_TIMEOUT,
  });
  await expect(page.getByTestId("fabric-count-b")).toHaveText(/1,?246/);
}

async function paintCell(page: Page, row: number, col: number): Promise<void> {
  const point = await cellPoint(page, row, col);
  await page.mouse.click(point.x, point.y);
}

test("paint with census verification, drag line walk, undo and redo", async ({ page }) => {
  await openDemoReady(page);
  await page.getByTestId("mode-paint").click();
  await page.getByTestId("swatch-b").click();

  // The fixture's top-left cell (0,0) is blue in Block A; cell (0,2) is
  // cream (row bbcbb). Paint cream cell (0,2) blue: census 1246 -> 1247.
  await paintCell(page, 0, 2);
  await expect(page.getByTestId("fabric-count-b")).toHaveText(/1,?247/);

  // Drag from (2,0) to (2,9): row 2 of blocks A|B is cbbbc|ccccc, so the
  // run covers cream cells at cols 0,4,5,6,7,8,9 = 7 creams -> +7 blues.
  const from = await cellPoint(page, 2, 0);
  const to = await cellPoint(page, 2, 9);
  await page.mouse.move(from.x, from.y);
  await page.mouse.down();
  await page.mouse.move(to.x, to.y, { steps: 2 }); // fast drag: 2 events for 10 cells
  await page.mouse.up();
  await expect(page.getByTestId("fabric-count-b")).toHaveText(/1,?254/);

  // Undo the drag stroke, then the single paint; census returns to baseline.
  await page.getByTestId("undo").click();
  await expect(page.getByTestId("fabric-count-b")).toHaveText(/1,?247/);
  await page.keyboard.press("ControlOrMeta+z");
  await expect(page.getByTestId("fabric-count-b")).toHaveText(/1,?246/);
  // Redo via Ctrl+Y.
  await page.keyboard.press("Control+y");
  await expect(page.getByTestId("fabric-count-b")).toHaveText(/1,?247/);
});

test("undo depth of at least 50", async ({ page }) => {
  test.setTimeout(240_000);
  await openDemoReady(page);
  await page.getByTestId("mode-paint").click();
  // 50 strokes alternating fabrics (defeats same-kind coalescing) across
  // distinct cells of the cream border rows of Block B (rows 5..9, cols
  // 5..9 is B's cream interior in block-row 1... use row 6, cols vary and
  // rows 6/7 to stay inside the 45x55 grid).
  for (let i = 0; i < 50; i++) {
    await page.getByTestId(i % 2 === 0 ? "swatch-b" : "swatch-c").click();
    await paintCell(page, 10 + Math.floor(i / 10), (i % 10) + 10);
  }
  for (let i = 0; i < 50; i++) {
    await page.keyboard.press("ControlOrMeta+z");
  }
  await expect(page.getByTestId("fabric-count-b")).toHaveText(/1,?246/);
  await expect(page.getByTestId("fabric-count-c")).toHaveText(/1,?229/);
});

test("palette add, rename, recolor; deleting an in-use fabric is blocked", async ({ page }) => {
  await openDemoReady(page);

  await page.getByTestId("add-fabric").click();
  const renameNew = page.locator("[data-testid^='fabric-rename-f']").last();
  await renameNew.fill("Leaf green");
  await renameNew.press("Enter");
  await expect(page.locator("[data-testid^='fabric-row-']").last()).toContainText("Leaf green");

  // Recolor the blue fabric; assignment is by id so this is one edit.
  await page.getByTestId("fabric-color-b").fill("#336699");

  // Deleting cream (in use by 1229 squares + border) must be blocked by the
  // bridge validation envelope, and the fabric stays.
  await page.getByTestId("delete-fabric-c").click();
  const toast = page.getByTestId("toast");
  await expect(toast).toBeVisible();
  await expect(toast).toContainText(/referenced|in use/i);
  await expect(toast).not.toContainText("Traceback");
  await expect(page.getByTestId("fabric-row-c")).toBeVisible();

  // Deleting the never-used new fabric succeeds.
  await page.locator("[data-testid^='delete-fabric-f']").last().click();
  await expect(page.locator("text=Leaf green")).toHaveCount(0);
});

test("save-to-file round trip is byte-identical on the canonical model", async ({ page }) => {
  await openDemoReady(page);
  await page.getByTestId("mode-paint").click();
  await page.getByTestId("swatch-b").click();
  await paintCell(page, 0, 2);
  await expect(page.getByTestId("fabric-count-b")).toHaveText(/1,?247/);

  const download1 = page.waitForEvent("download");
  await page.getByTestId("save-project").click();
  const file1 = await (await download1).createReadStream();
  const bytes1 = await streamToString(file1);

  // Reload fresh, upload the saved file, save again: the canonical model
  // serialization must be byte-identical.
  await page.reload();
  await page.getByTestId("open-project").click();
  await page.getByTestId("open-file-input").setInputFiles({
    name: "roundtrip.qrep.json",
    mimeType: "application/json",
    buffer: Buffer.from(bytes1, "utf8"),
  });
  await expect(page.getByTestId("editor")).toBeVisible();
  const download2 = page.waitForEvent("download");
  await page.getByTestId("save-project").click();
  const bytes2 = await streamToString(await (await download2).createReadStream());

  const model1 = JSON.stringify(JSON.parse(bytes1).model);
  const model2 = JSON.stringify(JSON.parse(bytes2).model);
  expect(model2).toBe(model1);
  // The painted cell survived: cell (0,2) is blue in both.
  expect(JSON.parse(bytes1).model.center.cells[0][2]).toBe("b");
});

test("autosave restores after reload with its age shown", async ({ page }) => {
  await openDemoReady(page);
  await page.getByTestId("mode-paint").click();
  await page.getByTestId("swatch-b").click();
  await paintCell(page, 0, 2);
  // Wait for the debounced autosave to land in localStorage.
  await expect
    .poll(async () => page.evaluate(() => localStorage.getItem("qrep-autosave") !== null))
    .toBe(true);

  await page.reload();
  const banner = page.getByTestId("resume-banner");
  await expect(banner).toBeVisible();
  await expect(banner).toContainText(/just now|minute/i);
  await page.getByTestId("resume-accept").click();
  await expect(page.getByTestId("editor")).toBeVisible();
  await expect(page.getByTestId("engine-chip")).toHaveAttribute("data-engine-phase", "ready", {
    timeout: READY_TIMEOUT,
  });
  // The painted square survived the restore: census shows 1247.
  await expect(page.getByTestId("fabric-count-b")).toHaveText(/1,?247/);
});

test("beforeunload guards only when edits are newer than the last save", async ({ page }) => {
  await openDemoReady(page);

  // Clean state: no beforeunload dialog on navigation.
  let sawDialog = false;
  page.on("dialog", (dialog) => {
    sawDialog = true;
    void dialog.dismiss();
  });
  await page.reload({ waitUntil: "domcontentloaded" });
  expect(sawDialog).toBe(false);

  // Dirty state: dialog appears.
  await page.getByTestId("resume-accept").click().catch(() => {});
  await page.getByTestId("open-demo").click().catch(() => {});
  await expect(page.getByTestId("editor")).toBeVisible();
  await expect(page.getByTestId("engine-chip")).toHaveAttribute("data-engine-phase", "ready", {
    timeout: READY_TIMEOUT,
  });
  await page.getByTestId("mode-paint").click();
  await page.getByTestId("swatch-b").click();
  const point = await cellPoint(page, 0, 2);
  await page.mouse.click(point.x, point.y);

  const dialogSeen = new Promise<boolean>((resolve) => {
    page.once("dialog", (dialog) => {
      void dialog.accept();
      resolve(true);
    });
  });
  await page.reload({ waitUntil: "domcontentloaded" }).catch(() => {});
  expect(await dialogSeen).toBe(true);

  // After a file save, the guard stands down.
  await page.getByTestId("resume-accept").click().catch(() => {});
  await expect(page.getByTestId("editor")).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByTestId("save-project").click();
  await download;
  let dialogAfterSave = false;
  page.once("dialog", (dialog) => {
    dialogAfterSave = true;
    void dialog.dismiss();
  });
  await page.reload({ waitUntil: "domcontentloaded" });
  expect(dialogAfterSave).toBe(false);
});

test("a foreign schema_version autosave is rejected with a clear message", async ({ page }) => {
  await page.goto("./");
  await page.evaluate(() => {
    localStorage.setItem(
      "qrep-autosave",
      JSON.stringify({
        app: "QREP",
        version: 1,
        name: "From the future",
        savedAt: 1,
        model: { schema_version: "2" },
        ui: {},
      }),
    );
  });
  await page.reload();
  const error = page.getByTestId("autosave-error");
  await expect(error).toBeVisible();
  await expect(error).toContainText(/schema_version "2"/);
  await expect(error).toContainText(/reads schema_version "1"/);
});

test("start from a blank grid (PARITY item 15)", async ({ page }) => {
  await page.goto("./");
  await page.getByTestId("start-blank").click();
  await expect(page.getByTestId("editor")).toBeVisible();
  // 18 cols x 2 1/2" + 2 x 2 1/2" border = 50" wide; 24 rows -> 65" tall.
  await expect(page.getByTestId("ruler-x-end")).toHaveText('50"');
  await expect(page.getByTestId("ruler-y-end")).toHaveText('65"');
});

async function streamToString(stream: NodeJS.ReadableStream): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of stream) {
    chunks.push(Buffer.from(chunk as Buffer));
  }
  return Buffer.concat(chunks).toString("utf8");
}
