/**
 * The live grid (C3a, issue #149; criteria W9): drawn in perspective from the
 * pins, the counts and the bands, with no engine call. It renders SVG in
 * canvas coordinates, inside PinLayer's overlay; strokes keep their screen
 * width at any zoom.
 */
import type { BorderBand, Point } from "../engine/contract";
import { bandRange, fieldRange } from "./bands";
import type { AxisCount } from "./counts";
import { gridLines, rangeQuad, type Homography, type Quad, type Segment } from "./geometry";

interface Props {
  /** The pinned quad's homography: the outer edge, or the field in field mode. */
  homography: Homography;
  across: AxisCount;
  down: AxisCount;
  /** Bands from the outside in; empty in field mode. */
  bands: readonly BorderBand[];
  activeBand?: number | null;
  /** Field corners pinned beside an outer edge, drawn for comparison. */
  pinnedField?: Quad | null;
}

const points = (quad: Quad) => quad.map((p) => `${p.x},${p.y}`).join(" ");

function Lines({ segments, className }: { segments: Segment[]; className: string }) {
  const d = segments.map(([a, b]: [Point, Point]) => `M${a.x} ${a.y}L${b.x} ${b.y}`).join("");
  return <path className={className} d={d} vectorEffect="non-scaling-stroke" />;
}

export function GridOverlay({ homography, across, down, bands, activeBand = null, pinnedField = null }: Props) {
  const cols = across.blocks * across.squaresPerBlock;
  const rows = down.blocks * down.squaresPerBlock;
  const field = fieldRange(cols, rows, bands);
  const squares = gridLines(homography, cols, rows, field);
  const blocks = gridLines(homography, across.blocks, down.blocks, field);
  return (
    <g className="cf-grid" data-testid="grid-overlay" data-cols={cols} data-rows={rows}>
      <Lines className="cf-grid__square" segments={[...squares.vertical, ...squares.horizontal]} />
      <Lines className="cf-grid__block" segments={[...blocks.vertical, ...blocks.horizontal]} />
      {bands.map((_, k) => (
        <polygon
          key={k}
          className="cf-grid__band"
          data-active={k === activeBand}
          data-testid={`band-line-${k + 1}`}
          points={points(rangeQuad(homography, bandRange(cols, rows, bands, k)))}
          vectorEffect="non-scaling-stroke"
        />
      ))}
      <polygon
        className="cf-grid__edge"
        points={points(rangeQuad(homography, { u0: 0, u1: 1, v0: 0, v1: 1 }))}
        vectorEffect="non-scaling-stroke"
      />
      {pinnedField && (
        <polygon className="cf-grid__field" points={points(pinnedField)} vectorEffect="non-scaling-stroke" />
      )}
    </g>
  );
}
