/**
 * S8 verdict story (sprint 3, issue #74; UI-SPEC sections 3-5).
 *
 * Pure mapping from a PhotoResult to the structure Results and Progress
 * render 1:1: honest failure copy, disclosure/banner semantics, the pill
 * failure tier that DROPS the percentage, period phrasing (inches only
 * when user-sized; ASSUMED_PPI never converts a period), and the
 * progress-row dash set.
 *
 * PALETTE GATE (frozen at write time, calibrated on the S0 fidelity
 * evidence recorded on #74): startBlankWithPalette requires palette
 * confidence >= 0.80 AND 2 <= k <= 6. The two junk populations are killed
 * structurally: solid-fabric phantoms by the k ceiling (k=8 at conf 0.89),
 * lighting-split palettes by the floor (conf 0.64). Plausible-color
 * averages (busy prints) pass - a recolorable blank start tolerates that.
 */
import type { PhotoResult } from "../shell/photoApi";
import { formatEighths } from "./units";

export const PALETTE_TRUST_MIN = 0.8;
export const PALETTE_K_MIN = 2;
export const PALETTE_K_MAX = 6;

export const UI_STAGES = [
  "straighten",
  "colors",
  "grid",
  "squares",
  "repeats",
  "borders",
] as const;

export interface VerdictStory {
  pill: { mode: "percent" | "failure" | "nonsquare"; text: string };
  failurePanel: { title: string; reason: string } | null;
  infoPanel: { title: string; period: string | null; sizeInvite: boolean } | null;
  caption: string | null;
  disclosure: { label: string; banner: string } | null;
  dashedStages: string[];
}

const REASONS: Record<string, string> = {
  no_quilt_found: "We could not tell the quilt apart from the background.",
  no_periodicity: "We did not find any repeating structure to read.",
  profile_too_short: "The photo is too small to read squares from.",
  anisotropic_pitch:
    "The rows and columns disagree - the photo may show the quilt at a steep angle.",
  implausible_dims: "The grid we found is not a plausible quilt.",
  weak_periodicity: "The square pattern is too faint to read confidently.",
  // S2 (#94): a coarse block lattice IS present, but the shapes inside are not
  // squares (curves or triangles). This replaces the wrong steep-angle message
  // on frontal curved quilts - the pipeline emits anisotropic_pitch only on
  // genuine skew now, and non_square_content when it found repeating blocks.
  non_square_content:
    "The blocks repeat, but the shapes inside are not squares - QREP can only recover square patchwork, not curves or triangles yet.",
};

function periodPhrase(
  diagnostics: Record<string, unknown> | undefined,
  grid: { cols: number; cellSize: number },
): { text: string | null; sized: boolean } {
  const sized = diagnostics?.["size_source"] === "user";
  const block = diagnostics?.["block_period_cells"] as [number, number] | null | undefined;
  const cells = block?.[0] ?? null;
  if (!cells || cells < 1) return { text: null, sized };
  if (sized) {
    // inches only when a user size exists: cells x cell_size (eighths).
    // The shared formatter emits an inch mark; this copy spells "in."
    // (UI-SPEC section 3), so drop the mark and keep the fraction body.
    const length = formatEighths(cells * grid.cellSize).replace(/"$/, "");
    return { text: `It repeats every ${length} in.`, sized };
  }
  const across = Math.floor(grid.cols / cells);
  if (across < 2) return { text: null, sized };
  return { text: `It repeats about ${across} times across its width.`, sized };
}

export function verdictStory(
  result: PhotoResult,
  grid: { cols: number; rows: number; cellSize: number },
): VerdictStory {
  const verdict = (result.verdict as string | undefined) ?? "readable";
  const diagnostics = result.diagnostics as Record<string, unknown> | undefined;
  const diagnosis = (diagnostics?.["grid_diagnosis"] as string | null | undefined) ?? null;

  if (verdict === "no_grid") {
    const failFromRectify = diagnosis === "no_quilt_found";
    const dashedFrom = failFromRectify ? 0 : 2; // straighten... vs grid...
    return {
      pill: { mode: "failure", text: "Could not read this photo" },
      failurePanel: {
        title: "We could not find a square grid in this photo",
        reason: REASONS[diagnosis ?? ""] ?? "The pattern did not read as a grid of squares.",
      },
      infoPanel: null,
      caption: null,
      disclosure: {
        label: "Show what we saw anyway",
        banner: "This reading is wrong - shown only to help you see what went wrong.",
      },
      dashedStages: UI_STAGES.slice(dashedFrom) as unknown as string[],
    };
  }

  if (verdict === "non_square_repeat") {
    const period = periodPhrase(diagnostics, grid);
    return {
      pill: { mode: "nonsquare", text: "blocks repeat - squares uncertain" },
      failurePanel: null,
      infoPanel: {
        // softened shape claim: edge energy cannot fully distinguish
        // piecing from busy prints
        title:
          "This quilt's blocks repeat, but they may use shapes QREP cannot read yet (triangles and curves)",
        period: period.text,
        sizeInvite: !period.sized,
      },
      caption: null,
      disclosure: {
        label: "Show the squares approximation",
        banner: "This is an approximation - the real blocks are not squares.",
      },
      dashedStages: [],
    };
  }

  if (verdict === "readable_no_repeat") {
    return {
      pill: { mode: "percent", text: "" },
      failurePanel: null,
      infoPanel: null,
      caption: "No repeating block found - common for samplers and medallion quilts.",
      disclosure: null,
      dashedStages: [],
    };
  }

  // readable (or a pre-S4 result with no verdict)
  const period = periodPhrase(diagnostics, grid);
  return {
    pill: { mode: "percent", text: "" },
    failurePanel: null,
    infoPanel: null,
    caption: period.text,
    disclosure: null,
    dashedStages: [],
  };
}

/** startBlankWithPalette gate: see the module docstring for calibration. */
export function paletteGate(paletteConfidence: number, k: number): boolean {
  return paletteConfidence >= PALETTE_TRUST_MIN && k >= PALETTE_K_MIN && k <= PALETTE_K_MAX;
}
