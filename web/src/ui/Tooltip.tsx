/**
 * Tooltip wrapper (S2). Hover-only, one short sentence, dark in both themes.
 * Suppressed under 720px and on coarse pointers (media query in tokens.css) —
 * never hide required information here.
 */
import type { ReactNode } from "react";

export function Tooltip({ tip, children }: { tip: string; children: ReactNode }) {
  return (
    <span className="q-tip-wrap">
      {children}
      <span className="q-tip" role="tooltip" data-noprint>
        {tip}
      </span>
    </span>
  );
}
