/*
 * Cross-builder photo API shim (S6, issue #46).
 *
 * The `photo`, `roundtrip`, and `uncertainty` surfaces on useProject() are
 * owned by the state builder (src/state/project.tsx, out of this slice's
 * scope). The photo shell is built against that FIXED contract; this module
 * declares the contract types and typed accessors so the shell type-checks and
 * integrates without editing project.tsx. When the state layer lands the
 * surface, the accessors read it directly; the cast stays sound because the
 * shapes match the contract.
 *
 * usePhoto() assumes the surface is present (PhotoFlow only mounts once the
 * state layer has entered the photo flow). useRoundTrip / useUncertainty read
 * defensively so panels that mount before integration (RoundTripPanel lives in
 * the always-present Pattern tab) render inert instead of throwing.
 */
import { useProject } from "../state/project";
import type { VisionState } from "../engine/rpc";

export type PhotoScreen = "idle" | "progress" | "results" | "corners";

export interface PhotoResult {
  modelJson: string;
  stageConfidence: Record<string, number>;
  uncertainCount: number;
  reverseMs: number;
}

export interface PhotoApi {
  state: PhotoScreen;
  photoUrl: string | null;
  result: PhotoResult | null;
  visionState: VisionState;
  visionBytes: number | null;
  start(file: File): Promise<void>;
  startSample(): Promise<void>;
  cancel(): void;
  toCorners(): void;
  corners: [number, number][] | null;
  setCorner(index: number, xy: [number, number]): void;
  resetCorners(): void;
  rerunWithCorners(): Promise<void>;
  openInEditor(): void;
  backToDropzone(): void;
  /**
   * Optional state-layer hooks the fixed contract left implicit:
   *  - backToResults returns from the corner editor to the results screen.
   *  - retryVision reloads the vision stack and re-runs the pending reverse
   *    after a failed load (drives the vision-retry button).
   * The shell degrades to a no-op when the state layer does not expose them.
   */
  backToResults?(): void;
  retryVision?(): void;
}

export interface RoundTripReport {
  dimsMatch: boolean;
  cellAccuracy: number;
}

export interface RoundTripApi {
  run(level: 0 | 2): Promise<void>;
  report: RoundTripReport | null;
}

export interface UncertaintyApi {
  count: number;
  showUncertain: boolean;
  toggle(): void;
}

interface PhotoProject {
  photo: PhotoApi;
  roundtrip: RoundTripApi;
  uncertainty: UncertaintyApi;
}

export function usePhoto(): PhotoApi {
  return (useProject() as unknown as PhotoProject).photo;
}

export function useRoundTrip(): RoundTripApi | null {
  return (useProject() as unknown as Partial<PhotoProject>).roundtrip ?? null;
}

export function useUncertainty(): UncertaintyApi | null {
  return (useProject() as unknown as Partial<PhotoProject>).uncertainty ?? null;
}
