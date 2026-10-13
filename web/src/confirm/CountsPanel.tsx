/**
 * Counts in quilter units (C3a, issue #149; plan section 2.1): blocks across
 * x squares per block, and blocks down x squares per block, typed or with
 * steppers, with the total shown, for example "8 blocks x 5 squares = 40
 * squares". A quilt with no repeating block uses one block per axis.
 */
import { useEffect, useState } from "react";
import { axisLabel, COUNT_MAX, parseCount, type AxisCount } from "./counts";
import "./confirm.css";

interface StepperProps {
  label: string;
  value: number;
  testId: string;
  onChange: (value: number) => void;
}

/** A whole-number field with minus and plus buttons; a typed value applies once it is valid. */
export function CountStepper({ label, value, testId, onChange }: StepperProps) {
  const [text, setText] = useState(String(value));
  useEffect(() => setText(String(value)), [value]);
  const set = (next: number) => onChange(Math.min(COUNT_MAX, Math.max(1, next)));
  return (
    <div className="cf-stepper">
      <button
        type="button"
        className="cf-btn cf-stepper__btn"
        aria-label={`Fewer ${label}`}
        data-testid={`${testId}-dec`}
        disabled={value <= 1}
        onClick={() => set(value - 1)}
      >
        -
      </button>
      <input
        className="cf-stepper__input"
        type="text"
        inputMode="numeric"
        aria-label={label}
        data-testid={testId}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          const parsed = parseCount(e.target.value);
          if (parsed !== null) onChange(parsed);
        }}
        onBlur={() => setText(String(value))}
      />
      <button
        type="button"
        className="cf-btn cf-stepper__btn"
        aria-label={`More ${label}`}
        data-testid={`${testId}-inc`}
        disabled={value >= COUNT_MAX}
        onClick={() => set(value + 1)}
      >
        +
      </button>
    </div>
  );
}

interface AxisProps {
  axis: "across" | "down";
  value: AxisCount;
  onChange: (value: AxisCount) => void;
}

function AxisRow({ axis, value, onChange }: AxisProps) {
  return (
    <fieldset className="cf-counts__axis">
      <legend className="cf-counts__legend">{axis === "across" ? "Across" : "Down"}</legend>
      <div className="cf-counts__row">
        <CountStepper
          label={`blocks ${axis}`}
          testId={`counts-${axis}-blocks`}
          value={value.blocks}
          onChange={(blocks) => onChange({ ...value, blocks })}
        />
        <span className="cf-counts__times">blocks x</span>
        <CountStepper
          label={`squares per block ${axis}`}
          testId={`counts-${axis}-squares`}
          value={value.squaresPerBlock}
          onChange={(squaresPerBlock) => onChange({ ...value, squaresPerBlock })}
        />
        <span className="cf-counts__times">squares</span>
      </div>
      <p className="cf-counts__total" data-testid={`counts-${axis}-total`}>
        {axisLabel(value)}
      </p>
    </fieldset>
  );
}

interface Props {
  across: AxisCount;
  down: AxisCount;
  onChange: (across: AxisCount, down: AxisCount) => void;
  /** Starts marking one square to seed the counts; absent hides the button. */
  onMeasure?: () => void;
}

export function CountsPanel({ across, down, onChange, onMeasure }: Props) {
  return (
    <section className="cf-counts" aria-label="Counts">
      <AxisRow axis="across" value={across} onChange={(next) => onChange(next, down)} />
      <AxisRow axis="down" value={down} onChange={(next) => onChange(across, next)} />
      {onMeasure && (
        <button type="button" className="cf-btn" data-testid="measure-square" onClick={onMeasure}>
          Count from one square
        </button>
      )}
    </section>
  );
}
