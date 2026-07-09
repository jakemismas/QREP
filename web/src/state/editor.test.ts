/**
 * Editor store tests (S3, issue #43): snapshot history (cap 100, branch
 * discard on edit-after-undo, same-kind coalescing), dirty tracking against
 * the last file save, wrapper/autosave formats with the schema_version
 * guard, the blank-grid factory (PARITY item 15), and confidence-clearing
 * paint (PARITY item 6). All expectations hand-derived.
 */
import { describe, expect, it } from "vitest";
import type { QuiltModel } from "../model/types";
import {
  EditorStore,
  HISTORY_CAP,
  buildAutosaveDoc,
  buildProjectFile,
  makeBlankModel,
  parseAutosaveDoc,
} from "./editor";

function tinyModel(withConfidence = false): QuiltModel {
  return {
    schema_version: "1",
    metadata: { name: "tiny" },
    palette: {
      fabrics: [
        { id: "bg", name: "Background", color: "#f7f1e0" },
        { id: "a1", name: "Accent 1", color: "#a9c7dc" },
      ],
    },
    center: {
      rows: 3,
      cols: 3,
      cell_size: 20,
      cells: [
        ["bg", "bg", "bg"],
        ["bg", "bg", "bg"],
        ["bg", "bg", "bg"],
      ],
      cell_confidence: withConfidence
        ? [
            [0.5, 1, 1],
            [1, 1, 1],
            [1, 1, 0.7],
          ]
        : null,
    },
    borders: [{ fabric_id: "bg", width: 20 }],
    binding: { fabric_id: "a1" },
  };
}

describe("paint", () => {
  it("paints cells and one stroke is one undo entry", () => {
    const store = new EditorStore(tinyModel(), { now: () => 0 });
    store.paintStroke(
      [
        { row: 0, col: 0 },
        { row: 0, col: 1 },
      ],
      "a1",
    );
    expect(store.model.center.cells[0][0]).toBe("a1");
    expect(store.model.center.cells[0][1]).toBe("a1");
    store.undo();
    expect(store.model.center.cells[0][0]).toBe("bg");
    expect(store.model.center.cells[0][1]).toBe("bg");
  });

  it("sets per-cell confidence to 1.0 on painted squares (PARITY item 6)", () => {
    const store = new EditorStore(tinyModel(true), { now: () => 0 });
    store.paintStroke([{ row: 0, col: 0 }], "a1");
    expect(store.model.center.cell_confidence![0][0]).toBe(1);
    // Unpainted low-confidence squares keep their value.
    expect(store.model.center.cell_confidence![2][2]).toBe(0.7);
  });
});

describe("history", () => {
  it("coalesces rapid same-kind strokes and separates distinct kinds", () => {
    let clock = 0;
    const store = new EditorStore(tinyModel(), { now: () => clock });
    store.paintStroke([{ row: 0, col: 0 }], "a1");
    clock = 300; // within the coalesce window, same fabric
    store.paintStroke([{ row: 0, col: 1 }], "a1");
    clock = 5000; // outside the window
    store.paintStroke([{ row: 2, col: 2 }], "a1");
    // Three strokes, two entries: undo removes the third stroke first, then
    // the coalesced pair together.
    store.undo();
    expect(store.model.center.cells[2][2]).toBe("bg");
    expect(store.model.center.cells[0][1]).toBe("a1");
    store.undo();
    expect(store.model.center.cells[0][0]).toBe("bg");
    expect(store.model.center.cells[0][1]).toBe("bg");
    expect(store.canUndo()).toBe(false);
  });

  it("caps history at HISTORY_CAP snapshots", () => {
    let clock = 0;
    const store = new EditorStore(tinyModel(), { now: () => clock });
    // 105 non-coalescing edits (alternating fabrics defeat coalescing).
    for (let i = 0; i < HISTORY_CAP + 5; i++) {
      clock += 10_000;
      store.paintStroke([{ row: i % 3, col: (i * 2) % 3 }], i % 2 === 0 ? "a1" : "bg");
    }
    let undos = 0;
    while (store.canUndo()) {
      store.undo();
      undos++;
    }
    expect(undos).toBe(HISTORY_CAP);
  });

  it("supports at least 50 undo levels", () => {
    let clock = 0;
    const store = new EditorStore(tinyModel(), { now: () => clock });
    for (let i = 0; i < 50; i++) {
      clock += 10_000;
      store.paintStroke([{ row: i % 3, col: i % 3 }], i % 2 === 0 ? "a1" : "bg");
    }
    let undos = 0;
    while (store.canUndo()) {
      store.undo();
      undos++;
    }
    expect(undos).toBe(50);
    expect(store.model).toEqual(tinyModel());
  });

  it("discards the redo branch on edit-after-undo", () => {
    let clock = 0;
    const store = new EditorStore(tinyModel(), { now: () => clock });
    clock = 10_000;
    store.paintStroke([{ row: 0, col: 0 }], "a1");
    clock = 20_000;
    store.paintStroke([{ row: 1, col: 1 }], "a1");
    store.undo();
    expect(store.canRedo()).toBe(true);
    clock = 30_000;
    store.paintStroke([{ row: 2, col: 0 }], "a1");
    expect(store.canRedo()).toBe(false);
    // The new edit stands on top of the undone state.
    expect(store.model.center.cells[1][1]).toBe("bg");
    expect(store.model.center.cells[2][0]).toBe("a1");
  });

  it("redo restores an undone edit", () => {
    const store = new EditorStore(tinyModel(), { now: () => 0 });
    store.paintStroke([{ row: 0, col: 0 }], "a1");
    store.undo();
    store.redo();
    expect(store.model.center.cells[0][0]).toBe("a1");
  });
});

describe("palette mutations", () => {
  it("recolor is one edit and undoes as one", () => {
    const store = new EditorStore(tinyModel(), { now: () => 0 });
    store.recolorFabric("a1", "#123456");
    expect(store.model.palette.fabrics[1].color).toBe("#123456");
    store.undo();
    expect(store.model.palette.fabrics[1].color).toBe("#a9c7dc");
  });

  it("rename and add fabric mutate the palette", () => {
    let clock = 0;
    const store = new EditorStore(tinyModel(), { now: () => clock });
    clock = 10_000;
    store.renameFabric("a1", "Sky");
    clock = 20_000;
    const id = store.addFabric();
    expect(store.model.palette.fabrics.map((f) => f.name)).toContain("Sky");
    expect(store.model.palette.fabrics).toHaveLength(3);
    expect(store.model.palette.fabrics.some((f) => f.id === id)).toBe(true);
    // Fresh ids never collide with existing ones.
    expect(new Set(store.model.palette.fabrics.map((f) => f.id)).size).toBe(3);
  });

  it("withFabricRemoved produces the candidate without committing", () => {
    const store = new EditorStore(tinyModel(), { now: () => 0 });
    const candidate = store.withFabricRemoved("a1");
    expect(candidate.palette.fabrics).toHaveLength(1);
    expect(store.model.palette.fabrics).toHaveLength(2);
  });
});

describe("dirty tracking", () => {
  it("tracks edits newer than the last file save", () => {
    let clock = 0;
    const store = new EditorStore(tinyModel(), { now: () => clock });
    expect(store.hasUnsavedChanges()).toBe(false);
    clock = 10_000;
    store.paintStroke([{ row: 0, col: 0 }], "a1");
    expect(store.hasUnsavedChanges()).toBe(true);
    store.markFileSaved();
    expect(store.hasUnsavedChanges()).toBe(false);
    clock = 20_000;
    store.paintStroke([{ row: 0, col: 1 }], "a1");
    expect(store.hasUnsavedChanges()).toBe(true);
    // Undo back to the saved state still counts as unsaved changes: the
    // content differs from what the file save captured only if it differs -
    // we track edit recency, not content equality (simple and honest).
    store.undo();
    expect(store.hasUnsavedChanges()).toBe(true);
  });
});

describe("wrapper and autosave formats", () => {
  it("buildProjectFile wraps the canonical model (PARITY item 5)", () => {
    const doc = JSON.parse(buildProjectFile(tinyModel(), "My Quilt"));
    expect(doc.app).toBe("QREP");
    expect(doc.version).toBe(1);
    expect(doc.name).toBe("My Quilt");
    expect(doc.model.schema_version).toBe("1");
    expect(doc.ui).toEqual({});
  });

  it("carries ui.seamFix through the wrapper (PARITY item 2)", () => {
    const ui = { seamFix: { "0,0:v": "split" as const }, seamStrategy: "strip" };
    const doc = JSON.parse(buildProjectFile(tinyModel(), "My Quilt", ui));
    expect(doc.ui.seamFix).toEqual({ "0,0:v": "split" });
    // And autosave round-trips it.
    const saved = buildAutosaveDoc(tinyModel(), "My Quilt", 5, ui);
    expect(parseAutosaveDoc(saved).ui).toEqual(ui);
  });

  it("autosave doc round-trips with age metadata", () => {
    const saved = buildAutosaveDoc(tinyModel(), "My Quilt", 1_700_000_000_000);
    const restored = parseAutosaveDoc(saved);
    expect(restored.name).toBe("My Quilt");
    expect(restored.savedAt).toBe(1_700_000_000_000);
    expect(restored.model).toEqual(tinyModel());
  });

  it("rejects a foreign schema_version with a clear message", () => {
    const saved = buildAutosaveDoc(
      { ...tinyModel(), schema_version: "2" } as QuiltModel,
      "My Quilt",
      0,
    );
    expect(() => parseAutosaveDoc(saved)).toThrowError(/schema_version "2"/);
  });
});

describe("blank grid factory (PARITY item 15)", () => {
  it("builds 24 rows x 18 cols of 2 1/2in squares with one 2 1/2in border", () => {
    const model = makeBlankModel();
    expect(model.center.rows).toBe(24);
    expect(model.center.cols).toBe(18);
    expect(model.center.cell_size).toBe(20); // 2 1/2" = 20 eighths
    expect(model.borders).toHaveLength(1);
    expect(model.borders[0].width).toBe(20);
    expect(model.palette.fabrics).toHaveLength(2);
    expect(model.center.cells).toHaveLength(24);
    expect(model.center.cells[0]).toHaveLength(18);
    // Every square starts as the background fabric.
    const background = model.palette.fabrics[0].id;
    expect(model.center.cells.every((row) => row.every((c) => c === background))).toBe(true);
    expect(model.schema_version).toBe("1");
  });
});
