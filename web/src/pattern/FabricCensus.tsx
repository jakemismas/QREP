/**
 * The census on Your pattern (C2a, issue #96): censusRows joins the engine's
 * letters and names with the palette swatches and the validate census, and
 * the revived FabricsPanel draws the rows.
 */
import { useMemo } from "react";
import type { FabricLine } from "../engine/contract";
import type { Fabric, ModelSummary } from "../model/types";
import { FabricsPanel } from "../viewer";
import { censusRows } from "./census";

export function FabricCensus({
  lines,
  palette,
  census,
}: {
  lines: FabricLine[];
  palette: Fabric[];
  census: ModelSummary | null;
}) {
  const rows = useMemo(() => censusRows(lines, palette, census), [lines, palette, census]);
  return <FabricsPanel rows={rows} />;
}
