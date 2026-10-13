/**
 * The size control's logic (C2b, issue #148): the text it shows, the
 * requests it sends to bridge.size_pattern, and the sizer that keeps only the
 * newest result. Every expected value is hand computed in its comment: a
 * length is integer eighths (e), so inches = e / 8.
 */
import { describe, expect, it } from "vitest";
import type { SizeBasis, SizeRequest } from "../engine/contract";
import { EngineError } from "../engine/rpc";
import type { QuiltModel } from "../model/types";
import {
  BACKING_WIDTHS,
  canvasModel,
  PatternSizer,
  SIZE_FAILED,
  STRIP_WIDTHS,
  parsePresets,
  parseSide,
  presetRequest,
  sizeLine,
  sizeText,
  typedRequest,
  withWidths,
  yardsText,
} from "./patternSize";
import type { SizerView } from "./patternSize";

/** A 45 x 55 quilt at 12 e squares with one 30 e border: the sample's shape. */
function quilt(extra: Record<string, unknown> = {}): QuiltModel {
  return {
    schema_version: "1.0",
    metadata: { name: "Double Irish Chain 75x90" },
    palette: { fabrics: [{ id: "b", name: "Blue", color: "#335599" }] },
    center: { rows: 55, cols: 45, cell_size: 12, cells: [] },
    borders: [{ fabric_id: "b", width: 30 }],
    binding: { fabric_id: "b" },
    settings: { wof: 336, backing_width: 336 },
    ...extra,
  } as QuiltModel;
}

function basis(over: Partial<SizeBasis>): SizeBasis {
  return {
    source: "typed",
    requested_width: null,
    requested_height: null,
    achieved_width: 600,
    achieved_height: 720,
    ...over,
  };
}

describe("sizeText and yardsText", () => {
  it("prints eighths as mixed-fraction inches, width first", () => {
    // 600 e / 8 = 75 in; 720 e / 8 = 90 in.
    expect(sizeText(600, 720)).toBe("75 x 90 in");
    // 502 e / 8 = 62 6/8 = 62 3/4 in; 602 e / 8 = 75 2/8 = 75 1/4 in.
    expect(sizeText(502, 602)).toBe("62 3/4 x 75 1/4 in");
    // A side left out: 540 e / 8 = 67 4/8 = 67 1/2 in.
    expect(sizeText(null, 540)).toBe("67 1/2 in high");
    expect(sizeText(688, null)).toBe("86 in wide");
  });

  it("prints the engine's yards as mixed fractions of a yard", () => {
    // V-BACK-09: 23 quarter yards = 23 / 4 = 5.75 yd = 5 3/4 yd.
    expect(yardsText(5.75)).toBe("5 3/4 yd");
    // 3 quarter yards = 0.75 yd = 3/4 yd, no whole part.
    expect(yardsText(0.75)).toBe("3/4 yd");
    // 4 quarter yards = 1 yd exactly.
    expect(yardsText(1)).toBe("1 yd");
    // An eighth-yard increment: 1.125 yd = 1 1/8 yd.
    expect(yardsText(1.125)).toBe("1 1/8 yd");
  });
});

describe("typed size entry", () => {
  it("parses a side in inches with the shared fraction grammar", () => {
    // 67.5 in x 8 = 540 e; 86 in x 8 = 688 e; 67 1/2 in = 67 x 8 + 4 = 540 e.
    expect(parseSide("67.5", "in")).toBe(540);
    expect(parseSide("86", "in")).toBe(688);
    expect(parseSide("67 1/2", "in")).toBe(540);
  });

  it("converts centimeters at entry by the pinned rule", () => {
    // eighths = round(cm x 8 / 2.54): 171.5 x 8 = 1372; 1372 / 2.54 = 540.16; round = 540.
    expect(parseSide("171.5", "cm")).toBe(540);
    // 100 x 8 = 800; 800 / 2.54 = 314.96; round = 315.
    expect(parseSide("100", "cm")).toBe(315);
  });

  it("tells a blank side from an invalid one", () => {
    expect(parseSide("", "in")).toBeNull();
    expect(parseSide("   ", "cm")).toBeNull();
    expect(parseSide("abc", "in")).toBe("invalid");
    // Zero is no size: size_pattern refuses a side below 1 e.
    expect(parseSide("0", "in")).toBe("invalid");
    expect(parseSide("-3", "cm")).toBe("invalid");
  });

  it("builds a typed request from the sides set, and none from no side", () => {
    const both: SizeRequest = { source: "typed", width: 688, height: 540 };
    expect(typedRequest(688, 540)).toEqual(both);
    // Only a height: the width key is left out, so the strict request model
    // sees no null it would have to read.
    expect(typedRequest(null, 540)).toEqual({ source: "typed", height: 540 });
    expect(typedRequest(688, null)).toEqual({ source: "typed", width: 688 });
    expect(typedRequest(null, null)).toBeNull();
  });

  it("builds a preset request by name", () => {
    expect(presetRequest("Queen")).toEqual({ source: "preset", preset: "Queen" });
  });
});

describe("parsePresets", () => {
  it("keeps the bridge's table in its order", () => {
    // bridge.presets() returns {presets: [{name, width, height}]} in eighths:
    // Crib 36 x 52 in = 288 x 416 e.
    const raw = { presets: [{ name: "Crib", width: 288, height: 416 }] };
    expect(parsePresets(raw)).toEqual([{ name: "Crib", width: 288, height: 416 }]);
  });

  it("returns no chips for a result of the wrong shape", () => {
    expect(parsePresets(null)).toEqual([]);
    expect(parsePresets({ presets: "Queen" })).toEqual([]);
    expect(parsePresets({ presets: [{ name: "Crib", width: "288", height: 416 }] })).toEqual([]);
  });
});

describe("withWidths", () => {
  it("writes the chosen widths into the settings and leaves the rest", () => {
    const model = quilt();
    // 40 in x 8 = 320 e for cutting; 108 in x 8 = 864 e for the backing.
    const next = withWidths(model, { strip: 320, backing: 864 });
    expect(next.settings).toEqual({ wof: 320, backing_width: 864, wide_back_width: 944 });
    // The input is not changed, and an unset width keeps the model's own.
    expect(model.settings).toEqual({ wof: 336, backing_width: 336 });
    expect(withWidths(model, { strip: null, backing: 352 }).settings).toEqual({
      wof: 336,
      backing_width: 352,
    });
  });

  it("widens the wide back past a 108 in backing, as the schema requires", () => {
    // Settings refuses wide_back_width <= backing_width (qrep/model/schema.py,
    // _wide_back_is_wider), and both default to 108 in = 864 e here. The wide
    // back moves to MATH.md section 1.3's other common width: 118 in x 8 = 944 e.
    const next = withWidths(quilt(), { strip: null, backing: 864 });
    expect(next.settings).toEqual({ wof: 336, backing_width: 864, wide_back_width: 944 });
  });

  it("returns the same model when no width is set", () => {
    const model = quilt();
    expect(withWidths(model, { strip: null, backing: null })).toBe(model);
  });

  it("offers 40 in and 42 in as the defaults (MATH.md section 1.3, U and B)", () => {
    // U = 40 in = 320 e; B = 42 in = 336 e; BW = 108 in = 864 e.
    expect(STRIP_WIDTHS.find((w) => w.isDefault)?.eighths).toBe(320);
    expect(BACKING_WIDTHS.find((w) => w.isDefault)?.eighths).toBe(336);
    expect(BACKING_WIDTHS.map((w) => w.eighths)).toContain(864);
  });
});

describe("sizeLine", () => {
  it("labels the sample's own size a default and names its square", () => {
    // 12 e / 8 = 1 1/2 in squares (PS-09 names the square size assumed).
    const line = sizeLine(quilt(), { width: 600, height: 720 }, null, "sample");
    expect(line.kind).toBe("default");
    expect(line.label).toBe("Default size");
    expect(line.achieved).toBe("75 x 90 in");
    expect(line.note).toContain("1 1/2 in squares");
    expect(line.note).not.toMatch(/photo/);
    expect(line.asked).toBeNull();
  });

  it("says a read's default size is estimated from the photo", () => {
    const line = sizeLine(quilt(), { width: 600, height: 720 }, null, "photo");
    expect(line.kind).toBe("default");
    expect(line.note).toMatch(/estimated from your photo/i);
    expect(line.note).toContain("1 1/2 in squares");
  });

  it("reads a default basis the model records as a default", () => {
    const model = quilt({ size_basis: { ...basis({ source: "default" }), rounding_step: 2, confidence: 0 } });
    expect(sizeLine(model, { width: 600, height: 720 }, null, "photo").kind).toBe("default");
  });

  it("shows the asked size beside the achieved size when they differ", () => {
    // Asked 86 x 67 1/2 in = 688 x 540 e; the engine achieved 502 x 602 e
    // = 62 3/4 x 75 1/4 in with 10 e (1 1/4 in) squares.
    const sized = {
      model: quilt({ center: { rows: 55, cols: 45, cell_size: 10, cells: [] } }),
      basis: basis({
        requested_width: 688,
        requested_height: 540,
        achieved_width: 502,
        achieved_height: 602,
      }),
      preset: null,
    };
    const line = sizeLine(sized.model, { width: 502, height: 602 }, sized, "sample");
    expect(line.kind).toBe("typed");
    expect(line.label).toBe("Your size");
    expect(line.asked).toBe("86 x 67 1/2 in");
    expect(line.achieved).toBe("62 3/4 x 75 1/4 in");
  });

  it("shows no asked line when the size was met exactly", () => {
    // Asked 75 x 90 in = 600 x 720 e, achieved the same.
    const sized = {
      model: quilt(),
      basis: basis({ requested_width: 600, requested_height: 720 }),
      preset: null,
    };
    expect(sizeLine(sized.model, { width: 600, height: 720 }, sized, "sample").asked).toBeNull();
  });

  it("compares only the side you set", () => {
    // Only the height asked: 720 e = 90 in, met exactly; the width is free.
    const sized = {
      model: quilt(),
      basis: basis({ requested_height: 720 }),
      preset: null,
    };
    expect(sizeLine(sized.model, { width: 600, height: 720 }, sized, "sample").asked).toBeNull();
    // Only the height asked, 540 e, achieved 720 e: the asked line names the height.
    const missed = { ...sized, basis: basis({ requested_height: 540 }) };
    expect(sizeLine(missed.model, { width: 600, height: 720 }, missed, "sample").asked).toBe(
      "67 1/2 in high",
    );
  });

  it("names the preset you picked", () => {
    // Queen is 90 x 108 in = 720 x 864 e.
    const sized = {
      model: quilt(),
      basis: basis({ source: "preset", requested_width: 720, requested_height: 864 }),
      preset: "Queen",
    };
    const line = sizeLine(sized.model, { width: 600, height: 720 }, sized, "sample");
    expect(line.kind).toBe("preset");
    expect(line.label).toBe("Queen size");
    expect(line.asked).toBe("90 x 108 in");
  });
});

describe("PatternSizer", () => {
  function sizedResult(width: number, height: number) {
    return {
      outcome: "sized",
      model: quilt(),
      basis: basis({ requested_width: 688, achieved_width: width, achieved_height: height }),
    };
  }

  it("sends the base model and the request, and keeps the sized result", async () => {
    const calls: unknown[][] = [];
    const views: SizerView[] = [];
    const sizer = new PatternSizer({
      call: async (...args) => {
        calls.push(args);
        return sizedResult(502, 602);
      },
      onChange: (view) => views.push(view),
    });
    await sizer.apply('{"base":1}', { source: "typed", width: 688 }, null);
    expect(calls).toEqual([["size_pattern", '{"base":1}', '{"source":"typed","width":688}']]);
    expect(views[0].status).toBe("busy");
    expect(sizer.view.status).toBe("idle");
    expect(sizer.view.sized?.basis.achieved_width).toBe(502);
  });

  it("drops a result that lands after clear", async () => {
    let release: (value: unknown) => void = () => undefined;
    const sizer = new PatternSizer({
      call: () => new Promise((resolve) => (release = resolve)),
    });
    const pending = sizer.apply("{}", { source: "typed", width: 688 }, null);
    sizer.clear();
    release(sizedResult(502, 602));
    await pending;
    expect(sizer.view).toEqual({ status: "idle", sized: null, message: null });
  });

  it("keeps only the newest of two requests", async () => {
    const releases: ((value: unknown) => void)[] = [];
    const sizer = new PatternSizer({
      call: () => new Promise((resolve) => releases.push(resolve)),
    });
    const first = sizer.apply("{}", { source: "typed", width: 688 }, null);
    const second = sizer.apply("{}", { source: "preset", preset: "Queen" }, "Queen");
    releases[1](sizedResult(842, 702));
    releases[0](sizedResult(502, 602));
    await Promise.all([first, second]);
    expect(sizer.view.sized?.basis.achieved_width).toBe(842);
    expect(sizer.view.sized?.preset).toBe("Queen");
  });

  it("shows a plain sentence when the engine refuses, and keeps the last size", async () => {
    let fail = false;
    const sizer = new PatternSizer({
      call: async () => {
        if (fail) throw new EngineError("value", "a finished width must be at least 1 e, got 0");
        return sizedResult(502, 602);
      },
    });
    await sizer.apply("{}", { source: "typed", width: 688 }, null);
    fail = true;
    await sizer.apply("{}", { source: "typed", width: 1 }, null);
    expect(sizer.view.status).toBe("failed");
    expect(sizer.view.message).toBe(SIZE_FAILED);
    expect(sizer.view.sized?.basis.achieved_width).toBe(502);
  });

  it("treats a result without its outcome as a failure, never a size", async () => {
    const sizer = new PatternSizer({ call: async () => ({ model: quilt() }) });
    await sizer.apply("{}", { source: "typed", width: 688 }, null);
    expect(sizer.view.status).toBe("failed");
    expect(sizer.view.sized).toBeNull();
  });

  it("sends a current request again after an engine restart", async () => {
    let calls = 0;
    const sizer = new PatternSizer({
      call: async () => {
        calls += 1;
        if (calls === 1) throw new EngineError("worker", "the engine was restarted");
        return sizedResult(502, 602);
      },
    });
    await sizer.apply("{}", { source: "typed", width: 688 }, null);
    expect(calls).toBe(2);
    expect(sizer.view.sized?.basis.achieved_width).toBe(502);
  });
});

describe("canvasModel", () => {
  const confidence = [[0.5]];
  const one = (cell: number, conf?: number[][]): QuiltModel =>
    quilt({ center: { rows: 1, cols: 1, cell_size: cell, cells: [["b"]], cell_confidence: conf } });

  it("draws the read's own model, else the opened one, until you set a size", () => {
    const opened = one(12);
    const read = one(12, confidence);
    expect(canvasModel(null, opened, read)).toBe(read);
    expect(canvasModel(null, opened, null)).toBe(opened);
  });

  it("draws the sized quilt with the read's square confidences", () => {
    // Sizing changes the square, never the grid, so the read's 1 x 1
    // confidences still line up with the sized 10 e squares.
    const shown = canvasModel(one(10), one(12), one(12, confidence));
    expect(shown.center.cell_size).toBe(10);
    expect(shown.center.cell_confidence).toEqual(confidence);
  });

  it("keeps the sized quilt's own confidences when the grids differ", () => {
    const read = quilt({ center: { rows: 2, cols: 1, cell_size: 12, cells: [["b"], ["b"]], cell_confidence: [[0.5], [1]] } });
    expect(canvasModel(one(10), one(12), read).center.cell_confidence).toBeUndefined();
  });
});
