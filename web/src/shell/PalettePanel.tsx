/**
 * Editable fabrics panel (S3, issue #43). A superset of the read-only
 * FabricsPanel: each row keeps the swatch + census meta, and adds an inline
 * recolor input, an inline rename field, and a per-row delete. The bridge
 * census (summary) stays the ground truth for square counts, exactly as in
 * FabricsPanel, so the count element only appears once validation lands.
 *
 * The committed name is mirrored in an aria-hidden text node so the row's
 * text content reflects renames (the rename control itself is an <input>,
 * whose value is not part of text content); screen readers use the input.
 */
import { useEffect, useRef, useState } from "react";
import type { Fabric } from "../model/types";
import { useProject } from "../state/project";

const PP_CSS = `
.pp-root { background: var(--card); border: 1px solid var(--line); border-radius: 16px; box-shadow: 0 2px 10px var(--shadow); padding: 18px; display: flex; flex-direction: column; gap: 6px; font: 400 16.5px var(--sans, sans-serif); color: var(--ink2); }
.pp-head { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.pp-title { margin: 0; font: 700 21px var(--serif, serif); color: var(--denim); flex: 1; }
.pp-hint { flex: none; font-size: 11.5px; color: var(--faint); border: 1px solid var(--pillLn); background: var(--pill); border-radius: 999px; padding: 3px 9px; }
.pp-list { list-style: none; margin: 0; padding: 0; }
.pp-row { display: flex; align-items: center; gap: 12px; padding: 12px 2px; border-bottom: 1px dashed var(--line); }
.pp-row:last-child { border-bottom: none; }
.pp-swatch { position: relative; flex: none; width: 46px; height: 46px; border-radius: 10px; border: 1px solid var(--line2); box-shadow: inset 0 -2px 5px rgba(0, 0, 0, 0.07); overflow: hidden; }
.pp-color { position: absolute; inset: 0; width: 100%; height: 100%; padding: 0; border: none; background: none; cursor: pointer; opacity: 0; }
.pp-info { min-width: 0; flex: 1; }
.pp-rename { width: 100%; border: 1.5px solid transparent; border-radius: 8px; padding: 4px 6px; font: 600 16.5px var(--sans, sans-serif); color: var(--ink); background: none; }
.pp-rename:hover { border-color: var(--line2); }
.pp-rename:focus { border-color: var(--accent); outline: none; background: var(--card2); box-shadow: 0 0 0 3px rgba(165, 80, 47, 0.16); }
.pp-sr { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
.pp-meta { font-size: 14px; color: var(--mut); margin-top: 2px; padding: 0 6px; }
.pp-hex { font-variant-numeric: tabular-nums; letter-spacing: 0.02em; }
.pp-counting { font-style: italic; color: var(--faint); }
.pp-del { flex: none; width: 34px; height: 34px; display: inline-flex; align-items: center; justify-content: center; border-radius: 9px; border: 1.5px solid var(--line2); background: var(--card2); color: var(--mut); }
.pp-del:hover { border-color: var(--accent); color: var(--accent); background: var(--card); }
.pp-add { margin-top: 10px; align-self: flex-start; border: 1.5px dashed var(--line2); border-radius: 10px; background: none; padding: 10px 14px; font: 600 14.5px var(--sans, sans-serif); color: var(--ink2); }
.pp-add:hover { border-color: var(--accent); color: var(--accent); }
.pp-note { margin: 12px 0 0; font-size: 13px; color: var(--faint); }
`;

function PaletteRow({
  fabric,
  count,
  inBorder,
}: {
  fabric: Fabric;
  count: number | undefined;
  inBorder: boolean;
}) {
  const { recolorFabric, renameFabric, deleteFabric } = useProject();
  const [draft, setDraft] = useState(fabric.name);
  const editingRef = useRef(false);

  // Adopt external name changes (open, undo) only when not mid-edit, so a
  // background re-render never clobbers what the user is typing.
  useEffect(() => {
    if (!editingRef.current) setDraft(fabric.name);
  }, [fabric.name]);

  const commit = () => {
    editingRef.current = false;
    const next = draft.trim();
    if (next && next !== fabric.name) renameFabric(fabric.id, next);
    else setDraft(fabric.name);
  };

  return (
    <li className="pp-row" data-testid={`fabric-row-${fabric.id}`}>
      <span className="pp-swatch" style={{ background: fabric.color }}>
        <input
          type="color"
          className="pp-color"
          data-testid={`fabric-color-${fabric.id}`}
          value={fabric.color}
          aria-label={`Recolor ${fabric.name}`}
          onChange={(event) => recolorFabric(fabric.id, event.target.value)}
        />
      </span>
      <div className="pp-info">
        <input
          className="pp-rename"
          data-testid={`fabric-rename-${fabric.id}`}
          value={draft}
          aria-label={`Rename ${fabric.name}`}
          onChange={(event) => {
            editingRef.current = true;
            setDraft(event.target.value);
          }}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              event.currentTarget.blur();
            } else if (event.key === "Escape") {
              editingRef.current = false;
              setDraft(fabric.name);
              event.currentTarget.blur();
            }
          }}
        />
        <span className="pp-sr" aria-hidden="true">
          {fabric.name}
        </span>
        <div className="pp-meta">
          <span className="pp-hex">{fabric.color.toUpperCase()}</span>
          <span> · </span>
          {count != null ? (
            <span className="pp-count" data-testid={`fabric-count-${fabric.id}`}>
              {count.toLocaleString("en-US")} squares{inBorder ? " + borders" : ""}
            </span>
          ) : (
            <span className="pp-count pp-counting">counting squares…</span>
          )}
        </div>
      </div>
      <button
        type="button"
        className="pp-del"
        data-testid={`delete-fabric-${fabric.id}`}
        aria-label={`Delete ${fabric.name}`}
        onClick={() => {
          void deleteFabric(fabric.id);
        }}
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path
            d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.6 8a1 1 0 0 0 1 .9h3.8a1 1 0 0 0 1-.9l.6-8"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
    </li>
  );
}

export function PalettePanel() {
  const { model, summary, addFabric } = useProject();
  if (model === null) return null;

  const borderFabricIds = new Set(model.borders.map((b) => b.fabric_id));
  const countById = new Map((summary?.fabrics ?? []).map((f) => [f.id, f.cell_count]));

  return (
    <section className="pp-root">
      <header className="pp-head">
        <h2 className="pp-title">Fabrics</h2>
        <span className="pp-hint">tap a swatch to recolor</span>
      </header>
      <ul className="pp-list">
        {model.palette.fabrics.map((fabric) => (
          <PaletteRow
            key={fabric.id}
            fabric={fabric}
            count={countById.get(fabric.id)}
            inBorder={borderFabricIds.has(fabric.id)}
          />
        ))}
      </ul>
      <button type="button" className="pp-add" data-testid="add-fabric" onClick={addFabric}>
        ＋ Add a fabric
      </button>
      <p className="pp-note">
        Pick a fabric here, then paint squares on the quilt. Recoloring updates the quilt
        instantly.
      </p>
      <style>{PP_CSS}</style>
    </section>
  );
}
