/**
 * Pure editor state (S3, issue #43): full-model snapshot history, dirty
 * tracking, wrapper/autosave serialization, and the blank-grid factory.
 * No React, no engine calls - commit-time bridge validation is orchestrated
 * by the UI layer; this store never leaves JS.
 *
 * History design (contract): snapshots of the whole model (tens of KB),
 * capped at HISTORY_CAP; rapid same-kind edits coalesce into one entry;
 * editing after undo discards the redo branch.
 */
import type { QuiltModel } from "../model/types";

export const HISTORY_CAP = 100;
/** Same-kind edits within this window merge into one undo entry (ms). */
export const COALESCE_WINDOW_MS = 1000;

export interface CellRef {
  row: number;
  col: number;
}

interface Clock {
  now: () => number;
}

function clone<T>(value: T): T {
  return structuredClone(value);
}

export class EditorStore {
  model: QuiltModel;
  private past: QuiltModel[] = [];
  private future: QuiltModel[] = [];
  private lastEditKind: string | null = null;
  private lastEditAt = Number.NEGATIVE_INFINITY;
  private dirty = false;
  private readonly clock: Clock;
  private fabricCounter = 0;

  constructor(model: QuiltModel, clock: Clock = { now: () => Date.now() }) {
    this.model = clone(model);
    this.clock = clock;
  }

  // ------------------------------------------------------------- mutations

  paintStroke(cells: CellRef[], fabricId: string): void {
    this.beginEdit(`paint:${fabricId}`);
    for (const { row, col } of cells) {
      if (row < 0 || row >= this.model.center.rows) continue;
      if (col < 0 || col >= this.model.center.cols) continue;
      this.model.center.cells[row][col] = fabricId;
      // PARITY item 6: painting a square clears its uncertainty.
      if (this.model.center.cell_confidence) {
        this.model.center.cell_confidence[row][col] = 1;
      }
    }
  }

  recolorFabric(fabricId: string, color: string): void {
    this.beginEdit(`recolor:${fabricId}`);
    const fabric = this.model.palette.fabrics.find((f) => f.id === fabricId);
    if (fabric) fabric.color = color;
  }

  renameFabric(fabricId: string, name: string): void {
    this.beginEdit(`rename:${fabricId}`);
    const fabric = this.model.palette.fabrics.find((f) => f.id === fabricId);
    if (fabric) fabric.name = name;
  }

  addFabric(): string {
    this.beginEdit("add-fabric");
    const existing = new Set(this.model.palette.fabrics.map((f) => f.id));
    let id: string;
    do {
      this.fabricCounter += 1;
      id = `f${this.fabricCounter}`;
    } while (existing.has(id));
    this.model.palette.fabrics.push({
      id,
      name: `Fabric ${this.model.palette.fabrics.length + 1}`,
      color: "#b8a06a",
    });
    return id;
  }

  /**
   * Candidate model with a fabric removed, WITHOUT committing: the UI must
   * bridge-validate the candidate (referential integrity lives in the
   * engine) and call commitCandidate only on an ok envelope.
   */
  withFabricRemoved(fabricId: string): QuiltModel {
    const candidate = clone(this.model);
    candidate.palette.fabrics = candidate.palette.fabrics.filter((f) => f.id !== fabricId);
    return candidate;
  }

  commitCandidate(candidate: QuiltModel, kind: string): void {
    this.beginEdit(kind);
    this.model = clone(candidate);
  }

  /** Replace the whole model (open/restore); clears history and dirtiness. */
  reset(model: QuiltModel): void {
    this.model = clone(model);
    this.past = [];
    this.future = [];
    this.lastEditKind = null;
    this.lastEditAt = Number.NEGATIVE_INFINITY;
    this.dirty = false;
  }

  // --------------------------------------------------------------- history

  private beginEdit(kind: string): void {
    const now = this.clock.now();
    const coalesce =
      kind === this.lastEditKind && now - this.lastEditAt <= COALESCE_WINDOW_MS;
    if (!coalesce) {
      this.past.push(clone(this.model));
      if (this.past.length > HISTORY_CAP) this.past.shift();
    }
    this.future = [];
    this.lastEditKind = kind;
    this.lastEditAt = now;
    this.dirty = true;
  }

  canUndo(): boolean {
    return this.past.length > 0;
  }

  canRedo(): boolean {
    return this.future.length > 0;
  }

  undo(): void {
    const previous = this.past.pop();
    if (previous === undefined) return;
    this.future.push(this.model);
    this.model = previous;
    this.lastEditKind = null;
    this.dirty = true;
  }

  redo(): void {
    const next = this.future.pop();
    if (next === undefined) return;
    this.past.push(this.model);
    this.model = next;
    this.lastEditKind = null;
    this.dirty = true;
  }

  // ---------------------------------------------------------- dirty state

  hasUnsavedChanges(): boolean {
    return this.dirty;
  }

  markFileSaved(): void {
    this.dirty = false;
  }
}

// ------------------------------------------------------------ serialization

/** PARITY item 5: the save file wraps the canonical engine model. */
export function buildProjectFile(model: QuiltModel, name: string): string {
  return JSON.stringify({ app: "QREP", version: 1, name, model, ui: {} }, null, 2);
}

interface AutosaveDoc {
  name: string;
  savedAt: number;
  model: QuiltModel;
}

export function buildAutosaveDoc(model: QuiltModel, name: string, savedAt: number): string {
  return JSON.stringify({ app: "QREP", version: 1, name, savedAt, model, ui: {} });
}

/**
 * Parses an autosave document. Throws on any schema_version other than "1"
 * with a message naming the found version - foreign versions are rejected
 * loudly, never silently dropped.
 */
export function parseAutosaveDoc(text: string): AutosaveDoc {
  const doc = JSON.parse(text) as {
    name?: string;
    savedAt?: number;
    model?: QuiltModel;
  };
  const version = doc.model?.schema_version;
  if (version !== "1") {
    throw new Error(
      `this autosave uses schema_version ${JSON.stringify(version)}; ` +
        `this app reads schema_version "1" only`,
    );
  }
  return {
    name: doc.name ?? "Untitled",
    savedAt: doc.savedAt ?? 0,
    model: doc.model!,
  };
}

// --------------------------------------------------------------- blank grid

/**
 * PARITY item 15: blank grid start - 24 rows x 18 cols of 2 1/2" squares
 * (20 eighths), one 2 1/2" background border, background + one accent
 * fabric, block size 1.
 */
export function makeBlankModel(): QuiltModel {
  const rows = 24;
  const cols = 18;
  return {
    schema_version: "1",
    metadata: { name: "New quilt" },
    palette: {
      fabrics: [
        { id: "bg", name: "Background", color: "#f7f1e0" },
        { id: "a1", name: "Accent 1", color: "#a9c7dc" },
      ],
    },
    center: {
      rows,
      cols,
      cell_size: 20,
      cells: Array.from({ length: rows }, () => Array.from({ length: cols }, () => "bg")),
    },
    borders: [{ fabric_id: "bg", width: 20 }],
    binding: { fabric_id: "a1" },
  };
}
