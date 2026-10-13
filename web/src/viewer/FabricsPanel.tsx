/**
 * Read-only fabric census panel (S2; revived for Your pattern in C2a, issue
 * #96). Each row shows the letter and name the pattern PDF prints, the
 * fabric's swatch and its square count; pattern/census.ts builds the rows.
 * Until the census lands a count shows a placeholder WITHOUT the test id, so
 * the e2e waits for the real census before asserting; a failed census says
 * so instead, while Your pattern's error line offers the Retry. The letter is
 * the engine's letter field, which is still the fabric id until A4b (#123);
 * no color code is shown as text. Swatch colors are user data and never theme.
 */
// The fp- rules live in pattern/FabricCensus.css, imported by FabricCensus, this
// panel's one user: plan section 5.C bans injected style strings.

export interface CensusRow {
  fabricId: string;
  letter: string;
  name: string;
  color: string | null;
  count: number | null;
}

export function FabricsPanel({ rows, countFailed = false }: { rows: CensusRow[]; countFailed?: boolean }) {
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
                  <span className="fp-count fp-counting">
                    {countFailed ? "not counted" : "counting squares…"}
                  </span>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
