/**
 * Pin drill records (C3a, issue #149; plan section 9, item 4). The drill
 * hides any loaded annotation, so the placements are unprompted (plan
 * section 8.2), and logs each placed pin and each count entered with the
 * photo id. D10 scores them against verified truth; nothing here computes
 * an error.
 */
import type { Counts, Point } from "../../engine/contract";
import { neutralInset, type FrameMode } from "../../confirm/frame";
import type { Draft } from "./annotation";

/** "outer.top_left", "field.bottom_right", ... */
export type PinId = string;

export interface DeviceInfo {
  viewport_width: number;
  viewport_height: number;
  device_pixel_ratio: number;
  pointer: "coarse" | "fine";
}

export type DrillRecord =
  | { seq: number; t_ms: number; kind: "pin"; pin: PinId; x: number; y: number; input: "pointer" | "key" }
  | { seq: number; t_ms: number; kind: "counts"; counts: Counts };

export interface DrillLog {
  drill_version: 1;
  photo: string;
  sha256: string;
  canvas: [number, number];
  frame_mode: FrameMode;
  started_at: string;
  device: DeviceInfo;
  records: DrillRecord[];
}

export interface PhotoIdentity {
  photo: string;
  sha256: string;
  canvas: [number, number];
}

export function createDrill(
  identity: PhotoIdentity,
  frameMode: FrameMode,
  device: DeviceInfo,
  startedAt: string,
): DrillLog {
  return {
    drill_version: 1,
    photo: identity.photo,
    sha256: identity.sha256,
    canvas: identity.canvas,
    frame_mode: frameMode,
    started_at: startedAt,
    device,
    records: [],
  };
}

/** t_ms counts from the drill's start, so D10 can see how long each placement took. */
export function recordPin(log: DrillLog, pin: PinId, point: Point, input: "pointer" | "key", tMs: number): DrillLog {
  const record: DrillRecord = { seq: log.records.length + 1, t_ms: tMs, kind: "pin", pin, x: point.x, y: point.y, input };
  return { ...log, records: [...log.records, record] };
}

export function recordCounts(log: DrillLog, counts: Counts, tMs: number): DrillLog {
  const record: DrillRecord = { seq: log.records.length + 1, t_ms: tMs, kind: "counts", counts: { ...counts } };
  return { ...log, records: [...log.records, record] };
}

export function serializeDrill(log: DrillLog): string {
  return `${JSON.stringify(log, null, 2)}\n`;
}

/** The drill's opening state: nothing from the annotation shows. */
export function drillStart(canvas: [number, number]): Draft {
  return {
    outer: neutralInset({ width: canvas[0], height: canvas[1] }),
    field: null,
    bands: [],
    across: { blocks: 1, squaresPerBlock: 1 },
    down: { blocks: 1, squaresPerBlock: 1 },
    constructionClass: null,
  };
}
