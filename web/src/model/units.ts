/**
 * Integer-eighths units, mirroring qrep/model/units.py exactly. All lengths
 * in the model JSON are integer eighths of an inch; this module is the only
 * place eighths become display strings in the UI. Parity is pinned by the
 * shared fixture tests/fixtures/fraction_display.json on both sides.
 */

export const EIGHTHS_PER_INCH = 8;

function gcd(a: number, b: number): number {
  while (b !== 0) {
    [a, b] = [b, a % b];
  }
  return a;
}

export function formatEighths(eighths: number): string {
  const sign = eighths < 0 ? "-" : "";
  const abs = Math.abs(eighths);
  const whole = Math.floor(abs / EIGHTHS_PER_INCH);
  const rem = abs % EIGHTHS_PER_INCH;
  let body: string;
  if (rem === 0) {
    body = String(whole);
  } else {
    const g = gcd(rem, EIGHTHS_PER_INCH);
    const num = rem / g;
    const den = EIGHTHS_PER_INCH / g;
    body = whole === 0 ? `${num}/${den}` : `${whole} ${num}/${den}`;
  }
  return `${sign}${body}"`;
}
