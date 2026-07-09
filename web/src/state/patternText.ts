/**
 * Pattern-panel value helpers shared by the project store and PatternPanel
 * (S5, issue #45). Every displayed number is engine-authoritative: these
 * helpers only FORMAT bridge values (quarter-yards to mixed-fraction yards)
 * and build the clipboard summary. The one derived quantity is batting
 * quarter-yards, computed from the engine's batting length per PARITY item 9
 * (batting is surfaced from bridge dims, never a construction-plan metric).
 */
import type { ModelSummary, QuiltModel } from "../model/types";
import { formatEighths } from "../model/units";

const QUARTER_YARD_EIGHTHS = 72; // 9" = 1/4 yd

/** Metrics block from bridge plan output (qrep/construct/plan.py PlanMetrics). */
export interface PlanMetrics {
  piece_count: number;
  cut_count: number;
  seam_count: number;
  strip_set_count: number;
  waste: number;
  bias_percent: number;
  difficulty: number;
  time_minutes: number;
  heuristic_label: string;
}

/** One purchase line from bridge yardage output (compute_purchase_lines). */
export interface YardageLine {
  fabric_id: string | null;
  name: string;
  purpose: string; // top | binding | backing
  length_needed: number;
  quarter_yards: number;
}

/** The bridge `plan` envelope result: {plan, yardage, summary}. */
export interface StrategyPlan {
  plan: { strategy: string; quilt_name: string; metrics: PlanMetrics };
  yardage: { strategy: string; lines: YardageLine[] };
  summary: ModelSummary;
}

/** Quarter-yards to a mixed-fraction yard count, e.g. 22 -> "5 1/2". */
export function formatQuarterYards(quarterYards: number): string {
  const whole = Math.floor(quarterYards / 4);
  const rem = quarterYards % 4;
  const frac = rem === 1 ? "1/4" : rem === 2 ? "1/2" : rem === 3 ? "3/4" : "";
  if (rem === 0) return `${whole}`;
  return whole === 0 ? frac : `${whole} ${frac}`;
}

/**
 * Batting quarter-yards derived ONLY from the engine's batting length.
 * 72 eighths (9") = one quarter yard of a wide batting roll, so the count is
 * ceil(batting_height / 72); e.g. 98" (784 eighths) -> 11 quarters -> 2 3/4 yd.
 */
export function battingQuarterYards(battingHeightEighths: number): number {
  return Math.ceil(battingHeightEighths / QUARTER_YARD_EIGHTHS);
}

function finishedEighths(model: QuiltModel): { width: number; height: number } {
  const bandTotal = model.borders.reduce((sum, b) => sum + b.width, 0);
  return {
    width: model.center.cols * model.center.cell_size + 2 * bandTotal,
    height: model.center.rows * model.center.cell_size + 2 * bandTotal,
  };
}

/**
 * PARITY item 12 clipboard summary: name, finished size, squares, borders,
 * per-fabric yardage (from bridge plan lines), binding, backing, batting.
 */
export function buildSettingsSummary(
  model: QuiltModel,
  name: string,
  summary: ModelSummary | null,
  plan: StrategyPlan | null,
): string {
  const finished = finishedEighths(model);
  const lines: string[] = [];
  lines.push(`QREP pattern — ${name}`);
  lines.push(`Finished size: ${formatEighths(finished.width)} × ${formatEighths(finished.height)}`);
  lines.push(
    `Squares: ${model.center.cols} × ${model.center.rows} at ${formatEighths(
      model.center.cell_size,
    )} each (${model.center.cols * model.center.rows} squares)`,
  );
  lines.push(`Borders: ${model.borders.map((b) => formatEighths(b.width)).join(" + ")}`);

  const yardage = plan?.yardage.lines ?? [];
  const tops = yardage.filter((line) => line.purpose === "top");
  if (tops.length > 0) {
    lines.push("Fabric yardage:");
    for (const line of tops) {
      lines.push(`  - ${line.name}: ${formatQuarterYards(line.quarter_yards)} yd`);
    }
  }
  const binding = yardage.find((line) => line.purpose === "binding");
  lines.push(`Binding: ${binding ? `${formatQuarterYards(binding.quarter_yards)} yd` : "—"}`);
  const backing = yardage.find((line) => line.purpose === "backing");
  lines.push(`Backing: ${backing ? `${formatQuarterYards(backing.quarter_yards)} yd` : "—"}`);
  if (summary) {
    lines.push(
      `Batting: ${formatEighths(summary.batting_width)} × ${formatEighths(
        summary.batting_height,
      )} (${formatQuarterYards(battingQuarterYards(summary.batting_height))} yd)`,
    );
  } else {
    lines.push("Batting: —");
  }
  return lines.join("\n");
}
