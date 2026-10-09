/**
 * Bridge v2 contract (E1a, issue #174; E1b, issue #175): the TypeScript half
 * of qrep/contract.py. It holds the contract version, the worker's boundary
 * helpers, and the v2 request and result types, the single TS result-types
 * file (plan section 4.2).
 *
 * Any change to the bridge's request or response shapes bumps
 * CONTRACT_VERSION here and in qrep/contract.py in the same commit;
 * tests/test_bridge.py fails when the two literals differ, and when an
 * interface's field names differ from its pydantic model. Each interface
 * keeps one field per line and no inline object types, so that test can read
 * it. Lengths are integer eighths of an inch; coordinates are staged-image
 * pixels.
 */
import type { QuiltModel } from "../model/types";

export const CONTRACT_VERSION = 2;

// ------------------------------------------------------------ read request

export interface Point {
  x: number;
  y: number;
}

export interface Corners {
  top_left: Point;
  top_right: Point;
  bottom_right: Point;
  bottom_left: Point;
}

/** One border band, its width in finished squares (need not be whole). */
export interface BorderBand {
  width_squares: number;
}

/** The four corners of the pieced field. */
export interface FieldFrame {
  kind: "field";
  corners: Corners;
}

/** The four outer-edge corners plus the border bands from the outside in. */
export interface OuterEdgeFrame {
  kind: "outer_edge";
  corners: Corners;
  bands: BorderBand[];
}

export type Frame = FieldFrame | OuterEdgeFrame;

/** Counts in quilter units: blocks across and down, squares per block. */
export interface Counts {
  blocks_across: number;
  blocks_down: number;
  squares_per_block_across: number;
  squares_per_block_down: number;
}

/**
 * The confirmed read's request. token is the staged image from stage_photo;
 * the corners are pixels of that staged crop, and crop_offset is the crop's
 * top-left corner in the decoded photo (#101). fabric_count is 2 to 12.
 */
export interface ReadRequest {
  token: string;
  frame: Frame;
  crop_offset: Point;
  counts: Counts;
  fabric_count?: number | null;
}

// ------------------------------------------------------------- v2 results

/** Why a result was held or refused: a stable code and a plain message. */
export interface Reason {
  code: string;
  message: string;
}

export const READ_OUTCOMES = ["read", "held", "refused"] as const;
export const SIZE_OUTCOMES = ["sized"] as const;
export const PATTERN_OUTCOMES = ["pattern_ready", "refused"] as const;
export const OUTCOMES = ["read", "held", "refused", "sized", "pattern_ready"] as const;
export type Outcome = (typeof OUTCOMES)[number];

export interface ReadResult {
  outcome: (typeof READ_OUTCOMES)[number];
  model?: QuiltModel | null;
  reason?: Reason | null;
}

export type SizeSource = "typed" | "preset" | "default";

/** The size you set: typed (width, height or both), a preset by name, or the default. */
export interface SizeRequest {
  source: SizeSource;
  width?: number | null;
  height?: number | null;
  preset?: string | null;
}

/** How the finished size was set; requested sizes are null for a default. */
export interface SizeBasis {
  source: SizeSource;
  requested_width: number | null;
  requested_height: number | null;
  achieved_width: number;
  achieved_height: number;
}

export interface SizeResult {
  outcome: (typeof SIZE_OUTCOMES)[number];
  model: QuiltModel;
  basis: SizeBasis;
}

/** A palette fabric: its letter, name and the yards the top needs. */
export interface FabricLine {
  letter: string;
  fabric_id: string;
  name: string;
  yards: number;
}

/** A binding, backing or wide-back line; fabric_id is null for backing. */
export interface PurchaseLine {
  fabric_id: string | null;
  name: string;
  yards: number;
}

export interface BattingSize {
  width: number;
  height: number;
}

/**
 * What Your pattern shows, from the same data as the PDF (PS-40). size_basis
 * is null when the model records none, wide_back when no wide-back line was
 * computed; strip_width and backing_width are the two width assumptions.
 */
export interface PatternSummary {
  finished_width: number;
  finished_height: number;
  size_basis: SizeBasis | null;
  method: string;
  method_reason: string;
  fabrics: FabricLine[];
  binding: PurchaseLine[];
  backing: PurchaseLine;
  wide_back: PurchaseLine | null;
  batting: BattingSize;
  strip_width: number;
  backing_width: number;
  uncertain_squares: number;
}

/** The one pattern download: the PDF, base64, with its summary. */
export interface PatternResult {
  outcome: (typeof PATTERN_OUTCOMES)[number];
  pdf_b64?: string | null;
  summary?: PatternSummary | null;
  reason?: Reason | null;
}

/** A v2 result whose outcome is missing, unknown or not one this call returns. */
export class OutcomeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "OutcomeError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * The outcome of a v2 result, checked against the outcomes its call returns.
 * A missing, unknown or other-call outcome throws OutcomeError: it is never
 * read as success (the verdictStory.ts:82 hazard; SPEC.md section 12.1).
 */
export function parseOutcome<T extends Outcome>(result: unknown, allowed: readonly T[]): T {
  if (!isRecord(result)) throw new OutcomeError("the engine returned no result object");
  const outcome = result.outcome;
  if (outcome === undefined || outcome === null) {
    throw new OutcomeError("the engine result states no outcome");
  }
  if (typeof outcome !== "string" || !(OUTCOMES as readonly string[]).includes(outcome)) {
    throw new OutcomeError(`the engine returned an unknown outcome: ${JSON.stringify(outcome)}`);
  }
  if (!(allowed as readonly string[]).includes(outcome)) {
    throw new OutcomeError(
      `the engine returned outcome ${outcome}, but this call returns ${allowed.join(" or ")}`,
    );
  }
  return outcome as T;
}

function requireReason(result: Record<string, unknown>, outcome: string): void {
  const reason = result.reason;
  if (!isRecord(reason) || typeof reason.code !== "string" || typeof reason.message !== "string") {
    throw new OutcomeError(`a ${outcome} result needs a reason with a code and a message`);
  }
}

function requireField(result: Record<string, unknown>, field: string, outcome: string): void {
  const value = result[field];
  const present = field === "pdf_b64" ? typeof value === "string" : isRecord(value);
  if (!present) throw new OutcomeError(`a ${outcome} result needs its ${field}`);
}

/** read_confirmed's result: a read carries the model, a hold or refusal its reason. */
export function parseReadResult(result: unknown): ReadResult {
  const outcome = parseOutcome(result, READ_OUTCOMES);
  const record = result as Record<string, unknown>;
  if (outcome === "read") requireField(record, "model", outcome);
  else requireReason(record, outcome);
  return result as ReadResult;
}

/** size_pattern's result: the sized model and its size basis. */
export function parseSizeResult(result: unknown): SizeResult {
  const outcome = parseOutcome(result, SIZE_OUTCOMES);
  const record = result as Record<string, unknown>;
  requireField(record, "model", outcome);
  requireField(record, "basis", outcome);
  return result as SizeResult;
}

/** export_pattern's result: a ready pattern carries the PDF and its summary. */
export function parsePatternResult(result: unknown): PatternResult {
  const outcome = parseOutcome(result, PATTERN_OUTCOMES);
  const record = result as Record<string, unknown>;
  if (outcome === "pattern_ready") {
    requireField(record, "pdf_b64", outcome);
    requireField(record, "summary", outcome);
  } else requireReason(record, outcome);
  return result as PatternResult;
}

// ------------------------------------------------------------ worker boot

/**
 * The URL of a file in the site's wheels folder, tagged with this app's
 * contract version. A page built for another contract asks for other URLs,
 * so the browser cache never hands it the manifest or wheel of the release it
 * replaced, and a reload after a mismatch fetches a matching pair. micropip
 * names a wheel from the URL path, so the query does not change the install.
 */
export function engineAssetUrl(baseUrl: string, file: string): string {
  return `${baseUrl}wheels/${file}?contract=${CONTRACT_VERSION}`;
}

/**
 * The version in bridge.contract_version()'s raw envelope, or null when the
 * engine reports none: a wheel that predates the function (raw is
 * undefined), or an envelope that is malformed, an error, or carries no
 * whole-number version.
 */
export function engineContractVersion(raw: unknown): number | null {
  if (typeof raw !== "string") return null;
  let envelope: unknown;
  try {
    envelope = JSON.parse(raw);
  } catch {
    return null;
  }
  if (typeof envelope !== "object" || envelope === null) return null;
  const { ok, result } = envelope as { ok?: unknown; result?: unknown };
  if (ok !== true || typeof result !== "object" || result === null) return null;
  const version = (result as { contract_version?: unknown }).contract_version;
  return typeof version === "number" && Number.isInteger(version) ? version : null;
}

/**
 * The boot-failed message when the engine's contract differs from this
 * app's, or null when they agree. A mismatch means the browser holds a page
 * and an engine wheel from different releases, so a reload fetches a
 * matching pair.
 */
export function contractMismatch(
  engineVersion: number | null,
  appVersion = CONTRACT_VERSION,
): string | null {
  if (engineVersion === appVersion) return null;
  const reported = engineVersion === null ? "no contract version" : `version ${engineVersion}`;
  return (
    `This app needs engine contract version ${appVersion}, but the loaded engine reports ` +
    `${reported}. Reload the page to load a matching engine.`
  );
}

// hasattr keeps a wheel that predates contract_version() from raising here;
// it returns None, which reaches JS as undefined and reads as no version.
const CONTRACT_PROBE =
  "import qrep.bridge\n" +
  "qrep.bridge.contract_version() if hasattr(qrep.bridge, 'contract_version') else None";

/**
 * Throws the boot-failed message unless the imported engine speaks this
 * app's contract. The worker calls it after `import qrep.bridge` and before
 * boot-done, passing Pyodide's runPython.
 */
export function assertEngineContract(runPython: (code: string) => unknown): void {
  const mismatch = contractMismatch(engineContractVersion(runPython(CONTRACT_PROBE)));
  if (mismatch !== null) throw new Error(mismatch);
}

/**
 * Bridge call arguments with each null swapped for undefined. Pyodide 0.28
 * converts JS null to jsnull, not None, so an optional argument the UI
 * leaves null would reach the bridge as a wrong type; undefined becomes None.
 */
export function bridgeArgs(args: readonly unknown[]): unknown[] {
  return args.map((arg) => (arg === null ? undefined : arg));
}
