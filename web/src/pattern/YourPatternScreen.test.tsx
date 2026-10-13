/**
 * Your pattern outlines the flagged squares of the read itself (C2a, issue
 * #96): the quilt canvas gets the photo read's model, whose cell confidences
 * it outlines, with showUncertain on, never the editor's model. Rendered to a
 * string in Node, so no DOM: a fake QuiltCanvas records the props the screen
 * passes it, and the state hooks return hand-made values. The error line's
 * census case renders the real FabricsPanel.
 */
import { renderToString } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { QuiltModel } from "../model/types";
import { YourPatternScreen } from "./YourPatternScreen";

interface CanvasProps {
  model: QuiltModel;
  showUncertain?: boolean;
}

const fakes = vi.hoisted(() => ({
  canvas: [] as CanvasProps[],
  model: null as unknown,
  photo: null as unknown,
  pattern: null as unknown,
  engineStatus: { phase: "ready" } as unknown,
}));

vi.mock("../viewer", async () => {
  const { FabricsPanel } =
    await vi.importActual<typeof import("../viewer/FabricsPanel")>("../viewer/FabricsPanel");
  return {
    QuiltCanvas: (props: CanvasProps) => {
      fakes.canvas.push(props);
      return null;
    },
    FabricsPanel,
  };
});
vi.mock("../state/model", () => ({ useModel: () => fakes.model }));
vi.mock("../state/photo", () => ({ usePhoto: () => fakes.photo }));
vi.mock("../state/pattern", () => ({ useYourPattern: () => fakes.pattern }));
vi.mock("../engine/engineStatus", () => ({ useEngineStatus: () => fakes.engineStatus }));

/** A 2 x 2 quilt in two fabrics with the given cell confidences. */
function quilt(confidence: number[][]): QuiltModel {
  return {
    schema_version: "1.0",
    metadata: { name: "Recovered quilt" },
    palette: {
      fabrics: [
        { id: "f0", name: "Fabric 1", color: "#336699" },
        { id: "f1", name: "Fabric 2", color: "#eeddcc" },
      ],
    },
    center: {
      rows: 2,
      cols: 2,
      cell_size: 16,
      cells: [
        ["f0", "f1"],
        ["f1", "f0"],
      ],
      cell_confidence: confidence,
    },
    borders: [],
    binding: { fabric_id: "f0" },
  };
}

// The read flags two squares: 0.5 and 0.89 are below PARITY item 6's 0.9,
// and the two 1s are not. The editor's model carries different confidences,
// all 1 (as after an edit), so a canvas fed from it would outline nothing.
const READ_CONFIDENCE = [
  [1, 0.5],
  [0.89, 1],
];
const EDITOR_CONFIDENCE = [
  [1, 1],
  [1, 1],
];

function setUp(source: "photo" | "sample"): void {
  fakes.canvas = [];
  fakes.engineStatus = { phase: "ready" };
  fakes.model = { model: quilt(EDITOR_CONFIDENCE), summary: null, censusFailed: false };
  fakes.photo = {
    photoUrl: "blob:read-photo",
    result: {
      modelJson: JSON.stringify(quilt(READ_CONFIDENCE)),
      stageConfidence: {},
      uncertainCount: 2,
      reverseMs: 1,
    },
  };
  const noop = () => {};
  fakes.pattern = {
    screen: "pattern",
    source,
    showPattern: noop,
    showEditor: noop,
    summary: { status: "loading" },
    pdf: { status: "idle", message: null },
    savePdf: noop,
    retry: noop,
  };
}

describe("YourPatternScreen's quilt canvas", () => {
  beforeEach(() => {
    fakes.canvas = [];
  });

  it("draws a photo read's own model with its flagged squares outlined", () => {
    setUp("photo");
    const html = renderToString(<YourPatternScreen />);

    expect(fakes.canvas).toHaveLength(1);
    const props = fakes.canvas[0];
    expect(props.showUncertain).toBe(true);
    expect(props.model.center.cell_confidence).toEqual(READ_CONFIDENCE);
    // Hand count: the two squares below 0.9 above.
    expect(html).toContain('data-count="2"');
  });

  it("draws the sample's own model with no outlines, whatever read is left over", () => {
    setUp("sample");
    const html = renderToString(<YourPatternScreen />);

    expect(fakes.canvas).toHaveLength(1);
    const props = fakes.canvas[0];
    expect(props.showUncertain).toBe(false);
    expect(props.model.center.cell_confidence).toEqual(EDITOR_CONFIDENCE);
    expect(html).not.toContain('data-testid="flagged-count"');
  });
});

const READY_SUMMARY = {
  status: "ready",
  summary: {
    method: "strip",
    method_reason: "Blocks repeat.",
    fabrics: [
      { fabric_id: "f0", letter: "f0", name: "Fabric 1" },
      { fabric_id: "f1", letter: "f1", name: "Fabric 2" },
    ],
  },
};

describe("YourPatternScreen's error line", () => {
  it("asks for an engine Retry while only the census waits on a failed engine", () => {
    setUp("sample");
    fakes.engineStatus = { phase: "failed", message: "the engine files did not load" };
    (fakes.pattern as { summary: unknown }).summary = READY_SUMMARY;
    const html = renderToString(<YourPatternScreen />);

    // The census is null and has not failed, so it is still to land.
    expect(html).toContain("The pattern engine did not start, so your pattern is not ready yet.");
    expect(html).toContain('data-testid="pattern-retry"');
    expect(html).toContain("counting squares");
  });

  it("shows a failed census with its Retry, and the census rows as not counted", () => {
    setUp("sample");
    fakes.model = { model: quilt(EDITOR_CONFIDENCE), summary: null, censusFailed: true };
    (fakes.pattern as { summary: unknown }).summary = READY_SUMMARY;
    const html = renderToString(<YourPatternScreen />);

    expect(html).toContain("Your fabrics could not be counted this time. Try again.");
    expect(html).toContain('data-testid="pattern-retry"');
    expect(html).toContain('data-testid="fabric-census"');
    // Hand count: two fabric lines, neither with a count, so two placeholders.
    expect(html.split("not counted")).toHaveLength(3);
    expect(html).not.toContain("counting squares");
  });
});
