/**
 * The confirm screen's state (C3b, issue #101), pure: no React, no DOM, no
 * engine, so the races are unit tested here and photo.tsx only wires it.
 *
 * Every decode and staging result carries the sequence it started under, and
 * every new photo and every clear bumps the sequence, so a result for an
 * older photo changes nothing. At 834d8be Analyze ran before the new photo
 * was staged, and after Cancel the request carried the previous photo's
 * bytes (web-09, ux-16). Pins start at a neutral inset, never a guessed quad
 * (criteria U3-4; approaches-37), and each new photo starts from its own
 * default pins and the default counts (criteria U3-8).
 */
import type { BorderBand, Corners, Point } from "../engine/contract";
import type { AxisCount } from "./counts";
import { neutralInset, quadProblem, type CornerName, type FrameMode } from "./frame";
import type { Size } from "./geometry";

export type ConfirmStatus = "empty" | "decoding" | "ready" | "failed";

export const DEFAULT_FRAME_MODE: FrameMode = "outer_edge";

/** "Empty" counts (criteria U3-8): one block of one square per axis, the count panel's floor. */
export const DEFAULT_COUNTS: { readonly across: AxisCount; readonly down: AxisCount } = Object.freeze({
  across: Object.freeze({ blocks: 1, squaresPerBlock: 1 }),
  down: Object.freeze({ blocks: 1, squaresPerBlock: 1 }),
});

/**
 * Why Continue stays off when the photo on screen is not the decoded photo:
 * the pins are placed through the img element's own pixels and the crop is
 * cut from the decoded bitmap's, so a browser that orients or sizes one
 * differently from the other would cut a quad the user never pinned.
 */
export const DISPLAY_ERROR = "QREP could not show this photo the way it reads it. Go back and choose it again.";

/** What Continue reads: the frame as confirmed, bound to its staging sequence. */
export interface ConfirmedFrame {
  seq: number;
  mode: FrameMode;
  corners: Corners;
  bands: BorderBand[];
  across: AxisCount;
  down: AxisCount;
}

const copyCorners = (c: Corners): Corners => ({
  top_left: { ...c.top_left },
  top_right: { ...c.top_right },
  bottom_right: { ...c.bottom_right },
  bottom_left: { ...c.bottom_left },
});

const copyBands = (bands: readonly BorderBand[]): BorderBand[] => bands.map((band) => ({ ...band }));

export class ConfirmFlow {
  /** The staging sequence; bumps on every new photo and on clear(). */
  seq = 0;
  status: ConfirmStatus = "empty";
  error: string | null = null;
  /** The decoded photo, EXIF applied. */
  size: Size | null = null;
  mode: FrameMode = DEFAULT_FRAME_MODE;
  /** Decoded-photo pixels. */
  corners: Corners | null = null;
  bands: BorderBand[] = [];
  across: AxisCount = { ...DEFAULT_COUNTS.across };
  down: AxisCount = { ...DEFAULT_COUNTS.down };
  /** Continue is cutting and staging the crop. */
  staging = false;
  /**
   * Finished square size in eighths for converting typed band inches: null
   * until a read gives A10's default (carried item from C3a, #149).
   */
  squareEighths: number | null = null;
  /** DISPLAY_ERROR once the img shows another size than the decoded photo, or fails to load; else null. */
  displayProblem: string | null = null;

  private reset(status: ConfirmStatus): void {
    this.status = status;
    this.error = null;
    this.size = null;
    this.mode = DEFAULT_FRAME_MODE;
    this.corners = null;
    this.bands = [];
    // Copies, so editing the flow's counts can never edit the defaults.
    this.across = { ...DEFAULT_COUNTS.across };
    this.down = { ...DEFAULT_COUNTS.down };
    this.staging = false;
    this.squareEighths = null;
    this.displayProblem = null;
  }

  /** Starts a photo: seq += 1, status "decoding", everything else back to defaults. */
  newPhoto(): number {
    this.seq += 1;
    this.reset("decoding");
    return this.seq;
  }

  isCurrent(seq: number): boolean {
    return seq === this.seq;
  }

  // A decode result lands once, on the photo still decoding, so a repeated
  // or late result can never reset pins the user already moved.
  private decoding(seq: number): boolean {
    return this.isCurrent(seq) && this.status === "decoding";
  }

  /** False (no change) when stale; else "ready" with the pins at the neutral inset. */
  decoded(seq: number, size: Size): boolean {
    if (!this.decoding(seq)) return false;
    this.status = "ready";
    this.size = { width: size.width, height: size.height };
    this.corners = neutralInset(this.size);
    return true;
  }

  /** False when stale; else "failed" with the message. */
  decodeFailed(seq: number, message: string): boolean {
    if (!this.decoding(seq)) return false;
    this.status = "failed";
    this.error = message;
    return true;
  }

  /**
   * The confirm screen's img loaded at its natural size. False (no change)
   * when stale or not ready; else a size that differs from the decoded one
   * blocks Continue, and a matching one clears an earlier failure.
   */
  displayLoaded(seq: number, natural: Size): boolean {
    if (!this.isCurrent(seq) || this.status !== "ready" || !this.size) return false;
    const same = natural.width === this.size.width && natural.height === this.size.height;
    this.displayProblem = same ? null : DISPLAY_ERROR;
    return true;
  }

  /** The confirm screen's img failed to load. False when stale or not ready; else it blocks Continue. */
  displayFailed(seq: number): boolean {
    if (!this.isCurrent(seq) || this.status !== "ready") return false;
    this.displayProblem = DISPLAY_ERROR;
    return true;
  }

  setCorner(name: CornerName, point: Point): void {
    if (!this.corners) return;
    // A new object, so a render keyed on the corners sees the move.
    this.corners = { ...this.corners, [name]: { x: point.x, y: point.y } };
  }

  setMode(mode: FrameMode): void {
    this.mode = mode;
  }

  setBands(bands: BorderBand[]): void {
    this.bands = copyBands(bands);
  }

  setCounts(across: AxisCount, down: AxisCount): void {
    this.across = { ...across };
    this.down = { ...down };
  }

  setSquareEighths(eighths: number | null): void {
    this.squareEighths = eighths;
  }

  /** Why Continue is off, or null: not ready, a display problem, already staging, or quadProblem(corners). */
  get blocked(): string | null {
    if (this.status === "empty" || this.status === "failed") return "Choose a photo of your quilt first.";
    if (this.status === "decoding" || !this.corners) return "QREP is still opening the photo.";
    if (this.displayProblem) return this.displayProblem;
    if (this.staging) return "QREP is preparing the photo.";
    return quadProblem(this.corners);
  }

  get canContinue(): boolean {
    return this.blocked === null;
  }

  /**
   * Starts staging and returns the confirmed frame, corners always included
   * whether or not a pin moved (criteria U3-5), or null when it cannot
   * continue. The frame is a copy, so a pin moved while staging runs cannot
   * change the read in flight.
   */
  beginStaging(): ConfirmedFrame | null {
    if (!this.canContinue || !this.corners) return null;
    this.staging = true;
    return {
      seq: this.seq,
      mode: this.mode,
      corners: copyCorners(this.corners),
      bands: copyBands(this.bands),
      across: { ...this.across },
      down: { ...this.down },
    };
  }

  /** staging = false, only for the current seq. */
  endStaging(seq: number): void {
    if (this.isCurrent(seq)) this.staging = false;
  }

  /**
   * Puts back the frame a read used, for "Adjust the crop": a pin, count,
   * band or mode change made while that read staged never reached it, so
   * showing the change would claim it had been read. Only for the current
   * seq; false (no change) otherwise.
   */
  restore(frame: ConfirmedFrame): boolean {
    if (!this.isCurrent(frame.seq) || this.status !== "ready") return false;
    this.mode = frame.mode;
    this.corners = copyCorners(frame.corners);
    this.bands = copyBands(frame.bands);
    this.across = { ...frame.across };
    this.down = { ...frame.down };
    return true;
  }

  /** seq += 1, so in-flight work goes stale; status "empty"; all defaults. */
  clear(): void {
    this.seq += 1;
    this.reset("empty");
  }
}
