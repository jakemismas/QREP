/**
 * Read-only fabric census panel (S2; revived for Your pattern in C2a, issue
 * #96). Each row shows the letter and name the pattern PDF prints, the
 * fabric's swatch and its square count; pattern/census.ts builds the rows.
 * Until the census lands a count shows a placeholder WITHOUT the test id, so
 * the e2e waits for the real census before asserting. No fabric id or color
 * code is ever shown as text. Swatch colors are user data and never theme.
 */

export interface CensusRow {
  fabricId: string;
  letter: string;
  name: string;
  color: string | null;
  count: number | null;
}

const FP_CSS = `
.fp-root { background: var(--card); border: 1px solid var(--line); border-radius: 16px; box-shadow: 0 2px 10px var(--shadow); padding: 18px; display: flex; flex-direction: column; gap: 6px; font: 400 16.5px var(--sans, sans-serif); color: var(--ink2); }
.fp-head { margin-bottom: 4px; }
.fp-title { margin: 0; font: 700 21px var(--serif, serif); color: var(--denim); }
.fp-list { list-style: none; margin: 0; padding: 0; }
.fp-row { display: flex; align-items: center; gap: 12px; padding: 12px 2px; border-bottom: 1px dashed var(--line); }
.fp-row:last-child { border-bottom: none; }
.fp-letter { flex: none; min-width: 30px; height: 30px; padding: 0 6px; display: inline-flex; align-items: center; justify-content: center; border-radius: 8px; background: var(--card2); border: 1.5px solid var(--line2); font: 700 15px var(--serif, serif); color: var(--ink); }
.fp-swatch { flex: none; width: 46px; height: 46px; border-radius: 10px; border: 1px solid var(--line2); box-shadow: inset 0 -2px 5px rgba(0, 0, 0, 0.07); }
.fp-info { min-width: 0; }
.fp-name { font: 600 16.5px var(--sans, sans-serif); color: var(--ink); overflow-wrap: anywhere; }
.fp-meta { font-size: 14px; color: var(--mut); margin-top: 2px; }
.fp-counting { font-style: italic; color: var(--faint); }
`;

export function FabricsPanel({ rows }: { rows: CensusRow[] }) {
  return (
    <section className="fp-root" data-testid="fabric-census">
      <header className="fp-head">
        <h2 className="fp-title">Fabrics</h2>
      </header>
      <ul className="fp-list">
        {rows.map((row) => (
          <li className="fp-row" key={row.fabricId}>
            <span className="fp-letter" data-testid={`fabric-letter-${row.fabricId}`}>
              {row.letter}
            </span>
            <span
              className="fp-swatch"
              style={{ background: row.color ?? "transparent" }}
              aria-hidden="true"
            />
            <div className="fp-info">
              <div className="fp-name">{row.name}</div>
              <div className="fp-meta">
                {row.count != null ? (
                  <span className="fp-count" data-testid={`fabric-count-${row.fabricId}`}>
                    {row.count.toLocaleString("en-US")} squares
                  </span>
                ) : (
                  <span className="fp-count fp-counting">counting squares…</span>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>
      <style>{FP_CSS}</style>
    </section>
  );
}
