/**
 * The census join (C2a, issue #96): one row per fabric of the engine's
 * pattern summary, in its order, with the letter and name the PDF prints
 * (PATTERN-SPEC C-02, C-03, PS-40), the palette color for the swatch, and
 * the square count from the validate census. The fabric id is the row key
 * and the test ids, and the letter shown is the engine's letter field, which
 * equals the fabric id ("b", "c", "f0") until ticket A4b prints A, B and C
 * (qrep/export/pattern.py sets letter=fabric.id), so for now the census
 * shows the id as the letter.
 */
import type { FabricLine } from "../engine/contract";
import type { Fabric, ModelSummary } from "../model/types";
import type { CensusRow } from "../viewer/FabricsPanel";

export function censusRows(
  lines: FabricLine[],
  palette: Fabric[],
  census: ModelSummary | null,
): CensusRow[] {
  const colorById = new Map(palette.map((fabric) => [fabric.id, fabric.color]));
  const countById = new Map((census?.fabrics ?? []).map((fabric) => [fabric.id, fabric.cell_count]));
  return lines.map((line) => ({
    fabricId: line.fabric_id,
    letter: line.letter,
    name: line.name,
    color: colorById.get(line.fabric_id) ?? null,
    count: countById.get(line.fabric_id) ?? null,
  }));
}
