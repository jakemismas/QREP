/**
 * The method in one line (C2a, issue #96): the engine's one-sentence reason
 * only. The method id, strategy cards and plan metrics never show (SPEC.md
 * section 2.5). While the summary loads, a short working line stands in,
 * unless the engine is down and the load waits on Retry (working false); a
 * failure or refusal shows in the screen's error line instead.
 */
import type { SummaryView } from "./patternPdf";
import "./MethodLine.css";

export function MethodLine({ summary, working }: { summary: SummaryView; working: boolean }) {
  if (summary.status === "ready") {
    return (
      <p className="ml-line" data-testid="method-line">
        {summary.summary.method_reason}
      </p>
    );
  }
  if (summary.status === "failed" || summary.status === "refused" || !working) return null;
  return (
    <p className="ml-line ml-line--working" data-testid="pattern-working" role="status">
      <span className="ml-spin" aria-hidden="true" />
      Working out your pattern…
    </p>
  );
}
