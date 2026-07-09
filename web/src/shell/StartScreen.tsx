/*
 * First-run screen (S2, issue #42). Photo entry is an S6 feature, so
 * "Start from a photo" is a visibly disabled teaser here. The demo and
 * open-project actions carry the fixed test ids; the blank-grid and resume
 * affordances arrive with S3.
 */
import { Tooltip } from "../ui";
import { useProject } from "../state/project";

// Decorative mini-quilt for the polaroid: a sparse two-colour chain motif.
// Purely presentational (aria-hidden); the real canvas render is the viewer.
const CELL = 18;
const GRID = 9;
const CHAIN = "#a9c7dc";
const CREAM = "#f7f1e0";

function isChain(row: number, col: number): boolean {
  return row === col || row + col === GRID - 1 || (row % 4 === 0 && col % 4 === 0);
}

const AXIS = Array.from({ length: GRID }, (_, index) => index);

function MiniQuilt() {
  const size = CELL * GRID;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      {AXIS.map((row) =>
        AXIS.map((col) => (
          <rect
            key={`${row}-${col}`}
            x={col * CELL}
            y={row * CELL}
            width={CELL}
            height={CELL}
            fill={isChain(row, col) ? CHAIN : CREAM}
          />
        )),
      )}
    </svg>
  );
}

export function StartScreen({ onOpenProject }: { onOpenProject: () => void }) {
  const { openDemo } = useProject();

  return (
    <div data-testid="start-screen" className="start-screen">
      <p className="start-eyebrow">QREP · quilt reverse-engineering</p>
      <h1 className="start-title">Turn a quilt photo into a pattern.</h1>
      <p className="start-subhead">
        QREP finds the grid, matches the fabrics, and does the sizing and yardage math.
        Everything runs right here in your browser.
      </p>

      <div className="start-row">
        <div className="start-polaroid" aria-hidden="true">
          <MiniQuilt />
          <div className="start-polaroid-caption">
            <span className="start-polaroid-name">IMG_2847.jpeg</span>
            <span className="start-polaroid-tag">sample photo</span>
          </div>
        </div>

        <div className="start-actions">
          <p className="start-lede">
            Lay the quilt flat, take one straight-on shot, and drop it in. You get back a
            quilt you can repaint, resize and re-plan — with the fabric math done for you.
          </p>

          <Tooltip tip="Coming soon">
            <span className="start-cta-wrap">
              <button
                type="button"
                data-testid="photo-teaser"
                className="btn start-cta"
                disabled
              >
                Start from a photo
              </button>
            </span>
          </Tooltip>

          <button
            type="button"
            data-testid="open-demo"
            className="btn btn--secondary"
            onClick={() => {
              void openDemo();
            }}
          >
            Open the demo quilt instead
          </button>

          <button
            type="button"
            data-testid="open-project"
            className="btn btn--link"
            onClick={onOpenProject}
          >
            Open a saved project
          </button>

          <p className="start-note">
            Everything runs in your browser — the vision engine loads itself the first
            time, about 12 MB.
          </p>
        </div>
      </div>
    </div>
  );
}
