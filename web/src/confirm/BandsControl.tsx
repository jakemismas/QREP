/**
 * Border bands, a list set inward from the outer edge (C3a, issue #149; plan
 * section 2.1; Critique: CR-cv-25). Set a band by dragging its inner line on
 * the photo, with steppers in quarter squares, or by a typed width in inches
 * rounded to 1/4 in. Inches need the finished square size; until it is set
 * the inch field is disabled and the other two ways still work (#149,
 * comment 6142353076).
 */
import { useEffect, useState } from "react";
import type { BorderBand } from "../engine/contract";
import { BAND_STEP_SQUARES, inchesToSquares, squaresToInches, stepBand } from "./bands";
import "./confirm.css";

interface Props {
  bands: BorderBand[];
  onChange: (bands: BorderBand[]) => void;
  /** The band whose inner line shows drag handles. */
  activeBand: number | null;
  onSelect: (k: number | null) => void;
  /** The finished square size in eighths of an inch, or null when unset. */
  squareEighths: number | null;
}

/** A new band starts one square wide; drag, step or type it to its width. */
const NEW_BAND: BorderBand = { width_squares: 1 };

function formatInches(inches: number): string {
  // Eighths, the unit lengths use (docs/SPEC.md section 7).
  const eighths = Math.round(inches * 8);
  const whole = Math.floor(eighths / 8);
  const rest = eighths % 8;
  if (rest === 0) return `${whole} in`;
  const [n, d] = rest % 4 === 0 ? [rest / 4, 2] : rest % 2 === 0 ? [rest / 2, 4] : [rest, 8];
  return whole ? `${whole} ${n}/${d} in` : `${n}/${d} in`;
}

function InchField({ index, width, squareEighths, onSet }: { index: number; width: number; squareEighths: number | null; onSet: (w: number) => void }) {
  // Three decimals: a dragged width is not a whole quarter inch.
  const shown = squareEighths ? String(Number(squaresToInches(width, squareEighths).toFixed(3))) : "";
  const [text, setText] = useState(shown);
  useEffect(() => setText(shown), [shown]);
  const apply = () => {
    const inches = Number(text);
    if (!squareEighths || !(inches > 0)) return setText(shown);
    const squares = inchesToSquares(inches, squareEighths);
    if (!(squares > 0)) return setText(shown);
    onSet(squares);
    // The rounded width can equal the current one, which leaves shown unchanged.
    setText(String(Number(squaresToInches(squares, squareEighths).toFixed(3))));
  };
  return (
    <label className="cf-bands__inches">
      <span>Width in inches</span>
      <input
        type="text"
        inputMode="decimal"
        data-testid={`band-${index + 1}-inches`}
        disabled={squareEighths === null}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={apply}
        onKeyDown={(e) => {
          if (e.key === "Enter") apply();
        }}
      />
    </label>
  );
}

export function BandsControl({ bands, onChange, activeBand, onSelect, squareEighths }: Props) {
  const setWidth = (k: number, width: number) =>
    onChange(bands.map((band, i) => (i === k ? { width_squares: width } : band)));
  return (
    <section className="cf-bands" aria-label="Border bands">
      <p className="cf-bands__hint">
        Bands run from the outer edge inward. Select a band to drag its inner line on the photo.
      </p>
      {squareEighths === null && (
        <p className="cf-bands__hint" data-testid="bands-inches-off">
          Set the finished square size to type widths in inches.
        </p>
      )}
      <ol className="cf-bands__list">
        {bands.map((band, k) => (
          <li key={k} className="cf-bands__band" data-active={k === activeBand} data-testid={`band-${k + 1}`}>
            <div className="cf-bands__head">
              <button
                type="button"
                className="cf-btn"
                aria-pressed={k === activeBand}
                data-testid={`band-${k + 1}-select`}
                onClick={() => onSelect(k === activeBand ? null : k)}
              >
                {k === 0 ? "Band 1 (outermost)" : `Band ${k + 1}`}
              </button>
              <span className="cf-bands__width" data-testid={`band-${k + 1}-width`}>
                {band.width_squares} {band.width_squares === 1 ? "square" : "squares"}
                {squareEighths !== null && `, ${formatInches(squaresToInches(band.width_squares, squareEighths))}`}
              </span>
            </div>
            <div className="cf-bands__controls">
              <button
                type="button"
                className="cf-btn cf-stepper__btn"
                aria-label={`Band ${k + 1} narrower by ${BAND_STEP_SQUARES} square`}
                data-testid={`band-${k + 1}-dec`}
                onClick={() => setWidth(k, stepBand(band.width_squares, -1))}
              >
                -
              </button>
              <button
                type="button"
                className="cf-btn cf-stepper__btn"
                aria-label={`Band ${k + 1} wider by ${BAND_STEP_SQUARES} square`}
                data-testid={`band-${k + 1}-inc`}
                onClick={() => setWidth(k, stepBand(band.width_squares, 1))}
              >
                +
              </button>
              <InchField index={k} width={band.width_squares} squareEighths={squareEighths} onSet={(w) => setWidth(k, w)} />
              <button
                type="button"
                className="cf-btn"
                data-testid={`band-${k + 1}-remove`}
                onClick={() => {
                  onChange(bands.filter((_, i) => i !== k));
                  onSelect(null);
                }}
              >
                Remove
              </button>
            </div>
          </li>
        ))}
      </ol>
      <button
        type="button"
        className="cf-btn"
        data-testid="band-add"
        onClick={() => {
          onChange([...bands, NEW_BAND]);
          onSelect(bands.length);
        }}
      >
        Add a band inside
      </button>
    </section>
  );
}
