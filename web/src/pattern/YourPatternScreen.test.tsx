/**
 * Your pattern outlines the flagged squares of the read itself (C2a, issue
 * #96): the quilt canvas gets the photo read's model, whose cell confidences
 * it outlines, with showUncertain on, never the editor's model. Rendered to a
 * string in Node, so no DOM: a fake QuiltCanvas records the props the screen
 * passes it, and the state hooks return hand-made values.
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
}));

vi.mock("../viewer", () => ({
  QuiltCanvas: (props: CanvasProps) => {
    fakes.canvas.push(props);
    return null;
  },
  FabricsPanel: () => null,
}));
vi.mock("../state/model", () => ({ useModel: () => fakes.model }));
vi.mock("../state/photo", () => ({ usePhoto: () => fakes.photo }));
vi.mock("../state/pattern", () => ({ useYourPattern: () => fakes.pattern }));
vi.mock("../engine/engineStatus", () => ({ useEngineStatus: () => ({ phase: "ready" }) }));

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
  fakes.model = { model: quilt(EDITOR_CONFIDENCE), summary: null };
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
    retrySummary: noop,
    pdf: { status: "idle", message: null },
    savePdf: noop,
    retryPdf: noop,
    retryEngine: noop,
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
