/**
 * Read-only fabric census panel (S2). Rows come from the model palette; the
 * per-fabric square counts come from bridge summary data. Until the summary
 * lands the count shows a placeholder WITHOUT the test id, so the e2e waits
 * for the real census before asserting. Swatch colors are user data and
 * never theme.
 */
import type { ModelSummary, QuiltModel } from "../model/types";
import { formatEighths } from "../model/units";

const FP_CSS = `
.fp-root { background: var(--card); border: 1px solid var(--line); border-radius: 16px; box-shadow: 0 2px 10px var(--shadow); padding: 18px; display: flex; flex-direction: column; gap: 6px; font: 400 16.5px var(--sans, sans-serif); color: var(--ink2); }
.fp-head { margin-bottom: 4px; }
.fp-title { margin: 0; font: 700 21px var(--serif, serif); color: var(--denim); }
.fp-list { list-style: none; margin: 0; padding: 0; }
.fp-row { display: flex; align-items: center; gap: 12px; padding: 12px 2px; border-bottom: 1px dashed var(--line); }
.fp-row:last-child { border-bottom: none; }
.fp-swatch { flex: none; width: 46px; height: 46px; border-radius: 10px; border: 1px solid var(--line2); box-shadow: inset 0 -2px 5px rgba(0, 0, 0, 0.07); }
.fp-info { min-width: 0; }
.fp-name { font: 600 16.5px var(--sans, sans-serif); color: var(--ink); }
.fp-meta { font-size: 14px; color: var(--mut); margin-top: 2px; }
.fp-hex { font-variant-numeric: tabular-nums; letter-spacing: 0.02em; }
.fp-counting { font-style: italic; color: var(--faint); }
.fp-summary { margin: 8px 0 0; padding-top: 10px; border-top: 1px dashed var(--line); display: flex; flex-direction: column; gap: 6px; }
.fp-sumrow { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.fp-sumrow dt { font-size: 14px; color: var(--mut); }
.fp-sumrow dd { margin: 0; font: 600 16px var(--serif, serif); color: var(--ink); }
`;

export function FabricsPanel({ model, summary }: { model: QuiltModel; summary: ModelSummary | null }) {
  const borderFabricIds = new Set(model.borders.map((b) => b.fabric_id));
  const countById = new Map((summary?.fabrics ?? []).map((f) => [f.id, f.cell_count]));

  return (
    <section className="fp-root">
      <header className="fp-head">
        <h2 className="fp-title">Fabrics</h2>
      </header>
      <ul className="fp-list">
        {model.palette.fabrics.map((f) => {
          const count = countById.get(f.id);
          const inBorders = borderFabricIds.has(f.id);
          return (
            <li className="fp-row" key={f.id}>
              <span className="fp-swatch" style={{ background: f.color }} aria-hidden="true" />
              <div className="fp-info">
                <div className="fp-name">{f.name}</div>
                <div className="fp-meta">
                  <span className="fp-hex">{f.color.toUpperCase()}</span>
                  <span> · </span>
                  {count != null ? (
                    <span className="fp-count" data-testid={`fabric-count-${f.id}`}>
                      {count.toLocaleString("en-US")} squares{inBorders ? " + borders" : ""}
                    </span>
                  ) : (
                    <span className="fp-count fp-counting">counting squares…</span>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
      {summary && (
        <dl className="fp-summary">
          <div className="fp-sumrow">
            <dt>Finished size</dt>
            <dd>
              {formatEighths(summary.finished_width)} × {formatEighths(summary.finished_height)}
            </dd>
          </div>
          <div className="fp-sumrow">
            <dt>Batting needed</dt>
            <dd>
              {formatEighths(summary.batting_width)} × {formatEighths(summary.batting_height)}
            </dd>
          </div>
        </dl>
      )}
      <style>{FP_CSS}</style>
    </section>
  );
}
