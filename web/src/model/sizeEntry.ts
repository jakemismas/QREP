/**
 * S7 size-entry state machine (sprint 3, issue #73; UI-SPEC section 2).
 *
 * Pure state, no React: the SizeBlock component renders it, the provider
 * reads sizeOptions() at analyze/apply time. The honesty rules are
 * structural, mirroring the S2 corners-passing precedent:
 * - a SUGGESTION prefills empty inputs for display only; an untouched
 *   suggestion ships as guess (sizeOptions() returns null);
 * - provenance user attaches only on an explicit gesture (chip tap or an
 *   edited input);
 * - cm converts AT ENTRY via the pinned rule eighths = round(cm*8/2.54);
 *   the model stays integer eighths everywhere.
 */
import { parseFractionInput } from "./fraction";
import { PRESETS } from "./sizing";

export type SizeSource = "none" | "suggested" | "user";
export type SizeUnit = "in" | "cm";

/** The pinned conversion (approval record): eighths = round(cm * 8 / 2.54). */
export function cmToEighths(cm: number): number {
  return Math.round((cm * 8) / 2.54);
}

/** One-decimal cm equivalent of an eighths length (display only). */
export function formatCmEquivalent(eighths: number): string {
  return (Math.round((eighths / 8) * 2.54 * 10) / 10).toFixed(1);
}

function presetByName(name: string): { width: number; height: number } | null {
  const hit = PRESETS.find((p) => p.name === name);
  return hit ? { width: hit.width, height: hit.height } : null;
}

export class SizeEntryState {
  widthEighths: number | null = null;
  heightEighths: number | null = null;
  source: SizeSource = "none";
  unit: SizeUnit = "in";
  enteredInCm = false;
  suggestedPreset: string | null = null;

  /** Parse and store one input; returns false (state unchanged) on junk. */
  editInput(which: "width" | "height", text: string): boolean {
    const eighths = this.parse(text);
    if (eighths === null || eighths <= 0) return false;
    if (which === "width") this.widthEighths = eighths;
    else this.heightEighths = eighths;
    this.source = "user";
    if (this.unit === "cm") this.enteredInCm = true;
    return true;
  }

  /** A chip tap is an explicit user gesture: both dims from the preset. */
  tapChip(name: string): void {
    const preset = presetByName(name);
    if (!preset) return;
    this.widthEighths = preset.width;
    this.heightEighths = preset.height;
    this.source = "user";
    this.enteredInCm = false;
  }

  /** Detection suggested a preset: highlight it, prefill ONLY empty inputs
   * for display, never claim user provenance. */
  suggest(name: string | null): void {
    this.suggestedPreset = name;
    if (name === null) return;
    const preset = presetByName(name);
    if (!preset) return;
    if (this.source === "none") {
      this.widthEighths = preset.width;
      this.heightEighths = preset.height;
      this.source = "suggested";
    }
  }

  toggleUnit(): void {
    this.unit = this.unit === "in" ? "cm" : "in";
  }

  /** The engine payload: dims ride ONLY on explicit user provenance. */
  sizeOptions(): { finished_width: number | null; finished_height: number | null } | null {
    if (this.source !== "user") return null;
    if (this.widthEighths === null && this.heightEighths === null) return null;
    return { finished_width: this.widthEighths, finished_height: this.heightEighths };
  }

  reset(): void {
    this.widthEighths = null;
    this.heightEighths = null;
    this.source = "none";
    this.enteredInCm = false;
    this.suggestedPreset = null;
  }

  private parse(text: string): number | null {
    const trimmed = text.trim();
    if (!trimmed) return null;
    if (this.unit === "cm") {
      const value = Number(trimmed.replace(",", "."));
      return Number.isFinite(value) && value > 0 ? cmToEighths(value) : null;
    }
    return parseFractionInput(trimmed);
  }
}
