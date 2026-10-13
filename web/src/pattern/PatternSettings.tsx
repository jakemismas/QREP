/**
 * The two fabric widths on Your pattern (C2b, issue #148): Fabric width for
 * cutting strips and Backing fabric width, MATH.md section 1.3's U and B,
 * with the 108 in wide back (BW) as a backing choice (J13). A change writes
 * the width into the model's settings and asks for the pattern again; the
 * engine does every computation with it. Each select shows the width in
 * force, which is the model's stored value until you change it (the
 * fixture stores 42 in for cutting until A6).
 */
import { BACKING_WIDTHS, STRIP_WIDTHS, inchText } from "./patternSize";
import type { WidthChoice, Widths } from "./patternSize";
import "./PatternSettings.css";

/** The offered widths, plus the width in force when the list lacks it. */
function options(choices: readonly WidthChoice[], current: number | null): WidthChoice[] {
  if (current === null || choices.some((choice) => choice.eighths === current)) {
    return [...choices];
  }
  return [...choices, { eighths: current, label: inchText(current), isDefault: false }];
}

function WidthField({
  testId,
  label,
  choices,
  value,
  disabled,
  onPick,
}: {
  testId: string;
  label: string;
  choices: readonly WidthChoice[];
  value: number | null;
  disabled: boolean;
  onPick: (eighths: number) => void;
}) {
  return (
    <label className="ps-field">
      <span className="ps-label">{label}</span>
      <select
        className="ps-select"
        data-testid={testId}
        value={value ?? ""}
        disabled={disabled || value === null}
        onChange={(event) => onPick(Number(event.target.value))}
      >
        {value === null ? <option value="">…</option> : null}
        {options(choices, value).map((choice) => (
          <option key={choice.eighths} value={choice.eighths}>
            {choice.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function PatternSettings({
  stripWidth,
  backingWidth,
  disabled,
  onChange,
}: {
  /** The width in force, in eighths: yours, else the pattern's; null until it lands. */
  stripWidth: number | null;
  backingWidth: number | null;
  disabled: boolean;
  onChange: (widths: Partial<Widths>) => void;
}) {
  return (
    <section className="ps-root" data-testid="pattern-settings">
      <h2 className="ps-title">Fabric widths</h2>
      <WidthField
        testId="strip-width"
        label="Fabric width for cutting strips"
        choices={STRIP_WIDTHS}
        value={stripWidth}
        disabled={disabled}
        onPick={(strip) => onChange({ strip })}
      />
      <WidthField
        testId="backing-width"
        label="Backing fabric width"
        choices={BACKING_WIDTHS}
        value={backingWidth}
        disabled={disabled}
        onPick={(backing) => onChange({ backing })}
      />
    </section>
  );
}
