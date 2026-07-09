/**
 * TS mirror of the engine model surface the UI reads (S2 is read-only).
 * The engine schema (qrep/model/schema.py) stays authoritative; these types
 * cover only what the UI touches. All lengths are integer eighths.
 */

export interface Fabric {
  id: string;
  name: string;
  color: string;
}

export interface QuiltModel {
  schema_version: string;
  metadata: { name: string; notes?: string };
  palette: { fabrics: Fabric[] };
  center: {
    rows: number;
    cols: number;
    cell_size: number;
    cells: string[][];
    cell_confidence?: number[][] | null;
  };
  borders: { fabric_id: string; width: number }[];
  binding: { fabric_id: string; strip_width?: number };
  settings?: Record<string, unknown>;
  provenance?: { source: string; stage_confidence: Record<string, number> };
}

/** bridge.validate() result shape (see qrep/bridge.py _summary). */
export interface ModelSummary {
  name: string;
  rows: number;
  cols: number;
  fabric_count: number;
  fabrics: { id: string; name: string; color: string; cell_count: number }[];
  finished_width: number;
  finished_height: number;
  batting_width: number;
  batting_height: number;
  usable_width: number;
}

/**
 * PARITY item 5: the project file is a wrapper {app, version, name, model,
 * ui}; Open also accepts a bare engine model. Returns the model JSON string
 * to hand to the bridge plus the display name. Throws SyntaxError on
 * malformed JSON (callers surface the bridge-style message).
 */
export function parseProjectFile(text: string): { modelJson: string; name: string } {
  const doc = JSON.parse(text) as Record<string, unknown>;
  if (doc && typeof doc === "object" && doc.app === "QREP" && "model" in doc) {
    const model = doc.model as QuiltModel;
    return {
      modelJson: JSON.stringify(model),
      name: typeof doc.name === "string" ? doc.name : (model?.metadata?.name ?? "Untitled"),
    };
  }
  const model = doc as unknown as QuiltModel;
  return { modelJson: text, name: model?.metadata?.name ?? "Untitled" };
}
