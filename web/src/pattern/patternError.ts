/**
 * The one error line on Your pattern (C2a, issue #96), framework-free so
 * vitest covers the choice without a DOM. A failed engine boot leaves the
 * queued calls waiting forever, so a wait on it gets ENGINE_DOWN and a Retry
 * that reboots the engine; a failed call gets its sentence and a Retry of that
 * call; a refusal shows its reason with no Retry, because the same quilt is
 * refused again.
 */
import type { PdfView, SummaryView } from "./patternPdf";

export const ENGINE_DOWN = "The pattern engine did not start, so your pattern is not ready yet.";

/** What Retry runs: reboot the engine, or one call again. */
export type RetryAction = "engine" | "pdf" | "summary";

export interface PatternError {
  message: string;
  retry: RetryAction | null;
}

export function patternError(
  engineFailed: boolean,
  summary: SummaryView,
  pdf: PdfView,
): PatternError | null {
  const waiting = summary.status === "loading" || pdf.status === "busy";
  if (engineFailed && waiting) return { message: ENGINE_DOWN, retry: "engine" };
  if (pdf.status === "failed" || pdf.status === "refused") {
    return { message: pdf.message ?? "", retry: pdf.status === "failed" ? "pdf" : null };
  }
  if (summary.status === "failed" || summary.status === "refused") {
    return { message: summary.message, retry: summary.status === "failed" ? "summary" : null };
  }
  return null;
}
