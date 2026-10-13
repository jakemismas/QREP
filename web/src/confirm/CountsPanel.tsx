/**
 * Counts in quilter units (C3a, issue #149; plan section 2.1): blocks across
 * x squares per block, and blocks down x squares per block, typed or with
 * steppers, with the total shown, for example "8 blocks x 5 squares = 40
 * squares". A quilt with no repeating block uses one block per axis.
 */
import { useEffect, useState } from "react";
import { axisLabel, COUNT_MAX, parseCount, type AxisCount } from "./counts";
import "./confirm.css";

/** A stepper press is one entry; typing is several, settled when the field is left or Enter is pressed. */
export type CountInput = "step" | "type";

interface StepperProps {
  label: string;
  value: number;
  testId: string;
  onChange: (value: number, input: CountInput) => void;
  onSettle?: () => void;
}

/** A whole-number field with minus and plus buttons; a typed value applies once it is valid. */
export function CountStepper({ label, value, testId, onChange, onSettle }: StepperProps) {
  const [text, setText] = useState(String(value));
  useEffect(() => setText(String(value)), [value]);
  const set = (next: number) => onChange(Math.min(COUNT_MAX, Math.max(1, next)), "step");
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
          if (parsed !== null) onChange(parsed, "type");
        }}
        onBlur={() => {
          setText(String(value));
          onSettle?.();
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") onSettle?.();
        }}
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
  onChange: (value: AxisCount, input: CountInput) => void;
  onSettle?: () => void;
}

function AxisRow({ axis, value, onChange, onSettle }: AxisProps) {
  return (
    <fieldset className="cf-counts__axis">
      <legend className="cf-counts__legend">{axis === "across" ? "Across" : "Down"}</legend>
      <div className="cf-counts__row">
        <CountStepper
          label={`blocks ${axis}`}
          testId={`counts-${axis}-blocks`}
          value={value.blocks}
          onChange={(blocks, input) => onChange({ ...value, blocks }, input)}
          onSettle={onSettle}
        />
        <span className="cf-counts__times">blocks x</span>
        <CountStepper
          label={`squares per block ${axis}`}
          testId={`counts-${axis}-squares`}
          value={value.squaresPerBlock}
          onChange={(squaresPerBlock, input) => onChange({ ...value, squaresPerBlock }, input)}
          onSettle={onSettle}
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
  onChange: (across: AxisCount, down: AxisCount, input: CountInput) => void;
  /** A typed count is final: its field was left, or Enter was pressed. */
  onSettle?: () => void;
  /** Starts marking one square to seed the counts; absent hides the button. */
  onMeasure?: () => void;
}

export function CountsPanel({ across, down, onChange, onSettle, onMeasure }: Props) {
  return (
    <section className="cf-counts" aria-label="Counts">
      <AxisRow axis="across" value={across} onChange={(next, input) => onChange(next, down, input)} onSettle={onSettle} />
      <AxisRow axis="down" value={down} onChange={(next, input) => onChange(across, next, input)} onSettle={onSettle} />
      {onMeasure && (
        <button type="button" className="cf-btn" data-testid="measure-square" onClick={onMeasure}>
          Count from one square
        </button>
      )}
    </section>
  );
}
