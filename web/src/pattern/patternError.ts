/**
 * The one error line on Your pattern (C2a, issue #96), framework-free so
 * vitest covers the choice without a DOM. A failed engine boot leaves the
 * queued calls waiting forever, so a wait on it gets ENGINE_DOWN and a Retry
 * that reboots the engine; a failed call gets its sentence and a Retry of that
 * call, which restarts the engine first when the worker itself failed
 * (retryPattern in patternPdf.ts); a refusal shows its reason with no Retry,
 * because the same quilt is refused again. A failed fabric census shows last:
 * any other failure's Retry sends it again too. A census still waiting counts
 * as a wait: a census Retry that restarts the engine onto a boot that fails
 * leaves it queued, and the screen would otherwise show no line at all.
 */
import type { PdfView, RetryAction, SummaryView } from "./patternPdf";

export type { RetryAction } from "./patternPdf";

export const ENGINE_DOWN = "The pattern engine did not start, so your pattern is not ready yet.";
export const CENSUS_FAILED = "Your fabrics could not be counted this time. Try again.";

/** The fabric census on Your pattern: still to land, failed, or shown. */
export type CensusState = "waiting" | "failed" | "ready";

export interface PatternError {
  message: string;
  retry: RetryAction | null;
}

export function patternError(
  engineFailed: boolean,
  summary: SummaryView,
  pdf: PdfView,
  census: CensusState = "ready",
): PatternError | null {
  const waiting = summary.status === "loading" || pdf.status === "busy" || census === "waiting";
  if (engineFailed && waiting) return { message: ENGINE_DOWN, retry: "engine" };
  if (pdf.status === "failed" || pdf.status === "refused") {
    return { message: pdf.message ?? "", retry: pdf.status === "failed" ? "pdf" : null };
  }
  if (summary.status === "failed" || summary.status === "refused") {
    return { message: summary.message, retry: summary.status === "failed" ? "summary" : null };
  }
  if (census === "failed") return { message: CENSUS_FAILED, retry: "census" };
  return null;
}
