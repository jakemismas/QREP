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

export type PhotoScreen = "idle" | "crop" | "progress" | "results";

export interface PhotoResult {
  modelJson: string;
  stageConfidence: Record<string, number>;
  uncertainCount: number;
  reverseMs: number;
}

/** S2 (issue #68): idle -> crop -> progress -> results; the post-results
 * corners screen is retired and toCrop() re-enters the crop screen seeded
 * with the confirmed quad. */
export interface PhotoApi {
  state: PhotoScreen;
  photoUrl: string | null;
  result: PhotoResult | null;
  visionState: VisionState;
  visionBytes: number | null;
  corners: [number, number][];
  detectedQuad: [number, number][] | null;
  detectPending: boolean;
  quadSource: "default" | "detected" | "user" | "seeded";
  stage(file: File): Promise<void>;
  analyze(): Promise<void>;
  startSample(): Promise<void>;
  cancel(): void;
  toCrop(): void;
  setCorner(index: number, xy: [number, number]): void;
  resetToAuto(): void;
  backFromCrop(): void;
  openInEditor(): void;
  backToDropzone(): void;
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
