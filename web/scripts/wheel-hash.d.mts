// Types for the wheel-hash.mjs helpers that src/wheel-stamp.test.ts imports,
// so the test type-checks under tsconfig.test.json without allowJs. Declare
// another export here only when a TypeScript file starts importing it.

export declare function qrepSourceHash(repoRoot?: string): string;

export declare function writeWheelStamp(
  wheelsDir: string,
  wheel: string,
  sourceHash: string,
): { wheel: string; sourceHash: string };

/** Returns null for a fresh wheel, otherwise what is wrong with it. */
export declare function wheelStampProblem(wheelsDir: string, repoRoot?: string): string | null;
