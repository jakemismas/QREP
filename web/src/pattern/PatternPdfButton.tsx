/**
 * The one pattern action on Your pattern (C2a, issue #96). The controller
 * behind onSave ignores presses while a pattern is being made, so the button
 * stays focusable and announces the busy state instead of going disabled.
 */
import type { PdfView } from "./patternPdf";
import "./PatternPdfButton.css";

const LABEL = "Download pattern (PDF)";
const BUSY_LABEL = "Making your pattern…";

export function PatternPdfButton({ pdf, onSave }: { pdf: PdfView; onSave: () => void }) {
  const busy = pdf.status === "busy";
  return (
    <button
      type="button"
      className="btn btn--primary pb-button"
      data-testid="download-pattern"
      data-state={pdf.status}
      aria-busy={busy}
      onClick={onSave}
    >
      {busy ? <span className="pb-spin" aria-hidden="true" /> : null}
      {busy ? BUSY_LABEL : LABEL}
    </button>
  );
}
