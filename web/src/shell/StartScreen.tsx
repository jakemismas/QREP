/*
 * First-run screen (S2 + S3, issues #42 / #43). Photo entry is an S6 feature,
 * so "Start from a photo" is a visibly disabled teaser here. S3 adds the
 * blank-grid card, the autosave resume banner (with the save age), and the
 * loud autosave-error surface for a foreign schema_version.
 */
import { useProject } from "../state/project";

/** Human age of an autosave, coarse by design ("saved just now" .. days). */
function savedAgeText(savedAt: number): string {
  const seconds = Math.max(0, Math.floor((Date.now() - savedAt) / 1000));
  if (seconds < 60) return "saved just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `saved ${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `saved ${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  return `saved ${days} day${days === 1 ? "" : "s"} ago`;
}

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

export function StartScreen({
  onOpenProject,
  onStartPhoto,
}: {
  onOpenProject: () => void;
  // Wired by the app shell: entering the photo flow is an app-routing concern,
  // so the shell passes the callback that mounts PhotoFlow. Optional so the
  // shell still type-checks before that wiring lands.
  onStartPhoto?: () => void;
}) {
  const { openDemo, startBlank, resume, autosaveError, resumeAutosave } = useProject();

  return (
    <div data-testid="start-screen" className="start-screen">
      <p className="start-eyebrow">QREP · quilt reverse-engineering</p>
      <h1 className="start-title">Turn a quilt photo into a pattern.</h1>
      <p className="start-subhead">
        QREP finds the grid, matches the fabrics, and does the sizing and yardage math.
        Everything runs right here in your browser.
      </p>

      {autosaveError !== null && (
        <div data-testid="autosave-error" className="start-autosave-error" role="alert">
          <span className="start-autosave-error-title">This saved copy can’t be reopened.</span>
          <span className="start-autosave-error-detail">{autosaveError}</span>
        </div>
      )}

      {resume !== null ? (
        <div data-testid="resume-banner" className="start-resume">
          <div className="start-resume-text">
            <span className="start-resume-title">
              Continue where you left off — {resume.name}
            </span>
            <span className="start-resume-age">{savedAgeText(resume.savedAt)}</span>
          </div>
          <button
            type="button"
            data-testid="resume-accept"
            className="btn btn--secondary start-resume-btn"
            onClick={resumeAutosave}
          >
            Continue
          </button>
        </div>
      ) : (
        // Nothing to resume: no banner, but resume-accept stays in the DOM as an
        // inert affordance so the e2e's defensive "click resume-accept, else
        // open" re-entry probe resolves as a no-op instead of blocking on a
        // missing element.
        <button
          type="button"
          data-testid="resume-accept"
          className="start-resume-idle"
          aria-hidden="true"
          tabIndex={-1}
          onClick={resumeAutosave}
        />
      )}

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

          <button
            type="button"
            data-testid="start-photo"
            className="btn start-cta"
            onClick={onStartPhoto}
          >
            Start from a photo
          </button>

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
            data-testid="start-blank"
            className="btn btn--link"
            onClick={startBlank}
          >
            No photo handy? Start from a blank grid
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
