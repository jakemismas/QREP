/**
 * Editor toolbar (S3, issue #43): Paint/Move mode group, one quick swatch per
 * fabric (picking a swatch also switches to paint, as the mock does), and
 * Undo/Redo. This component owns the Ctrl/Cmd+Z / Ctrl+Y / Ctrl+Shift+Z
 * keyboard shortcuts for the editor, so the integration layer must NOT also
 * bind them. Styled from design tokens only; swatch colors are user data.
 */
import { useEffect, useRef } from "react";
import type { Fabric } from "../model/types";

export type EditorMode = "move" | "paint";

interface EditorToolbarProps {
  fabrics: Fabric[];
  mode: EditorMode;
  selectedFabricId: string | null;
  onMode: (mode: EditorMode) => void;
  onSelectFabric: (id: string) => void;
  onUndo: () => void;
  onRedo: () => void;
  canUndo: boolean;
  canRedo: boolean;
}

const ET_CSS = `
.et-root { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.et-group { display: flex; align-items: center; gap: 4px; background: var(--card2); border: 1.5px solid var(--line2); border-radius: 11px; padding: 4px; }
.et-mode { display: inline-flex; align-items: center; gap: 6px; height: 34px; padding: 0 15px; border: none; background: transparent; border-radius: 8px; font: 600 14.5px var(--sans, sans-serif); color: var(--mut); cursor: pointer; }
.et-mode:hover { color: var(--ink2); }
.et-mode--active { background: var(--card); color: var(--accent); box-shadow: 0 2px 6px var(--shadow); }
.et-mode--active:hover { color: var(--accent); }
.et-divider { flex: none; width: 1px; height: 30px; background: var(--line); }
.et-swatches { display: flex; align-items: center; gap: 8px; }
.et-swatch { flex: none; width: 34px; height: 34px; border-radius: 9px; border: none; padding: 0; cursor: pointer; box-shadow: inset 0 -2px 5px rgba(0, 0, 0, 0.07); }
.et-swatch--selected { box-shadow: inset 0 -2px 5px rgba(0, 0, 0, 0.07), 0 0 0 2.5px var(--card), 0 0 0 5px var(--accent); }
.et-icons { display: flex; align-items: center; gap: 6px; }
.et-icon { display: inline-flex; align-items: center; justify-content: center; width: 38px; height: 38px; color: var(--ink2); background: var(--card2); border: 1.5px solid var(--line2); border-radius: 10px; cursor: pointer; }
.et-icon:hover:not(:disabled) { background: var(--card3); }
.et-icon:disabled { opacity: 0.35; cursor: default; }
`;

const UNDO_PATH = "M9 7 4.5 11.5 9 16 M4.5 11.5 H15 a4.5 4.5 0 0 1 0 9 h-1.5";
const REDO_PATH = "M15 7 19.5 11.5 15 16 M19.5 11.5 H9 a4.5 4.5 0 0 0 0 9 h1.5";

export function EditorToolbar({
  fabrics,
  mode,
  selectedFabricId,
  onMode,
  onSelectFabric,
  onUndo,
  onRedo,
  canUndo,
  canRedo,
}: EditorToolbarProps) {
  // Keyboard handlers read live values through refs so the window listener can
  // bind once without going stale as undo depth or the callbacks change.
  const onUndoRef = useRef(onUndo);
  onUndoRef.current = onUndo;
  const onRedoRef = useRef(onRedo);
  onRedoRef.current = onRedo;
  const canUndoRef = useRef(canUndo);
  canUndoRef.current = canUndo;
  const canRedoRef = useRef(canRedo);
  canRedoRef.current = canRedo;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey)) return;
      const key = e.key.toLowerCase();
      if (key === "z" && !e.shiftKey) {
        e.preventDefault();
        if (canUndoRef.current) onUndoRef.current();
      } else if (key === "y" || (key === "z" && e.shiftKey)) {
        e.preventDefault();
        if (canRedoRef.current) onRedoRef.current();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="et-root" role="toolbar" aria-label="Editing tools">
      <div className="et-group" role="group" aria-label="Canvas mode">
        <button
          type="button"
          data-testid="mode-paint"
          className={`et-mode${mode === "paint" ? " et-mode--active" : ""}`}
          aria-pressed={mode === "paint"}
          title="Paint squares with the selected fabric"
          onClick={() => onMode("paint")}
        >
          Paint
        </button>
        <button
          type="button"
          data-testid="mode-move"
          className={`et-mode${mode === "move" ? " et-mode--active" : ""}`}
          aria-pressed={mode === "move"}
          title="Drag to move around the quilt"
          onClick={() => onMode("move")}
        >
          Move
        </button>
      </div>

      <span className="et-divider" aria-hidden="true" />

      <div className="et-swatches" role="group" aria-label="Fabrics">
        {fabrics.map((f) => (
          <button
            key={f.id}
            type="button"
            data-testid={`swatch-${f.id}`}
            className={`et-swatch${selectedFabricId === f.id ? " et-swatch--selected" : ""}`}
            style={{ background: f.color }}
            aria-label={`${f.name} — paint with this`}
            aria-pressed={selectedFabricId === f.id}
            title={`${f.name} — paint with this`}
            onClick={() => {
              onSelectFabric(f.id);
              onMode("paint");
            }}
          />
        ))}
      </div>

      <span className="et-divider" aria-hidden="true" />

      <div className="et-icons">
        <button
          type="button"
          data-testid="undo"
          className="et-icon"
          disabled={!canUndo}
          aria-label="Undo"
          title="Undo"
          onClick={onUndo}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d={UNDO_PATH} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        <button
          type="button"
          data-testid="redo"
          className="et-icon"
          disabled={!canRedo}
          aria-label="Redo"
          title="Redo"
          onClick={onRedo}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d={REDO_PATH} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>

      <style>{ET_CSS}</style>
    </div>
  );
}
