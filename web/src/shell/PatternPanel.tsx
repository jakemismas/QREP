/**
 * Pattern panel (S5, issue #45; PARITY items 1, 2, 9, 11, 12). Three strategy
 * cards whose metrics come VERBATIM from bridge plan output (no JS arithmetic
 * on metrics), a hand-tweaked badge with clearly-labeled seam estimates, the
 * yardage table (fabric/binding/backing from bridge lines + a UI-derived
 * batting row), the five engine downloads plus print, and copy-my-settings.
 * A hidden print sheet renders here and is revealed only by @media print.
 *
 * Squares, never cells. Styling is design-tokens only; swatch colors are the
 * user's fabric data.
 */
import { useState } from "react";
import { useProject } from "../state/project";
import type { ExportKind } from "../state/project";
import type { SeamStrategy } from "../model/seams";
import { formatEighths } from "../model/units";
import { useToast } from "../ui";
import { battingQuarterYards, formatQuarterYards } from "../state/patternText";

const STRAT_CARDS: { k: SeamStrategy; title: string; blurb: string }[] = [
  {
    k: "historical",
    title: "Historical",
    blurb:
      "Every square cut and sewn one at a time, the way the original was likely made. Most control.",
  },
  {
    k: "strip",
    title: "Strip piecing",
    blurb:
      "Sew long strips first, then crosscut whole rows at once. The classic shortcut for repeating patterns.",
  },
  {
    k: "modern",
    title: "Modern optimized",
    blurb:
      "Merges same-color neighbors into bigger patches. Fewest seams for painted, irregular quilts.",
  },
];

const DL_BTNS: { kind: ExportKind; testid: string; label: string; sub: string }[] = [
  { kind: "pdf", testid: "download-pdf", label: "Pattern booklet · PDF", sub: "multi-page, ready to sew" },
  { kind: "cutlist-csv", testid: "download-cutlist-csv", label: "Cut list · CSV", sub: "for spreadsheets" },
  { kind: "cutlist-md", testid: "download-cutlist-md", label: "Cut list · Markdown", sub: "plain text" },
  { kind: "yardage", testid: "download-yardage", label: "Yardage report", sub: "shopping list" },
  { kind: "svg", testid: "download-svg", label: "SVG diagram", sub: "vector of the quilt" },
];

const countFmt = (n: number): string => n.toLocaleString("en-US");
const pctFmt = (x: number): string =>
  new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 0 }).format(x);

const PP_CSS = `
.pp-root { display: flex; flex-direction: column; gap: 10px; }
.pp-head { display: flex; align-items: center; gap: 12px; margin-bottom: 2px; }
.pp-title { margin: 0; font: 700 21px var(--serif, serif); color: var(--denim); }
.pp-sub-title { margin: 0; font: 700 17.5px var(--serif, serif); color: var(--denim); }
.pp-rule { flex: 1; border-top: 2px dashed var(--line2); }
.pp-pill { font-size: 12.5px; color: var(--mut); border: 1px solid var(--pillLn); border-radius: 999px; padding: 3px 10px; background: var(--pill); }
.pp-cards { display: flex; flex-direction: column; gap: 9px; }
.pp-card { text-align: left; width: 100%; padding: 13px 14px; border-radius: 13px; cursor: pointer; background: var(--card); border: 2px solid var(--line); display: flex; flex-direction: column; gap: 5px; }
.pp-card--selected { background: var(--card3); border-color: var(--accent); }
.pp-card-head { display: flex; align-items: center; gap: 9px; }
.pp-radio { width: 14px; height: 14px; border-radius: 50%; flex: none; border: 2px solid var(--line2); background: var(--card); }
.pp-card--selected .pp-radio { border: 1px solid var(--accent); background: var(--accent); box-shadow: inset 0 0 0 3px var(--card); }
.pp-card-title { font: 700 16.5px var(--sans, sans-serif); color: var(--ink); }
.pp-badge { margin-left: auto; font-size: 11.5px; font-weight: 700; color: var(--accentInk); background: var(--accent); border-radius: 999px; padding: 2px 9px; }
.pp-card-blurb { font-size: 13.5px; color: var(--mut); line-height: 1.45; }
.pp-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px 6px; margin-top: 4px; }
.pp-stat { display: flex; flex-direction: column; gap: 1px; }
.pp-stat-label { font-size: 11px; color: var(--faint); text-transform: uppercase; letter-spacing: .08em; }
.pp-stat-value { font: 700 15px var(--serif, serif); color: var(--ink2); }
.pp-stat-note { font-size: 10.5px; font-style: italic; color: var(--faint); }
.pp-estimate { margin-top: 6px; font-size: 12.5px; color: var(--ink2); background: var(--sageBg); border: 1px solid var(--sageLn); border-radius: 8px; padding: 6px 9px; }
.pp-hint { font-size: 12.5px; color: var(--faint); line-height: 1.5; }
.pp-table { width: 100%; border-collapse: collapse; }
.pp-tr td { padding: 9px 6px; border-bottom: 1px dashed var(--line); vertical-align: top; }
.pp-name { display: flex; align-items: center; gap: 9px; font-weight: 600; font-size: 14.5px; color: var(--ink); white-space: nowrap; }
.pp-swatch { width: 22px; height: 22px; border-radius: 6px; border: 1px solid var(--line2); flex: none; }
.pp-detail { font-size: 12.5px; color: var(--mut); line-height: 1.4; }
.pp-buy { text-align: right; font: 700 14.5px var(--serif, serif); color: var(--ink); white-space: nowrap; }
.pp-sub { font-size: 11px; font-style: italic; color: var(--faint); }
.pp-foot { margin: 4px 0 0; font-size: 12.5px; color: var(--faint); line-height: 1.5; }
.pp-dl-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; }
.pp-dl { text-align: left; padding: 11px 13px; border-radius: 11px; cursor: pointer; background: var(--card); border: 1.5px solid var(--line2); color: var(--ink2); }
.pp-dl:hover:not(:disabled) { background: var(--card2); }
.pp-dl:disabled { opacity: 0.75; cursor: wait; }
.pp-dl-label { display: block; font-weight: 600; font-size: 14.5px; }
.pp-dl-sub { display: block; font-size: 12px; color: var(--faint); margin-top: 2px; }
.pp-dl-busy { display: flex; align-items: center; gap: 8px; justify-content: center; font-weight: 600; font-size: 14.5px; }
.pp-spinner { width: 14px; height: 14px; border-radius: 50%; border: 2.4px solid var(--line2); border-top-color: var(--accent); animation: qSpin .8s linear infinite; }
.pp-copy { width: 100%; margin-top: 4px; padding: 14px; font: 600 16px var(--sans, sans-serif); background: var(--accent); color: var(--accentInk); border: none; border-radius: 12px; cursor: pointer; box-shadow: 0 4px 12px var(--shadow); }
.pp-copy--done { background: var(--sage); }
.pp-print-sheet { display: none; }
@media print {
  body { visibility: hidden !important; }
  .pp-print-sheet, .pp-print-sheet * { visibility: visible !important; }
  .pp-print-sheet { display: block !important; position: absolute; left: 0; top: 0; width: 100%; padding: 24px; font-family: var(--sans, sans-serif); color: #3b3020; }
}
.pp-ps-head { display: flex; justify-content: space-between; align-items: baseline; gap: 16px; border-bottom: 2.5px solid #3b3020; padding-bottom: 10px; }
.pp-ps-title { font: 700 24px var(--serif, serif); }
.pp-ps-meta { font-size: 13px; color: #6d5f49; }
.pp-ps-size { font: 700 26px var(--serif, serif); padding: 12px 0 4px; }
.pp-ps-facts { display: flex; gap: 8px 24px; flex-wrap: wrap; font-size: 14px; color: #4a3f2d; padding-bottom: 8px; }
.pp-ps-note { font-size: 12.5px; color: #6d5f49; padding-bottom: 12px; }
.pp-ps-list-head { font-size: 12.5px; letter-spacing: .14em; text-transform: uppercase; color: #8a7a61; font-weight: 700; padding-bottom: 4px; border-bottom: 1.5px solid #3b3020; }
.pp-ps-row { display: flex; justify-content: space-between; gap: 16px; padding: 8px 0; border-bottom: 1px solid #ddd2ba; font-size: 14px; }
`;

function Metric({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <span className="pp-stat">
      <span className="pp-stat-label">{label}</span>
      <span className="pp-stat-value">{value}</span>
      {note ? <span className="pp-stat-note">{note}</span> : null}
    </span>
  );
}

export function PatternPanel() {
  const {
    model,
    name,
    summary,
    seamStrategy,
    selectStrategy,
    handTweaked,
    estimates,
    plans,
    exportDownload,
    copySettings,
  } = useProject();
  const toast = useToast();
  const [busy, setBusy] = useState<ExportKind | null>(null);
  const [copied, setCopied] = useState(false);

  if (!model) return null;

  const bandTotal = model.borders.reduce((s, b) => s + b.width, 0);
  const finishedW = model.center.cols * model.center.cell_size + 2 * bandTotal;
  const finishedH = model.center.rows * model.center.cell_size + 2 * bandTotal;
  const finishedSize = `${formatEighths(finishedW)} × ${formatEighths(finishedH)}`;
  const stratTitle = STRAT_CARDS.find((c) => c.k === seamStrategy)?.title ?? "";
  const borderText = model.borders.map((b) => formatEighths(b.width)).join(" + ");

  const colorById = new Map(model.palette.fabrics.map((f) => [f.id, f.color]));
  const squaresById = new Map((summary?.fabrics ?? []).map((f) => [f.id, f.cell_count]));

  const yardage = plans[seamStrategy]?.yardage;
  const topLines = yardage?.lines.filter((l) => l.purpose === "top") ?? [];
  const bindingLine = yardage?.lines.find((l) => l.purpose === "binding");
  const backingLine = yardage?.lines.find((l) => l.purpose === "backing");

  const wof =
    model.settings && typeof model.settings.wof === "number" ? model.settings.wof : undefined;
  const usableEighths = summary?.usable_width ?? wof;

  const onExport = async (kind: ExportKind): Promise<void> => {
    setBusy(kind);
    try {
      await exportDownload(kind);
    } finally {
      setBusy(null);
    }
  };
  const onCopy = async (): Promise<void> => {
    const ok = await copySettings();
    if (ok) {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2600);
    }
  };
  const onPrint = (): void => {
    toast.push("Print dialog opened — your one-page plan is ready.", "success");
    window.print();
  };

  return (
    <section className="pp-root" data-testid="pattern-panel">
      <div className="pp-head">
        <h2 className="pp-title">Pattern</h2>
        <span className="pp-rule" />
        <span className="pp-pill">how to sew it</span>
      </div>

      <div className="pp-cards">
        {STRAT_CARDS.map(({ k, title, blurb }) => {
          const selected = seamStrategy === k;
          const m = plans[k]?.plan.metrics;
          return (
            <button
              key={k}
              type="button"
              data-testid={`strategy-card-${k}`}
              data-selected={selected || undefined}
              className={`pp-card${selected ? " pp-card--selected" : ""}`}
              onClick={() => selectStrategy(k)}
            >
              <span className="pp-card-head">
                <span className="pp-radio" aria-hidden="true" />
                <span className="pp-card-title">{title}</span>
                {selected && handTweaked ? (
                  <span data-testid="hand-tweaked" className="pp-badge">
                    hand-tweaked
                  </span>
                ) : null}
              </span>
              <span className="pp-card-blurb">{blurb}</span>
              <span className="pp-stats">
                <Metric label="Pieces" value={m ? countFmt(m.piece_count) : "…"} />
                <Metric label="Cuts" value={m ? countFmt(m.cut_count) : "…"} />
                <Metric label="Seams" value={m ? countFmt(m.seam_count) : "…"} />
                <Metric label="Strip sets" value={m ? countFmt(m.strip_set_count) : "…"} />
                <Metric label="Waste" value={m ? pctFmt(m.waste) : "…"} />
                <Metric
                  label="Difficulty"
                  value={m ? countFmt(m.difficulty) : "…"}
                  note={m?.heuristic_label}
                />
                <Metric
                  label="Sewing"
                  value={m ? `${countFmt(m.time_minutes)} min` : "…"}
                  note={m?.heuristic_label}
                />
              </span>
              {selected && handTweaked ? (
                <span className="pp-estimate">
                  Your version: {countFmt(estimates.pieces)} pieces · {countFmt(estimates.seams)}{" "}
                  seams — estimate
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
      <div className="pp-hint">
        The quilt preview draws the seams for the plan you pick. Want it your way? Use the Seams tool
        on the canvas — drag to sew squares into one piece, tap a piece to split it.
      </div>

      <div className="pp-head">
        <h3 className="pp-sub-title">Yardage</h3>
        <span className="pp-rule" />
        <span className="pp-pill">estimates</span>
      </div>
      <table className="pp-table" data-testid="yardage-table">
        <tbody>
          {yardage ? (
            <>
              {topLines.map((l) => (
                <tr key={l.fabric_id ?? l.name} className="pp-tr" data-testid={`yardage-row-${l.fabric_id}`} data-quarter-yards={l.quarter_yards}>
                  <td>
                    <span className="pp-name">
                      <span className="pp-swatch" style={{ background: colorById.get(l.fabric_id ?? "") ?? "#e0d4b8" }} />
                      {l.name}
                    </span>
                  </td>
                  <td className="pp-detail">
                    {squaresById.has(l.fabric_id ?? "")
                      ? `${countFmt(squaresById.get(l.fabric_id ?? "") ?? 0)} squares`
                      : "for the quilt top"}
                  </td>
                  <td className="pp-buy">
                    {formatQuarterYards(l.quarter_yards)} yd
                    <br />
                    <span className="pp-sub">estimate</span>
                  </td>
                </tr>
              ))}
              {bindingLine ? (
                <tr className="pp-tr" data-testid="yardage-row-binding" data-quarter-yards={bindingLine.quarter_yards}>
                  <td>
                    <span className="pp-name">
                      <span className="pp-swatch" style={{ background: colorById.get(bindingLine.fabric_id ?? "") ?? "#8c6f4e" }} />
                      {bindingLine.name}
                    </span>
                  </td>
                  <td className="pp-detail">binding strips, joined end to end</td>
                  <td className="pp-buy">
                    {formatQuarterYards(bindingLine.quarter_yards)} yd
                    <br />
                    <span className="pp-sub">estimate</span>
                  </td>
                </tr>
              ) : null}
              {backingLine ? (
                <tr className="pp-tr" data-testid="yardage-row-backing" data-quarter-yards={backingLine.quarter_yards}>
                  <td>
                    <span className="pp-name">
                      <span className="pp-swatch" style={{ background: "#e0d4b8" }} />
                      {backingLine.name}
                    </span>
                  </td>
                  <td className="pp-detail">wide backing fabric, seamed to fit</td>
                  <td className="pp-buy">
                    {formatQuarterYards(backingLine.quarter_yards)} yd
                    <br />
                    <span className="pp-sub">estimate</span>
                  </td>
                </tr>
              ) : null}
            </>
          ) : (
            <tr className="pp-tr">
              <td colSpan={3} className="pp-detail">
                Working out the yardage…
              </td>
            </tr>
          )}
          {summary ? (
            <tr
              className="pp-tr"
              data-testid="yardage-row-batting"
              data-quarter-yards={battingQuarterYards(summary.batting_height)}
            >
              <td>
                <span className="pp-name">
                  <span className="pp-swatch" style={{ background: "#f4efe3" }} />
                  Batting
                </span>
              </td>
              <td className="pp-detail">quilt plus 4 in on every side</td>
              <td className="pp-buy">
                {formatEighths(summary.batting_width)} × {formatEighths(summary.batting_height)}
                <br />
                <span className="pp-sub">
                  {formatQuarterYards(battingQuarterYards(summary.batting_height))} yd of a wide roll
                </span>
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
      <p className="pp-foot">
        Rounded up to the next 1/4 yard
        {usableEighths != null ? `, assuming ${formatEighths(usableEighths)} usable width` : ""}. Buy
        a little extra for insurance.
      </p>

      <div className="pp-head">
        <h3 className="pp-sub-title">Take it with you</h3>
        <span className="pp-rule" />
      </div>
      <div className="pp-dl-grid">
        {DL_BTNS.map((b) => (
          <button
            key={b.kind}
            type="button"
            data-testid={b.testid}
            className="pp-dl"
            disabled={busy === b.kind}
            onClick={() => void onExport(b.kind)}
          >
            {busy === b.kind ? (
              <span className="pp-dl-busy">
                <span className="pp-spinner" aria-hidden="true" />
                Making it…
              </span>
            ) : (
              <>
                <span className="pp-dl-label">{b.label}</span>
                <span className="pp-dl-sub">{b.sub}</span>
              </>
            )}
          </button>
        ))}
        <button type="button" data-testid="print-plan" className="pp-dl" onClick={onPrint}>
          <span className="pp-dl-label">Print one-page plan</span>
          <span className="pp-dl-sub">opens your print dialog</span>
        </button>
      </div>
      <button
        type="button"
        data-testid="copy-settings"
        className={`pp-copy${copied ? " pp-copy--done" : ""}`}
        onClick={() => void onCopy()}
      >
        {copied ? "Copied ✓" : "Copy my settings"}
      </button>

      <div className="pp-print-sheet" data-testid="print-sheet">
        <div className="pp-ps-head">
          <span className="pp-ps-title">{name} — quilt plan</span>
          <span className="pp-ps-meta">QREP</span>
        </div>
        <div className="pp-ps-size">{finishedSize} finished</div>
        <div className="pp-ps-facts">
          <span>
            Squares: {model.center.cols} × {model.center.rows} at{" "}
            {formatEighths(model.center.cell_size)}
          </span>
          <span>Borders: {borderText}</span>
          <span>Plan: {stratTitle} piecing plan</span>
        </div>
        <div className="pp-ps-note">
          Print the SVG diagram export for a full-size, true-to-scale cutting map.
        </div>
        <div className="pp-ps-list-head">Shopping list</div>
        {topLines.map((l) => (
          <div key={l.fabric_id ?? l.name} className="pp-ps-row">
            <span>{l.name}</span>
            <span>{formatQuarterYards(l.quarter_yards)} yd</span>
          </div>
        ))}
        <div className="pp-ps-row">
          <span>Binding</span>
          <span>{bindingLine ? `${formatQuarterYards(bindingLine.quarter_yards)} yd` : "estimate pending"}</span>
        </div>
        <div className="pp-ps-row">
          <span>Backing</span>
          <span>{backingLine ? `${formatQuarterYards(backingLine.quarter_yards)} yd` : "estimate pending"}</span>
        </div>
        {summary ? (
          <div className="pp-ps-row">
            <span>Batting</span>
            <span>
              {formatEighths(summary.batting_width)} × {formatEighths(summary.batting_height)}
            </span>
          </div>
        ) : null}
      </div>

      <style>{PP_CSS}</style>
    </section>
  );
}
