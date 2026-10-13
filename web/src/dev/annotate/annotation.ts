/**
 * D3a's annotation format, as the dev annotate page reads and writes it
 * (C3a, issue #149; corpus/README.md; corpus/schema/annotation.schema.json,
 * exported from scripts/eval/qrep_eval/annotation.py).
 *
 * Every annotated field is a list of claims, each a value with a provenance
 * code, so a verification sits beside the proposals instead of overwriting
 * them (plan section 8.2). The page writes only verified-jake claims, for
 * the frame, the counts and the construction class, and keeps every other
 * field and claim as it read them. Coordinates are pixels of the source
 * image (canvas), whichever file the page shows.
 */
import type { BorderBand, Corners, Counts, FieldFrame, OuterEdgeFrame } from "../../engine/contract";
import type { AxisCount } from "../../confirm/counts";
import { cornersToQuad, fieldInsideProblem, quadProblem, type FrameMode } from "../../confirm/frame";
import type { Size } from "../../confirm/geometry";

export const VERIFIED = "verified-jake";

export const CONSTRUCTION_CLASSES = ["squares", "hst", "qst", "snowball", "flying_geese", "out_of_scope"] as const;
export type ConstructionClass = (typeof CONSTRUCTION_CLASSES)[number];

export const CLASS_LABELS: Record<ConstructionClass, string> = {
  squares: "Squares",
  hst: "Half-square triangles (HST)",
  qst: "Quarter-square triangles (QST)",
  snowball: "Snowball",
  flying_geese: "Flying geese",
  out_of_scope: "Out of scope",
};

/** The outer edge with its bands from the outside in, and the field corners when they show. */
export interface AnnotatedFrame {
  outer_edge: OuterEdgeFrame;
  field?: FieldFrame | null;
}

export interface Claim<T> {
  value: T;
  provenance: string;
}

export interface Annotation {
  schema_version: 1;
  photo: string;
  sha256: string;
  canvas: [number, number];
  frame?: Claim<AnnotatedFrame>[];
  counts?: Claim<Counts>[];
  construction_class?: Claim<string>[];
  [field: string]: unknown;
}

/** What the page edits: the pins, bands, counts and class of one photo. */
export interface Draft {
  outer: Corners;
  field: Corners | null;
  bands: BorderBand[];
  across: AxisCount;
  down: AxisCount;
  constructionClass: ConstructionClass | null;
}

export class AnnotationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AnnotationError";
  }
}

const IDENTITY_FIELDS = new Set(["schema_version", "photo", "sha256", "canvas"]);
const SHA256 = /^[0-9a-f]{64}$/;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

const isWhole = (value: unknown, min: number): value is number =>
  typeof value === "number" && Number.isInteger(value) && value >= min;

function isPoint(value: unknown): boolean {
  return isRecord(value) && Number.isFinite(value.x) && Number.isFinite(value.y);
}

function isCorners(value: unknown): boolean {
  return isRecord(value) && ["top_left", "top_right", "bottom_right", "bottom_left"].every((k) => isPoint(value[k]));
}

function isFrameValue(value: unknown): boolean {
  if (!isRecord(value) || !isRecord(value.outer_edge)) return false;
  const edge = value.outer_edge;
  const bandsOk =
    Array.isArray(edge.bands) &&
    edge.bands.every((band: unknown) => isRecord(band) && Number(band.width_squares) > 0);
  const fieldOk = value.field == null || (isRecord(value.field) && isCorners(value.field.corners));
  return edge.kind === "outer_edge" && isCorners(edge.corners) && bandsOk && fieldOk;
}

function isCountsValue(value: unknown): boolean {
  return (
    isRecord(value) &&
    ["blocks_across", "blocks_down", "squares_per_block_across", "squares_per_block_down"].every((k) =>
      isWhole(value[k], 1),
    )
  );
}

/** Reads an annotation file, or throws AnnotationError with a plain sentence. */
export function parseAnnotation(text: string): Annotation {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    throw new AnnotationError("This file is not JSON, so it is not an annotation.");
  }
  if (!isRecord(data)) throw new AnnotationError("This file holds no annotation object.");
  if (data.schema_version !== 1) {
    throw new AnnotationError(`This annotation has schema version ${String(data.schema_version)}; the page reads version 1.`);
  }
  if (typeof data.photo !== "string" || data.photo.length === 0) {
    throw new AnnotationError("This annotation names no photo.");
  }
  if (typeof data.sha256 !== "string" || !SHA256.test(data.sha256)) {
    throw new AnnotationError("This annotation's sha256 is not 64 lowercase hex digits.");
  }
  const canvas = data.canvas;
  if (!Array.isArray(canvas) || canvas.length !== 2 || !canvas.every((side) => isWhole(side, 1))) {
    throw new AnnotationError("This annotation's canvas is not [width, height] in whole pixels.");
  }
  for (const [name, claims] of Object.entries(data)) {
    if (IDENTITY_FIELDS.has(name)) continue;
    const listOk =
      Array.isArray(claims) &&
      claims.every((claim) => isRecord(claim) && typeof claim.provenance === "string" && "value" in claim);
    if (!listOk) throw new AnnotationError(`This annotation's ${name} field is not a list of claims.`);
  }
  const check = (name: string, valid: (value: unknown) => boolean) => {
    const claims = (data as Record<string, unknown>)[name] as Claim<unknown>[] | undefined;
    if (claims?.some((claim) => !valid(claim.value))) {
      throw new AnnotationError(`This annotation has a ${name} claim the page cannot read.`);
    }
  };
  check("frame", isFrameValue);
  check("counts", isCountsValue);
  check("construction_class", (value) => typeof value === "string");
  return data as unknown as Annotation;
}

export function newAnnotation(photo: string, sha256: string, canvas: [number, number]): Annotation {
  return { schema_version: 1, photo, sha256, canvas };
}

const DEFAULT_ORDER = [VERIFIED, "proposed-a", "proposed-b"];

function pick<T>(claims: Claim<T>[] | undefined, order: string[]): Claim<T> | undefined {
  for (const code of order) {
    const found = claims?.find((claim) => claim.provenance === code);
    if (found) return found;
  }
  return undefined;
}

/** The provenance codes that have a frame claim, best first. */
export function frameProvenances(annotation: Annotation): string[] {
  const codes = (annotation.frame ?? []).map((claim) => claim.provenance);
  return [...DEFAULT_ORDER.filter((code) => codes.includes(code)), ...codes.filter((c) => !DEFAULT_ORDER.includes(c))];
}

/**
 * The values the page opens with: each field's verified claim, else proposer
 * A's, else proposer B's, or a chosen provenance first.
 */
export function startingValues(annotation: Annotation, provenance?: string) {
  const order = provenance ? [provenance, ...DEFAULT_ORDER.filter((c) => c !== provenance)] : DEFAULT_ORDER;
  const frame = pick(annotation.frame, order);
  const cls = pick(annotation.construction_class, order)?.value;
  return {
    provenance: frame?.provenance ?? null,
    frame: frame?.value ?? null,
    counts: pick(annotation.counts, order)?.value ?? null,
    constructionClass: (CONSTRUCTION_CLASSES as readonly string[]).includes(cls ?? "")
      ? (cls as ConstructionClass)
      : null,
  };
}

/**
 * The frame claim's value. Field corners with no border are an outer edge
 * equal to the field with no bands (corpus/README.md: no border means no
 * bands, and the field lies on the outer edge).
 */
export function annotatedFrame(
  mode: FrameMode,
  corners: Corners,
  bands: readonly BorderBand[],
  field: Corners | null,
): AnnotatedFrame {
  if (mode === "field") {
    return {
      outer_edge: { kind: "outer_edge", corners, bands: [] },
      field: { kind: "field", corners },
    };
  }
  return {
    outer_edge: { kind: "outer_edge", corners, bands: bands.map((b) => ({ width_squares: b.width_squares })) },
    field: field ? { kind: "field", corners: field } : null,
  };
}

export interface Verified {
  frame: AnnotatedFrame;
  counts: Counts;
  constructionClass: ConstructionClass | null;
}

function replaceVerified<T>(claims: Claim<T>[] | undefined, value: T): Claim<T>[] {
  // The model allows one claim per provenance in a field, so a new
  // verification replaces the last one.
  return [...(claims ?? []).filter((claim) => claim.provenance !== VERIFIED), { value, provenance: VERIFIED }];
}

/** A copy of the annotation with this verification; every other claim stays as it was. */
export function withVerified(annotation: Annotation, verified: Verified & { constructionClass: ConstructionClass }): Annotation {
  return {
    ...annotation,
    frame: replaceVerified(annotation.frame, verified.frame),
    counts: replaceVerified(annotation.counts, verified.counts),
    construction_class: replaceVerified(annotation.construction_class, verified.constructionClass),
  };
}

/** Why the verification cannot be saved, as plain sentences; empty when it can. */
export function saveProblems(verified: Verified, canvas: [number, number]): string[] {
  const [width, height] = canvas;
  const problems: string[] = [];
  const { outer_edge: edge, field } = verified.frame;
  const quads = [edge.corners, ...(field ? [field.corners] : [])];
  for (const corner of quads.flatMap(cornersToQuad)) {
    if (!(corner.x >= 0 && corner.x <= width && corner.y >= 0 && corner.y <= height)) {
      problems.push(`A pin lies off the photo at (${corner.x}, ${corner.y}); the photo is ${width} x ${height} pixels.`);
    }
  }
  const edgeProblem = quadProblem(edge.corners, "The outer edge");
  if (edgeProblem) problems.push(edgeProblem);
  if (field) {
    const fieldProblem = quadProblem(field.corners, "The field");
    if (fieldProblem) problems.push(fieldProblem);
    else if (!edgeProblem) {
      const inside = fieldInsideProblem(edge.corners, field.corners);
      if (inside) problems.push(inside);
    }
  }
  if (!edge.bands.every((band) => band.width_squares > 0 && Number.isFinite(band.width_squares))) {
    problems.push("Every border band needs a width above zero.");
  }
  if (!isCountsValue(verified.counts)) problems.push("Every count needs a whole number of at least 1.");
  if (verified.constructionClass === null) problems.push("Choose a construction class before you save.");
  return problems;
}

export function serializeAnnotation(annotation: Annotation): string {
  return `${JSON.stringify(annotation, null, 2)}\n`;
}

/**
 * Whether an image is the canvas's shape within 1 percent, the rule
 * to_read_request applies to a downsized copy. A miss is usually a photo
 * turned by its EXIF orientation, which would stretch every pin.
 */
export function aspectMatches(canvas: [number, number], image: Size): boolean {
  const canvasRatio = canvas[0] / canvas[1];
  return Math.abs(image.width / image.height - canvasRatio) / canvasRatio <= 0.01;
}

/** The file name without folders or extension: annotations/<stem>.json. */
export function photoStem(photo: string): string {
  const name = photo.split(/[\\/]/).pop() ?? photo;
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(0, dot) : name;
}
