/**
 * Engine status chip (S2). Renders the four EngineClient phases as one pill.
 * The failed state has no mock (grep-confirmed); it extends the DS idiom with
 * an accent dot + message + retry, matching the pill anatomy.
 *
 * Contract: outer element carries data-testid="engine-chip" and
 * data-engine-phase; the retry button (data-testid="engine-retry") renders
 * only when failed.
 */
import type { EngineStatus } from "../engine/rpc";

function BootSpinner() {
  return (
    <svg
      className="q-chip__spin"
      width="13"
      height="13"
      viewBox="0 0 13 13"
      fill="none"
      aria-hidden="true"
    >
      <circle
        cx="6.5"
        cy="6.5"
        r="5"
        stroke="var(--denim)"
        strokeWidth="2.4"
        strokeDasharray="22 10"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function EngineChip({
  status,
  onRetry,
}: {
  status: EngineStatus;
  onRetry: () => void;
}) {
  return (
    <span
      className={status.phase === "failed" ? "q-chip q-chip--failed" : "q-chip"}
      data-testid="engine-chip"
      data-engine-phase={status.phase}
    >
      {status.phase === "booting" && (
        <>
          <BootSpinner />
          <span className="q-chip__label">{status.step}</span>
        </>
      )}
      {status.phase === "ready" && (
        <>
          <span className="q-chip__dot q-chip__dot--sage" />
          <span className="q-chip__label">Engine ready</span>
        </>
      )}
      {status.phase === "busy" && (
        <>
          <span className="q-chip__dot q-chip__dot--amber" />
          <span className="q-chip__label">Engine busy</span>
        </>
      )}
      {status.phase === "failed" && (
        <>
          <span className="q-chip__dot q-chip__dot--accent" />
          <span className="q-chip__label">{status.message}</span>
          <button
            type="button"
            className="q-chip__retry"
            data-testid="engine-retry"
            onClick={onRetry}
          >
            Retry
          </button>
        </>
      )}
    </span>
  );
}
