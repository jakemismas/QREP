/**
 * The confirm screen's state (C3b, issue #101): a staging sequence that
 * makes every decode and staging result for an older photo stale (web-09,
 * ux-16), default pins and counts for each new photo (criteria U3-8), and
 * corners on every read (criteria U3-5). Expected values are hand computed
 * in the comments.
 */
import { describe, expect, it } from "vitest";
import { ConfirmFlow, DEFAULT_COUNTS, DEFAULT_FRAME_MODE } from "./confirmFlow";
import { quadProblem } from "./frame";

// neutralInset of a 894 x 1044 photo (frame.ts, inset 0.15):
// left round(894 x 0.15 = 134.1) = 134, right round(894 x 0.85 = 759.9) = 760,
// top round(1044 x 0.15 = 156.6) = 157, bottom round(1044 x 0.85 = 887.4) = 887.
const SIZE_A = { width: 894, height: 1044 };
const PINS_A = {
  top_left: { x: 134, y: 157 },
  top_right: { x: 760, y: 157 },
  bottom_right: { x: 760, y: 887 },
  bottom_left: { x: 134, y: 887 },
};

// neutralInset of a 1000 x 800 photo: x 150 and 850, y 120 and 680.
const SIZE_B = { width: 1000, height: 800 };
const PINS_B = {
  top_left: { x: 150, y: 120 },
  top_right: { x: 850, y: 120 },
  bottom_right: { x: 850, y: 680 },
  bottom_left: { x: 150, y: 680 },
};

function readyFlow(): { flow: ConfirmFlow; seq: number } {
  const flow = new ConfirmFlow();
  const seq = flow.newPhoto();
  expect(flow.decoded(seq, SIZE_A)).toBe(true);
  return { flow, seq };
}

function expectDefaults(flow: ConfirmFlow): void {
  expect(flow.error).toBeNull();
  expect(flow.size).toBeNull();
  expect(flow.corners).toBeNull();
  expect(flow.mode).toBe(DEFAULT_FRAME_MODE);
  expect(flow.bands).toEqual([]);
  expect(flow.across).toEqual(DEFAULT_COUNTS.across);
  expect(flow.down).toEqual(DEFAULT_COUNTS.down);
  expect(flow.staging).toBe(false);
  expect(flow.squareEighths).toBeNull();
}

describe("defaults", () => {
  it("starts empty with the outer edge and one block of one square per axis", () => {
    const flow = new ConfirmFlow();
    expect(flow.status).toBe("empty");
    expect(flow.seq).toBe(0);
    expect(DEFAULT_FRAME_MODE).toBe("outer_edge");
    expect(DEFAULT_COUNTS).toEqual({
      across: { blocks: 1, squaresPerBlock: 1 },
      down: { blocks: 1, squaresPerBlock: 1 },
    });
    expectDefaults(flow);
    expect(flow.canContinue).toBe(false);
  });
});

describe("newPhoto", () => {
  it("bumps the sequence and resets everything to the defaults", () => {
    const { flow, seq } = readyFlow();
    flow.setCorner("top_left", { x: 200, y: 200 });
    flow.setMode("field");
    flow.setBands([{ width_squares: 2 }]);
    flow.setCounts({ blocks: 8, squaresPerBlock: 5 }, { blocks: 9, squaresPerBlock: 5 });
    flow.setSquareEighths(32);
    const next = flow.newPhoto();
    // seq 1 -> 2
    expect(next).toBe(seq + 1);
    expect(flow.seq).toBe(seq + 1);
    expect(flow.status).toBe("decoding");
    expectDefaults(flow);
  });
});

describe("decoded", () => {
  it("sets the pins to the neutral inset of the decoded size", () => {
    const flow = new ConfirmFlow();
    const seq = flow.newPhoto();
    expect(flow.decoded(seq, SIZE_A)).toBe(true);
    expect(flow.status).toBe("ready");
    expect(flow.size).toEqual(SIZE_A);
    expect(flow.corners).toEqual(PINS_A);
  });

  it("ignores a stale sequence and changes nothing", () => {
    const flow = new ConfirmFlow();
    const first = flow.newPhoto();
    const second = flow.newPhoto();
    expect(flow.decoded(first, SIZE_A)).toBe(false);
    expect(flow.status).toBe("decoding");
    expect(flow.seq).toBe(second);
    expect(flow.corners).toBeNull();
    expect(flow.size).toBeNull();
    // The current photo still lands.
    expect(flow.decoded(second, SIZE_B)).toBe(true);
    expect(flow.corners).toEqual(PINS_B);
  });

  it("applies once, so a repeat cannot reset pins the user moved", () => {
    const { flow, seq } = readyFlow();
    flow.setCorner("top_left", { x: 140, y: 160 });
    expect(flow.decoded(seq, SIZE_A)).toBe(false);
    expect(flow.corners?.top_left).toEqual({ x: 140, y: 160 });
  });
});

describe("decodeFailed", () => {
  it("shows the failure with its message and no pins", () => {
    const flow = new ConfirmFlow();
    const seq = flow.newPhoto();
    const message = "QREP could not open this file. Choose a JPG or PNG photo of your quilt.";
    expect(flow.decodeFailed(seq, message)).toBe(true);
    expect(flow.status).toBe("failed");
    expect(flow.error).toBe(message);
    expect(flow.corners).toBeNull();
    expect(flow.canContinue).toBe(false);
  });

  it("ignores a stale sequence", () => {
    const flow = new ConfirmFlow();
    const first = flow.newPhoto();
    flow.newPhoto();
    expect(flow.decodeFailed(first, "old photo failed")).toBe(false);
    expect(flow.status).toBe("decoding");
    expect(flow.error).toBeNull();
  });

  it("clears the error when the next photo starts", () => {
    const flow = new ConfirmFlow();
    flow.decodeFailed(flow.newPhoto(), "bad file");
    flow.newPhoto();
    expect(flow.status).toBe("decoding");
    expect(flow.error).toBeNull();
  });
});

describe("a second photo (criteria U3-8)", () => {
  it("starts from that photo's default pins and the default counts", () => {
    const { flow } = readyFlow();
    flow.setCorner("bottom_right", { x: 700, y: 800 });
    flow.setCounts({ blocks: 8, squaresPerBlock: 5 }, { blocks: 10, squaresPerBlock: 4 });
    flow.setBands([{ width_squares: 1.5 }]);
    flow.setMode("field");
    flow.setSquareEighths(16);
    const seq = flow.newPhoto();
    expect(flow.decoded(seq, SIZE_B)).toBe(true);
    // Photo B's own inset, not photo A's moved pins.
    expect(flow.corners).toEqual(PINS_B);
    expect(flow.across).toEqual({ blocks: 1, squaresPerBlock: 1 });
    expect(flow.down).toEqual({ blocks: 1, squaresPerBlock: 1 });
    expect(flow.bands).toEqual([]);
    expect(flow.mode).toBe("outer_edge");
    expect(flow.squareEighths).toBeNull();
  });

  it("keeps the shared defaults unchanged when the counts change", () => {
    const { flow } = readyFlow();
    flow.setCounts({ blocks: 3, squaresPerBlock: 3 }, { blocks: 4, squaresPerBlock: 4 });
    flow.across.blocks = 99;
    expect(DEFAULT_COUNTS.across).toEqual({ blocks: 1, squaresPerBlock: 1 });
    flow.newPhoto();
    expect(flow.across).toEqual({ blocks: 1, squaresPerBlock: 1 });
  });
});

describe("setters", () => {
  it("moves one pin and keeps the rest", () => {
    const { flow } = readyFlow();
    const before = flow.corners;
    flow.setCorner("top_right", { x: 700, y: 150 });
    expect(flow.corners).toEqual({ ...PINS_A, top_right: { x: 700, y: 150 } });
    // A new object, so a render keyed on the corners sees the change.
    expect(flow.corners).not.toBe(before);
  });

  it("does nothing to pins before a photo is decoded", () => {
    const flow = new ConfirmFlow();
    flow.newPhoto();
    flow.setCorner("top_left", { x: 1, y: 1 });
    expect(flow.corners).toBeNull();
  });

  it("holds counts, bands, mode and the square size", () => {
    const { flow } = readyFlow();
    flow.setCounts({ blocks: 8, squaresPerBlock: 5 }, { blocks: 9, squaresPerBlock: 5 });
    flow.setBands([{ width_squares: 2 }, { width_squares: 0.5 }]);
    flow.setMode("field");
    flow.setSquareEighths(32);
    expect(flow.across).toEqual({ blocks: 8, squaresPerBlock: 5 });
    expect(flow.down).toEqual({ blocks: 9, squaresPerBlock: 5 });
    expect(flow.bands).toEqual([{ width_squares: 2 }, { width_squares: 0.5 }]);
    expect(flow.mode).toBe("field");
    expect(flow.squareEighths).toBe(32);
    flow.setSquareEighths(null);
    expect(flow.squareEighths).toBeNull();
  });
});

describe("Continue", () => {
  it("is off before a photo is ready", () => {
    const flow = new ConfirmFlow();
    expect(flow.canContinue).toBe(false);
    expect(flow.blocked).not.toBeNull();
    flow.newPhoto();
    expect(flow.canContinue).toBe(false);
    expect(flow.beginStaging()).toBeNull();
  });

  it("is on for the default pins", () => {
    const { flow } = readyFlow();
    expect(flow.blocked).toBeNull();
    expect(flow.canContinue).toBe(true);
  });

  it("is off for a concave quad, with quadProblem's reason", () => {
    const { flow } = readyFlow();
    // Top left to (700, 850): each corner stays on its own side (700 < 760,
    // 134 < 760, 850 < 887, 157 < 887), but the turn at the top left,
    // cross(BL, TL, TR) = (700 - 134)(157 - 887) - (850 - 887)(760 - 134)
    // = 566 x -730 + 37 x 626 = -413180 + 23162 = -390018 <= 0, is concave.
    flow.setCorner("top_left", { x: 700, y: 850 });
    expect(flow.canContinue).toBe(false);
    expect(flow.blocked).toBe(quadProblem(flow.corners!));
    expect(flow.blocked).toMatch(/crossed, concave or flat/);
    expect(flow.beginStaging()).toBeNull();
  });

  it("is off for corners out of order", () => {
    const { flow } = readyFlow();
    // Top right left of top left: 100 < 134 breaks tl.x < tr.x.
    flow.setCorner("top_right", { x: 100, y: 157 });
    expect(flow.canContinue).toBe(false);
    expect(flow.blocked).toBe(quadProblem(flow.corners!));
  });
});

describe("beginStaging and endStaging", () => {
  it("returns the corners even when no pin moved (criteria U3-5)", () => {
    const { flow, seq } = readyFlow();
    const frame = flow.beginStaging();
    expect(frame).toEqual({
      seq,
      mode: "outer_edge",
      corners: PINS_A,
      bands: [],
      across: { blocks: 1, squaresPerBlock: 1 },
      down: { blocks: 1, squaresPerBlock: 1 },
    });
    expect(flow.staging).toBe(true);
  });

  it("carries the confirmed counts, bands and mode", () => {
    const { flow } = readyFlow();
    flow.setCounts({ blocks: 8, squaresPerBlock: 5 }, { blocks: 9, squaresPerBlock: 5 });
    flow.setBands([{ width_squares: 2.5 }]);
    const frame = flow.beginStaging();
    expect(frame?.across).toEqual({ blocks: 8, squaresPerBlock: 5 });
    expect(frame?.down).toEqual({ blocks: 9, squaresPerBlock: 5 });
    expect(frame?.bands).toEqual([{ width_squares: 2.5 }]);
    expect(frame?.mode).toBe("outer_edge");
  });

  it("returns null while already staging", () => {
    const { flow } = readyFlow();
    expect(flow.beginStaging()).not.toBeNull();
    expect(flow.canContinue).toBe(false);
    expect(flow.blocked).not.toBeNull();
    expect(flow.beginStaging()).toBeNull();
  });

  it("ends staging for the current sequence", () => {
    const { flow } = readyFlow();
    const frame = flow.beginStaging()!;
    flow.endStaging(frame.seq);
    expect(flow.staging).toBe(false);
    expect(flow.canContinue).toBe(true);
  });

  it("leaves staging on when a stale sequence ends", () => {
    const { flow } = readyFlow();
    const old = flow.beginStaging()!;
    const seq = flow.newPhoto();
    flow.decoded(seq, SIZE_B);
    const current = flow.beginStaging()!;
    expect(current.seq).toBe(seq);
    flow.endStaging(old.seq);
    expect(flow.staging).toBe(true);
    flow.endStaging(current.seq);
    expect(flow.staging).toBe(false);
  });

  it("hands out a copy, so a later pin move cannot change a frame in flight", () => {
    const { flow } = readyFlow();
    const frame = flow.beginStaging()!;
    flow.setCorner("top_left", { x: 140, y: 160 });
    flow.setBands([{ width_squares: 1 }]);
    expect(frame.corners).toEqual(PINS_A);
    expect(frame.bands).toEqual([]);
  });
});

describe("clear", () => {
  it("makes an in-flight decode stale", () => {
    const flow = new ConfirmFlow();
    const seq = flow.newPhoto();
    flow.clear();
    // seq 1 -> 2
    expect(flow.seq).toBe(seq + 1);
    expect(flow.isCurrent(seq)).toBe(false);
    expect(flow.decoded(seq, SIZE_A)).toBe(false);
    expect(flow.decodeFailed(seq, "late failure")).toBe(false);
    expect(flow.status).toBe("empty");
    expectDefaults(flow);
  });

  it("makes an in-flight staging result stale", () => {
    const { flow } = readyFlow();
    const frame = flow.beginStaging()!;
    flow.clear();
    expect(flow.isCurrent(frame.seq)).toBe(false);
    expect(flow.status).toBe("empty");
    expect(flow.staging).toBe(false);
    expect(flow.corners).toBeNull();
    expect(flow.canContinue).toBe(false);
  });
});
