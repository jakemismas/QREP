/**
 * One PNG of every journey step at every size (issue #280), for review. The
 * step screenshots go into a small HTML grid as data URLs, one row per size,
 * and the page screenshots that grid, so it needs no image library.
 *
 * It lands under test-results/spike/, which CI's web-spike job uploads as
 * spike-artifacts. It is a record, never compared: golden-discipline.test.ts
 * bans snapshot assertions.
 */
import { mkdirSync } from "node:fs";
import * as path from "node:path";
import type { Page } from "@playwright/test";

export interface SheetShot {
  /** What the cell's caption says, such as "Your pattern". */
  label: string;
  png: Buffer;
}

export interface SheetRow {
  /** The size the row shows, such as "Phone, 390 x 844". */
  title: string;
  /** The width each screenshot takes on the sheet, in CSS px. */
  cellWidth: number;
  shots: SheetShot[];
}

const escapeHtml = (text: string) =>
  text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

export async function writeContactSheet(page: Page, rows: SheetRow[], file: string): Promise<void> {
  const gap = 24;
  const width = Math.max(
    800,
    ...rows.map((row) => row.shots.length * row.cellWidth + (row.shots.length + 1) * gap),
  );
  const body = rows
    .map(
      (row) => `
      <section>
        <h2>${escapeHtml(row.title)}</h2>
        <div class="row">
          ${row.shots
            .map(
              (shot, index) => `
            <figure style="width:${row.cellWidth}px">
              <figcaption>${index + 1}. ${escapeHtml(shot.label)}</figcaption>
              <img alt="" src="data:image/png;base64,${shot.png.toString("base64")}">
            </figure>`,
            )
            .join("")}
        </div>
      </section>`,
    )
    .join("");
  await page.setViewportSize({ width, height: 800 });
  await page.setContent(`<!doctype html>
    <html><head><meta charset="utf-8"><style>
      body { margin: 0; padding: ${gap}px; background: #e9e6e1; color: #1f1d1a; font: 18px/1.4 sans-serif; }
      h2 { margin: 0 0 12px; font-size: 22px; }
      section + section { margin-top: ${gap * 2}px; }
      .row { display: flex; gap: ${gap}px; align-items: flex-start; }
      figure { margin: 0; flex: none; }
      figcaption { margin-bottom: 8px; font-weight: 600; }
      img { display: block; width: 100%; height: auto; background: #fff; outline: 1px solid #8a857d; }
    </style></head><body>${body}</body></html>`);
  await page.evaluate(() => Promise.all([...document.images].map((image) => image.decode())));
  mkdirSync(path.dirname(file), { recursive: true });
  await page.screenshot({ path: file, fullPage: true });
}
