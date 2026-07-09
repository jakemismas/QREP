/*
 * App header (S2, issue #42). Always visible. The project-name field and the
 * "Open" button appear only once a model is loaded: on the start screen the
 * open affordance lives in StartScreen, so keeping the header's copy off-screen
 * there guarantees getByTestId("open-project") resolves to a single element.
 */
import { useEffect, useState } from "react";
import { EngineChip, Tooltip, useTheme } from "../ui";
import { useEngine } from "../engine/useEngine";
import { useProject } from "../state/project";

function Logo({ isDesk, onClick }: { isDesk: boolean; onClick: () => void }) {
  return (
    <Tooltip tip="Back to the start screen">
      <button
        type="button"
        className="qrep-logo"
        onClick={onClick}
        aria-label="Back to the start screen"
      >
        <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true">
          <rect x="1" y="1" width="11" height="11" rx="2" fill="#a9c7dc" />
          <rect x="14" y="1" width="11" height="11" rx="2" fill="var(--accent)" />
          <rect x="1" y="14" width="11" height="11" rx="2" fill="var(--accent)" />
          <rect x="14" y="14" width="11" height="11" rx="2" fill="#a9c7dc" />
        </svg>
        <span className="qrep-wordmark">QREP</span>
        {isDesk ? <span className="qrep-tagline">quilt reverse-engineering</span> : null}
      </button>
    </Tooltip>
  );
}

function ProjectName() {
  const { name, rename } = useProject();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(name);

  useEffect(() => {
    setDraft(name);
  }, [name]);

  if (!editing) {
    return (
      <Tooltip tip="Project name — click to rename">
        <button
          type="button"
          data-testid="project-name"
          className="qrep-projname"
          onClick={() => {
            setDraft(name);
            setEditing(true);
          }}
        >
          {name}
        </button>
      </Tooltip>
    );
  }

  const commit = () => {
    rename(draft);
    setEditing(false);
  };

  return (
    <input
      data-testid="project-name"
      className="qrep-projname qrep-projname--edit"
      value={draft}
      autoFocus
      aria-label="Project name"
      onChange={(event) => setDraft(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          event.currentTarget.blur();
        } else if (event.key === "Escape") {
          setDraft(name);
          setEditing(false);
        }
      }}
    />
  );
}

function ThemeToggle() {
  const { skin, toggle } = useTheme();
  const label = skin === "light" ? "Switch to evening mode" : "Switch to daylight mode";
  return (
    <Tooltip tip={label}>
      <button
        type="button"
        data-testid="theme-toggle"
        className="theme-toggle"
        onClick={toggle}
        aria-label={label}
      >
        {skin === "light" ? (
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
            <circle cx="9" cy="9" r="4" fill="currentColor" />
            <g stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
              <line x1="9" y1="0.5" x2="9" y2="2.5" />
              <line x1="9" y1="15.5" x2="9" y2="17.5" />
              <line x1="0.5" y1="9" x2="2.5" y2="9" />
              <line x1="15.5" y1="9" x2="17.5" y2="9" />
              <line x1="2.9" y1="2.9" x2="4.3" y2="4.3" />
              <line x1="13.7" y1="13.7" x2="15.1" y2="15.1" />
              <line x1="2.9" y1="15.1" x2="4.3" y2="13.7" />
              <line x1="13.7" y1="4.3" x2="15.1" y2="2.9" />
            </g>
          </svg>
        ) : (
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
            <path d="M15 11.5A7 7 0 0 1 6.5 3 7 7 0 1 0 15 11.5z" fill="currentColor" />
          </svg>
        )}
      </button>
    </Tooltip>
  );
}

export function Header({
  isDesk,
  onOpenProject,
}: {
  isDesk: boolean;
  onOpenProject: () => void;
}) {
  const engine = useEngine();
  const { model, goHome } = useProject();
  const hasModel = model !== null;

  return (
    <header className="qrep-header" data-noprint>
      <Logo isDesk={isDesk} onClick={goHome} />
      {hasModel && isDesk ? <ProjectName /> : null}
      <span className="qrep-spacer" />
      {hasModel ? (
        <button
          type="button"
          data-testid="open-project"
          className="btn btn--secondary"
          onClick={onOpenProject}
        >
          Open
        </button>
      ) : null}
      <EngineChip status={engine.status} onRetry={engine.retry} />
      <ThemeToggle />
    </header>
  );
}
