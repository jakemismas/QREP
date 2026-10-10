/**
 * Tooltip wrapper (S2). Hover or focus, one short sentence, dark in both themes.
 * Suppressed under 720px and on coarse pointers (media query in tokens.css) —
 * never hide required information here.
 *
 * The tip exists only while open: a hidden tip that stayed in the DOM still
 * widened the page (ux-17: a header tip ended at x 1486 on a 1440 px page).
 * It is fixed-positioned and clamped inside the viewport, because a control
 * near the edge would otherwise push half of a centered tip off the screen.
 */
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";

// The mock's gap between a control and its tip (MOCK-NOTES.md, tooltip section).
const GAP_PX = 9;
// The nearest a tip comes to a viewport edge.
const EDGE_PX = 8;

export function Tooltip({
  tip,
  children,
  placement = "above",
  className,
}: {
  tip: string;
  children: ReactNode;
  placement?: "above" | "below";
  className?: string;
}) {
  const wrapRef = useRef<HTMLSpanElement>(null);
  const tipRef = useRef<HTMLSpanElement>(null);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<{ left: number; top: number } | null>(null);

  useLayoutEffect(() => {
    if (!open || !wrapRef.current || !tipRef.current) return;
    const anchor = wrapRef.current.getBoundingClientRect();
    const box = tipRef.current.getBoundingClientRect();
    const viewWidth = document.documentElement.clientWidth;
    const centered = anchor.left + anchor.width / 2 - box.width / 2;
    const left = Math.max(EDGE_PX, Math.min(centered, viewWidth - box.width - EDGE_PX));
    const above = anchor.top - GAP_PX - box.height;
    const below = anchor.bottom + GAP_PX;
    // An "above" tip with no room above its control opens below instead.
    const top = placement === "below" || above < EDGE_PX ? below : above;
    setPosition({ left, top });
  }, [open, placement, tip]);

  return (
    <span
      ref={wrapRef}
      className={className ? `q-tip-wrap ${className}` : "q-tip-wrap"}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {children}
      {open ? (
        <span
          ref={tipRef}
          className="q-tip"
          role="tooltip"
          data-noprint
          style={position ? { left: position.left, top: position.top } : undefined}
        >
          {tip}
        </span>
      ) : null}
    </span>
  );
}
