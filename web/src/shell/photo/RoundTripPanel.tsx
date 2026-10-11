/*
 * Round-trip check (Pattern tab): render the design at level 0 or 2, reverse
 * the render, and compare the recovered quilt with the design. C6a removes
 * it with the editor.
 */
import { useState } from "react";
import { useRoundTrip } from "../../state/pattern";
import "./shared.css";
import "./RoundTripPanel.css";

export function RoundTripPanel() {
  const roundtrip = useRoundTrip();
  const [level, setLevel] = useState<0 | 2>(0);
  const [busy, setBusy] = useState(false);

  const report = roundtrip?.report ?? null;

  const run = async (): Promise<void> => {
    if (!roundtrip) return;
    setBusy(true);
    try {
      await roundtrip.run(level);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="pf-rt" data-testid="roundtrip-panel">
      <div className="pf-rt-head">
        <h3 className="pf-rt-title">Round-trip check</h3>
        <span className="pf-rt-rule" />
        <span className="pf-rt-pill">render then reverse</span>
      </div>
      <p className="pf-rt-lede">
        Render this design, reverse the render back, and compare, so you can see the pipeline agree
        with itself.
      </p>
      <div className="pf-rt-controls">
        <label className="pf-rt-field">
          <span className="pf-rt-field-label">Detail level</span>
          <select
            className="pf-rt-select"
            data-testid="roundtrip-level"
            value={level}
            onChange={(e) => setLevel(Number(e.target.value) === 2 ? 2 : 0)}
          >
            <option value={0}>Level 0, exact grid</option>
            <option value={2}>Level 2, textured</option>
          </select>
        </label>
        <button
          type="button"
          className="pf-btn pf-btn--secondary"
          data-testid="roundtrip-run"
          disabled={busy || !roundtrip}
          onClick={() => void run()}
        >
          {busy ? "Checking…" : "Run round-trip check"}
        </button>
      </div>
      {report ? (
        <div
          className={`pf-rt-report pf-rt-report--${report.dimsMatch ? "ok" : "bad"}`}
          data-testid="roundtrip-report"
        >
          <span className="pf-rt-report-line">
            Dimensions {report.dimsMatch ? "MATCH" : "MISMATCH"}
          </span>
          <span className="pf-rt-report-line">
            Square accuracy {(report.cellAccuracy * 100).toFixed(0)}% (
            {report.cellAccuracy.toFixed(4)})
          </span>
        </div>
      ) : null}
    </section>
  );
}
