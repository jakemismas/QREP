// Types for wheel-hash.mjs, so src/wheel-stamp.test.ts type-checks under
// tsconfig.test.json without allowJs. Keep in step with the module's exports.

export declare const STAMP_FILE: "qrep-source-hash.json";

export declare function qrepSourceHash(repoRoot?: string): string;

export declare function writeWheelStamp(
  wheelsDir: string,
  wheel: string,
  sourceHash: string,
): { wheel: string; sourceHash: string };

/** Returns null for a fresh wheel, otherwise what is wrong with it. */
export declare function wheelStampProblem(wheelsDir: string, repoRoot?: string): string | null;

export declare function assertFreshWheel(
  wheelsDir: string,
  rebuildHint: string,
  repoRoot?: string,
): void;

export default function globalSetup(): void;
