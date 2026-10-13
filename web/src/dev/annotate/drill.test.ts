/**
 * Pin drill (C3a, issue #149; plan section 9, item 4): the drill hides a
 * loaded annotation and records each placed pin and each count entered, with
 * the photo id, for D10 to score against verified truth.
 */
import { describe, expect, it } from "vitest";
import { createDrill, drillStart, recordCounts, recordPin, serializeDrill } from "./drill";

const IDENTITY = {
  photo: "images/lacma-54871.jpg",
  sha256: "3ceb4eeb83a38a3d78576eb4282554ddd1c51644e8c212502800ec995672996e",
  canvas: [800, 600] as [number, number],
};
const DEVICE = { viewport_width: 390, viewport_height: 844, device_pixel_ratio: 3, pointer: "coarse" as const };

describe("the drill log", () => {
  it("names the photo, the frame and the device", () => {
    const log = createDrill(IDENTITY, "outer_edge", DEVICE, "2026-10-13T10:00:00.000Z");
    expect(log).toEqual({
      drill_version: 1,
      photo: IDENTITY.photo,
      sha256: IDENTITY.sha256,
      canvas: [800, 600],
      frame_mode: "outer_edge",
      started_at: "2026-10-13T10:00:00.000Z",
      device: DEVICE,
      records: [],
    });
  });

  it("records each placement and each count entry in order", () => {
    let log = createDrill(IDENTITY, "outer_edge", DEVICE, "2026-10-13T10:00:00.000Z");
    log = recordPin(log, "outer.top_left", { x: 101, y: 52 }, "pointer", 1500);
    log = recordPin(log, "outer.top_left", { x: 100, y: 52 }, "key", 1800);
    const counts = { blocks_across: 8, blocks_down: 9, squares_per_block_across: 5, squares_per_block_down: 5 };
    log = recordCounts(log, counts, 2400);
    expect(log.records).toEqual([
      { seq: 1, t_ms: 1500, kind: "pin", pin: "outer.top_left", x: 101, y: 52, input: "pointer" },
      { seq: 2, t_ms: 1800, kind: "pin", pin: "outer.top_left", x: 100, y: 52, input: "key" },
      { seq: 3, t_ms: 2400, kind: "counts", counts },
    ]);
  });

  it("writes two-space JSON ending in a newline", () => {
    const text = serializeDrill(createDrill(IDENTITY, "field", DEVICE, "2026-10-13T10:00:00.000Z"));
    expect(JSON.parse(text).frame_mode).toBe("field");
    expect(text.endsWith("}\n")).toBe(true);
  });
});

describe("starting a drill", () => {
  it("hides the annotation: pins at the neutral inset, one square, no bands, no class", () => {
    // Arithmetic: 0.15 x 800 = 120, 0.85 x 800 = 680; 0.15 x 600 = 90, 0.85 x 600 = 510
    const start = drillStart(IDENTITY.canvas);
    expect(start.outer).toEqual({
      top_left: { x: 120, y: 90 },
      top_right: { x: 680, y: 90 },
      bottom_right: { x: 680, y: 510 },
      bottom_left: { x: 120, y: 510 },
    });
    expect(start.field).toBeNull();
    expect(start.bands).toEqual([]);
    expect(start.across).toEqual({ blocks: 1, squaresPerBlock: 1 });
    expect(start.down).toEqual({ blocks: 1, squaresPerBlock: 1 });
    expect(start.constructionClass).toBeNull();
  });
});
