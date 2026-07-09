/**
 * Forgiving fraction-input grammar (S4, issue #44; PARITY item 13).
 * Accepts plain inches, mixed fractions, exact-eighth decimals, unicode
 * vulgar fractions, and an optional trailing inch mark (" or in). Returns
 * integer eighths, or null when the text is not a valid non-negative
 * eighths length - callers restore the prior value and show the toast.
 */

const UNICODE_FRACTIONS: Record<string, number> = {
  "¼": 2, // 1/4
  "½": 4, // 1/2
  "¾": 6, // 3/4
  "⅛": 1, // 1/8
  "⅜": 3, // 3/8
  "⅝": 5, // 5/8
  "⅞": 7, // 7/8
};

export function parseFractionInput(text: string): number | null {
  let s = text.trim().toLowerCase();
  if (s === "") return null;
  // Optional inch suffix.
  s = s.replace(/\s*(?:"|”|in(?:ch(?:es)?)?)$/u, "");
  if (s === "") return null;

  // Unicode vulgar fraction, optionally after a whole number.
  const unicodeMatch = s.match(/^(\d+)?\s*([¼½¾⅛-⅞])$/u);
  if (unicodeMatch) {
    const whole = unicodeMatch[1] ? Number(unicodeMatch[1]) : 0;
    return whole * 8 + UNICODE_FRACTIONS[unicodeMatch[2]];
  }

  // Mixed fraction "W N/D" or bare "N/D".
  const fractionMatch = s.match(/^(?:(\d+)\s+)?(\d+)\s*\/\s*(\d+)$/);
  if (fractionMatch) {
    const whole = fractionMatch[1] ? Number(fractionMatch[1]) : 0;
    const num = Number(fractionMatch[2]);
    const den = Number(fractionMatch[3]);
    if (den === 0 || 8 % den !== 0) return null;
    return whole * 8 + num * (8 / den);
  }

  // Decimal or integer inches; only exact eighths are valid.
  if (/^\d+(?:\.\d+)?$/.test(s)) {
    const eighths = Number(s) * 8;
    return Number.isInteger(eighths) ? eighths : null;
  }

  return null;
}
