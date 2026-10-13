/**
 * The shopping lines on Your pattern (C2b, issue #148): the binding, backing,
 * wide-back and batting lines of the export_pattern summary, the data the
 * PDF prints (PS-40). Each line shows the engine's own name and amount, so
 * the screen computes no yardage, backing or batting number (criterion P13;
 * MATH.md D-15). The wide-back line shows only when the engine returns one
 * (MATH.md F11), and the closing line names both width assumptions from the
 * summary (MATH.md D-16).
 */
import type { PatternSummary, PurchaseLine } from "../engine/contract";
import { inchText, sizeText, yardsText } from "./patternSize";
import "./ShoppingLines.css";

function Line({ testId, line }: { testId: string; line: PurchaseLine }) {
  return (
    <li className="sl-row" data-testid={testId} data-yards={line.yards}>
      <span className="sl-name">{line.name}</span>
      <span className="sl-amount">{yardsText(line.yards)}</span>
    </li>
  );
}

export function ShoppingLines({ summary }: { summary: PatternSummary }) {
  return (
    <section className="sl-root" data-testid="shopping-lines">
      <h2 className="sl-title">Binding, backing and batting</h2>
      <ul className="sl-list">
        {summary.binding.map((line) => (
          <Line key={line.fabric_id ?? line.name} testId="shop-binding" line={line} />
        ))}
        <Line testId="shop-backing" line={summary.backing} />
        {summary.wide_back !== null ? (
          <Line testId="shop-wide-back" line={summary.wide_back} />
        ) : null}
        <li className="sl-row" data-testid="shop-batting">
          <span className="sl-name">Batting</span>
          <span className="sl-amount">
            {sizeText(summary.batting.width, summary.batting.height)}
          </span>
        </li>
      </ul>
      <p className="sl-widths" data-testid="shop-widths">
        {`Cutting amounts assume strips at ${inchText(summary.strip_width)} of usable fabric ` +
          `width. The backing assumes fabric ${inchText(summary.backing_width)} wide.`}
      </p>
    </section>
  );
}
