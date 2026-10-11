/*
 * The draggable pin and quad overlay (S2: one pin surface, one behavior),
 * extracted from the retired corner editor so the crop screen and any future
 * pin surface share it.
 */
import { useRef } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import "./shared.css";
import "./PinOverlay.css";

function quadPath(corners: [number, number][]): string {
  const pts = corners.map(([x, y]) => `${(x * 100).toFixed(2)} ${(y * 100).toFixed(2)}`);
  return `M${pts[0]}L${pts[1]}L${pts[2]}L${pts[3]}Z`;
}

/** Pin drag is pure JS: it never waits on the engine (cold-start contract). */
export function PinOverlay({
  photoUrl,
  corners,
  onMovePin,
}: {
  photoUrl: string | null;
  corners: [number, number][];
  onMovePin: (index: number, xy: [number, number]) => void;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const activeRef = useRef<number | null>(null);

  const onDown = (i: number) => (e: ReactPointerEvent<HTMLButtonElement>) => {
    activeRef.current = i;
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {
      /* capture is best-effort */
    }
  };
  const onMove = (e: ReactPointerEvent<HTMLButtonElement>) => {
    const i = activeRef.current;
    if (i == null) return;
    const box = boxRef.current?.getBoundingClientRect();
    if (!box || box.width < 2 || box.height < 2) return;
    const x = Math.min(1, Math.max(0, (e.clientX - box.left) / box.width));
    const y = Math.min(1, Math.max(0, (e.clientY - box.top) / box.height));
    onMovePin(i, [Number(x.toFixed(4)), Number(y.toFixed(4))]);
  };
  const onUp = (e: ReactPointerEvent<HTMLButtonElement>) => {
    activeRef.current = null;
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      /* release is best-effort */
    }
  };

  return (
    <div className="pf-corner-stage">
      <div className="pf-corner-box" ref={boxRef}>
        {photoUrl ? (
          <img className="pf-corner-img" src={photoUrl} alt="Your uploaded quilt" />
        ) : (
          <div className="pf-corner-img pf-photo--gone">Photo cleared</div>
        )}
        <svg className="pf-corner-quad" viewBox="0 0 100 100" preserveAspectRatio="none">
          <path d={quadPath(corners)} />
        </svg>
        {corners.map((c, i) => (
          <button
            key={i}
            type="button"
            className="pf-pin"
            data-testid={`corner-pin-${i}`}
            aria-label={`Corner ${i + 1}`}
            style={{ left: `${c[0] * 100}%`, top: `${c[1] * 100}%` }}
            onPointerDown={onDown(i)}
            onPointerMove={onMove}
            onPointerUp={onUp}
            onPointerCancel={onUp}
          />
        ))}
      </div>
    </div>
  );
}
