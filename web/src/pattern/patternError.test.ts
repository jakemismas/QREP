/**
 * The error line on Your pattern (C2a, issue #96): which sentence shows and
 * what its Retry runs. A refusal shows its reason with no Retry, because the
 * same quilt is refused again; a failure keeps its Retry.
 */
import { describe, expect, it } from "vitest";
import { patternError } from "./patternError";
import type { PdfView, SummaryView } from "./patternPdf";

// The sentences, written out here so a changed constant fails these tests.
const ENGINE_DOWN_SENTENCE = "The pattern engine did not start, so your pattern is not ready yet.";
const FAILED_SENTENCE = "Your pattern could not be made this time. Try again.";
const REFUSAL = "This quilt has too few squares to make a pattern.";

const IDLE_PDF: PdfView = { status: "idle", message: null };
const BUSY_PDF: PdfView = { status: "busy", message: null };
const LOADING: SummaryView = { status: "loading" };
const READY: SummaryView = {
  status: "ready",
  summary: {
    finished_width: 600,
    finished_height: 720,
    size_basis: null,
    method: "strip",
    method_reason: "Blocks repeat.",
    fabrics: [],
    binding: [],
    backing: { fabric_id: null, name: "Backing", yards: 5.5 },
    wide_back: null,
    batting: { width: 664, height: 784 },
    strip_width: 336,
    backing_width: 336,
    uncertain_squares: 0,
  },
};

describe("patternError", () => {
  it("asks for an engine Retry while a call waits on a failed boot", () => {
    expect(patternError(true, LOADING, IDLE_PDF)).toEqual({
      message: ENGINE_DOWN_SENTENCE,
      retry: "engine",
    });
    expect(patternError(true, READY, BUSY_PDF)).toEqual({
      message: ENGINE_DOWN_SENTENCE,
      retry: "engine",
    });
  });

  it("shows nothing while the engine boots or nothing waits on a failed one", () => {
    expect(patternError(false, LOADING, BUSY_PDF)).toBeNull();
    expect(patternError(true, READY, IDLE_PDF)).toBeNull();
  });

  it("keeps Retry for a failed call", () => {
    expect(patternError(false, READY, { status: "failed", message: FAILED_SENTENCE })).toEqual({
      message: FAILED_SENTENCE,
      retry: "pdf",
    });
    expect(patternError(false, { status: "failed", message: FAILED_SENTENCE }, IDLE_PDF)).toEqual({
      message: FAILED_SENTENCE,
      retry: "summary",
    });
  });

  it("shows a refusal's reason with no Retry", () => {
    expect(patternError(false, READY, { status: "refused", message: REFUSAL })).toEqual({
      message: REFUSAL,
      retry: null,
    });
    expect(patternError(false, { status: "refused", message: REFUSAL }, IDLE_PDF)).toEqual({
      message: REFUSAL,
      retry: null,
    });
  });
});
