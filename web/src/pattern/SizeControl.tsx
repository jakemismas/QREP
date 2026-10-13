/**
 * The size control on Your pattern (C2b, issue #148; SPEC.md section 6.3).
 * The size line shows the finished size the pattern prints: a size you set
 * with your request beside it when the whole-square size misses it, any
 * other size labeled a default, never a measurement (PS-09; criterion
 * U3-14). You set a size with a preset chip from bridge.presets() or a typed
 * width, height or both, in inches or centimeters (criteria U3-11, U3-12);
 * the engine snaps it to whole squares with no re-read (criterion U3-15).
 */
import { useState } from "react";
import type { FormEvent } from "react";
import type { SizeRequest } from "../engine/contract";
import type { SizeUnit } from "../model/sizeEntry";
import { parseSide, presetRequest, sizeText, typedRequest } from "./patternSize";
import type { Preset, SizeLine, SizerView } from "./patternSize";
import "./SizeControl.css";

const ENTRY_INVALID = "Type each side as a number, such as 86 or 67 1/2.";
const ENTRY_EMPTY = "Type a width, a height or both.";

function slug(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

export function SizeControl({
  line,
  presets,
  status,
  message,
  onSize,
}: {
  /** Null while the summary that holds the finished size is on its way. */
  line: SizeLine | null;
  presets: Preset[];
  status: SizerView["status"];
  message: string | null;
  onSize: (request: SizeRequest, preset: string | null) => void;
}) {
  const [width, setWidth] = useState("");
  const [height, setHeight] = useState("");
  const [unit, setUnit] = useState<SizeUnit>("in");
  const [entryError, setEntryError] = useState<string | null>(null);
  const busy = status === "busy";

  const apply = (event: FormEvent) => {
    event.preventDefault();
    const w = parseSide(width, unit);
    const h = parseSide(height, unit);
    if (w === "invalid" || h === "invalid") {
      setEntryError(ENTRY_INVALID);
      return;
    }
    const request = typedRequest(w, h);
    if (request === null) {
      setEntryError(ENTRY_EMPTY);
      return;
    }
    setEntryError(null);
    onSize(request, null);
  };

  const alert = entryError ?? (status === "failed" ? message : null);

  return (
    <section className="sc-root" data-testid="pattern-size">
      <h2 className="sc-title">Finished size</h2>
      {line !== null ? (
        <>
          <p className="sc-line" data-testid="pattern-size-line" data-size-kind={line.kind}>
            <span className="sc-label">{line.label}</span>
            <span className="sc-achieved">{line.achieved}</span>
          </p>
          {line.note !== null ? <p className="sc-note">{line.note}</p> : null}
          {line.asked !== null ? (
            <p className="sc-asked" data-testid="pattern-size-asked">
              {`You asked for ${line.asked}. In whole squares the nearest size is ${line.achieved}.`}
            </p>
          ) : null}
        </>
      ) : (
        <p className="sc-note">Working out the size…</p>
      )}

      {presets.length > 0 ? (
        <div className="sc-chips" role="group" aria-label="Standard sizes">
          {presets.map((preset) => (
            <button
              key={preset.name}
              type="button"
              className="sc-chip"
              data-testid={`pattern-size-chip-${slug(preset.name)}`}
              disabled={busy}
              onClick={() => {
                setEntryError(null);
                onSize(presetRequest(preset.name), preset.name);
              }}
            >
              <span className="sc-chip-name">{preset.name}</span>
              <span className="sc-chip-size">{sizeText(preset.width, preset.height)}</span>
            </button>
          ))}
        </div>
      ) : null}

      <form className="sc-typed" onSubmit={apply}>
        <label className="sc-field">
          <span className="sc-field-label">Width</span>
          <input
            className="sc-input"
            data-testid="pattern-size-width"
            inputMode="decimal"
            autoComplete="off"
            value={width}
            disabled={busy}
            onChange={(event) => setWidth(event.target.value)}
          />
        </label>
        <span className="sc-by" aria-hidden="true">
          x
        </span>
        <label className="sc-field">
          <span className="sc-field-label">Height</span>
          <input
            className="sc-input"
            data-testid="pattern-size-height"
            inputMode="decimal"
            autoComplete="off"
            value={height}
            disabled={busy}
            onChange={(event) => setHeight(event.target.value)}
          />
        </label>
        <button
          type="button"
          className="sc-unit"
          data-testid="pattern-size-unit"
          aria-label={unit === "in" ? "Inches; switch to centimeters" : "Centimeters; switch to inches"}
          disabled={busy}
          onClick={() => setUnit(unit === "in" ? "cm" : "in")}
        >
          {unit}
        </button>
        <button
          type="submit"
          className="btn btn--secondary sc-apply"
          data-testid="pattern-size-apply"
          disabled={busy}
        >
          Set size
        </button>
      </form>

      {busy ? (
        <p className="sc-busy" role="status" data-testid="pattern-size-busy">
          Sizing your pattern…
        </p>
      ) : null}
      {alert !== null ? (
        <p className="sc-error" role="alert" data-testid="pattern-size-error">
          {alert}
        </p>
      ) : null}
    </section>
  );
}
