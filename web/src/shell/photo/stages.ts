/*
 * The six analysis stages and their confidence words, shared by the progress
 * and results screens so both read the same stage list.
 */

export type Tone = "sage" | "amber" | "accent";

// Engine stage key -> UI stage key + display label (1:1 with the pipeline's
// provenance.stage_confidence). rectify/palette/cells/repeat/border read as
// straighten/colors/squares/repeats/borders.
export const STAGES: { ui: string; engine: string; label: string }[] = [
  { ui: "straighten", engine: "rectify", label: "Straighten" },
  { ui: "colors", engine: "palette", label: "Fabric colors" },
  { ui: "grid", engine: "grid", label: "Grid" },
  { ui: "squares", engine: "cells", label: "Squares" },
  { ui: "repeats", engine: "repeat", label: "Repeats" },
  { ui: "borders", engine: "border", label: "Borders" },
];

export function stageConf(sc: Record<string, number>, stage: { ui: string; engine: string }): number {
  const value = sc[stage.engine] ?? sc[stage.ui];
  return typeof value === "number" ? value : 0;
}

export function confWord(conf: number): { word: string; tone: Tone } {
  if (conf >= 0.95) return { word: "Very sure", tone: "sage" };
  if (conf >= 0.85) return { word: "Solid", tone: "sage" };
  if (conf >= 0.8) return { word: "Good", tone: "amber" };
  return { word: "Check it", tone: "accent" };
}
