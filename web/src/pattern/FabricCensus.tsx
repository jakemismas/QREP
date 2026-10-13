/**
 * The census on Your pattern (C2a, issue #96): censusRows joins the engine's
 * letters and names with the palette swatches and the validate census, and
 * the revived FabricsPanel draws the rows. C2b (issue #148) adds each
 * fabric's yards from the same summary line, printed as the engine gives it.
 */
import { useMemo } from "react";
import type { FabricLine } from "../engine/contract";
import type { Fabric, ModelSummary } from "../model/types";
import { FabricsPanel } from "../viewer";
import { censusRows } from "./census";
import { yardsText } from "./patternSize";
import "./FabricCensus.css";

export function FabricCensus({
  lines,
  palette,
  census,
  countFailed,
}: {
  lines: FabricLine[];
  palette: Fabric[];
  census: ModelSummary | null;
  /** The census failed: the error line above offers its Retry. */
  countFailed: boolean;
}) {
  const rows = useMemo(() => {
    // A fabric the top does not use has a 0 yd line; its amount is elsewhere
    // (the binding line), so its row shows none.
    const yardsById = new Map(lines.map((line) => [line.fabric_id, line.yards]));
    return censusRows(lines, palette, census).map((row) => {
      const yards = yardsById.get(row.fabricId) ?? 0;
      return { ...row, yards: yards > 0 ? { value: yards, text: yardsText(yards) } : null };
    });
  }, [lines, palette, census]);
  return <FabricsPanel rows={rows} countFailed={countFailed} />;
}
