/**
 * S2 crop-flow state machine (sprint 3, issue #68).
 *
 * Pure state, no React and no engine: the provider stages the photo, calls
 * detect_quad, and feeds the result back through detectionResolved(seq).
 * The sequence number makes the second-photo rule mechanical: a detection
 * belonging to an earlier enterCrop() is stale and ignored, so a new photo
 * always starts from ITS OWN detection, never the previous corners.
 *
 * Corner-passing rule (keeps every frozen sprint 2 result assertion
 * bit-identical): analyze() returns corners ONLY when the user moved a
 * pin. Untouched pins - default, snapped-in detected, or seeded from a
 * confirmed run - pass nothing, and the pipeline re-detects the same quad
 * deterministically. Default pins are a placeholder, not information;
 * passing them would claim a crop the user never chose.
 */

export type PhotoScreen = "idle" | "crop" | "progress" | "results";
export type QuadSource = "default" | "detected" | "user" | "seeded";

export interface DetectedQuad {
  quad: [number, number][];
  tier: number | null;
  confidence: number;
}

/** Normalized [0,1] default pins, inset 6% (the sprint 2 corner-pin seed). */
export const DEFAULT_PIN_CORNERS: [number, number][] = [
  [0.06, 0.06],
  [0.94, 0.06],
  [0.94, 0.94],
  [0.06, 0.94],
];

function clonePins(pins: [number, number][]): [number, number][] {
  return pins.map(([x, y]) => [x, y]) as [number, number][];
}

export class PhotoFlowMachine {
  state: PhotoScreen = "idle";
  corners: [number, number][] = clonePins(DEFAULT_PIN_CORNERS);
  quadSource: QuadSource = "default";
  detectedQuad: [number, number][] | null = null;
  detectedInfo: DetectedQuad | null = null;
  detectPending = false;
  private seq = 0;
  private confirmed: [number, number][] | null = null;

  /** New photo staged: enter crop with fresh pins; returns the detection
   * sequence the provider must echo back into detectionResolved. */
  enterCrop(): number {
    this.state = "crop";
    this.corners = clonePins(DEFAULT_PIN_CORNERS);
    this.quadSource = "default";
    this.detectedQuad = null;
    this.detectedInfo = null;
    this.detectPending = true;
    this.confirmed = null;
    return ++this.seq;
  }

  detectionResolved(seq: number, result: DetectedQuad): void {
    if (seq !== this.seq) return; // stale: belongs to a previous photo
    this.detectPending = false;
    this.detectedQuad = clonePins(result.quad);
    this.detectedInfo = result;
    if (this.quadSource === "default") {
      // snap in - unless the user already moved a pin (user wins)
      this.corners = clonePins(result.quad);
      this.quadSource = "detected";
    }
  }

  detectionFailed(seq: number): void {
    if (seq !== this.seq) return;
    this.detectPending = false;
  }

  movePin(index: number, xy: [number, number]): void {
    this.corners = this.corners.map((c, i) => (i === index ? xy : c)) as [number, number][];
    this.quadSource = "user";
  }

  resetToAuto(): void {
    if (this.detectedQuad) {
      this.corners = clonePins(this.detectedQuad);
      this.quadSource = "detected";
    } else {
      this.corners = clonePins(DEFAULT_PIN_CORNERS);
      this.quadSource = "default";
    }
  }

  /** Move to progress; returns the corners to pass to reverse, or null when
   * the pipeline should detect on its own (pins untouched by the user). */
  analyze(): [number, number][] | null {
    this.confirmed = clonePins(this.corners);
    this.state = "progress";
    return this.quadSource === "user" ? clonePins(this.corners) : null;
  }

  results(): void {
    this.state = "results";
  }

  /** "Adjust the crop" from results: re-enter crop seeded with the quad the
   * confirmed run used. */
  seedFromConfirmed(): void {
    this.state = "crop";
    if (this.confirmed) {
      this.corners = clonePins(this.confirmed);
      this.quadSource = "seeded";
    }
    this.detectPending = false;
  }

  cancel(): void {
    this.reset();
  }

  backFromCrop(): void {
    this.reset();
  }

  reset(): void {
    this.state = "idle";
    this.corners = clonePins(DEFAULT_PIN_CORNERS);
    this.quadSource = "default";
    this.detectedQuad = null;
    this.detectedInfo = null;
    this.detectPending = false;
    this.confirmed = null;
  }
}
