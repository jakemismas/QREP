/**
 * Flagged squares on Your pattern (C2a, issue #96). The count is the read's
 * own (PhotoResult.uncertainCount), and the outlines QuiltCanvas draws come
 * from the read's cell confidences, never from the editor's model. A sample
 * pattern has no read, so the screen shows no flagged line for it.
 */
import "./FlaggedOverlay.css";

export function FlaggedOverlay({
  count,
  shown,
  onToggle,
}: {
  count: number;
  shown: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="fo-root" data-testid="flagged-count" data-count={count}>
      {count === 0 ? (
        <p className="fo-line">No squares were flagged to double-check.</p>
      ) : (
        <>
          <p className="fo-line">
            <span className="fo-mark" aria-hidden="true" />
            {count.toLocaleString("en-US")} {count === 1 ? "square is" : "squares are"} flagged
            to double-check against your photo.
          </p>
          <button
            type="button"
            className="btn btn--link fo-toggle"
            data-testid="flagged-toggle"
            aria-pressed={shown}
            onClick={onToggle}
          >
            {shown ? "Hide the outlines" : "Show the outlines"}
          </button>
        </>
      )}
    </div>
  );
}
