/**
 * The loupe (C3a, issue #149; ux-12): a magnified view of the photo under the
 * pin being dragged, with a crosshair on the pin, so a finger never hides the
 * corner it is placing. It sits in the stage's top left corner, or its top
 * right when the pin itself is in the top left quarter.
 */
import { useEffect, useRef } from "react";
import type { Point } from "../engine/contract";
import type { Size } from "./geometry";

/** The loupe shows the photo at this many times its size on screen. */
export const LOUPE_MAGNIFICATION = 3;
const LOUPE_CSS_PX = 128;

interface Props {
  image: HTMLImageElement | null;
  point: Point;
  canvas: Size;
  side: "left" | "right";
}

export function Loupe({ image, point, canvas, side }: Props) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const target = ref.current;
    const ctx = target?.getContext("2d");
    if (!target || !ctx || !image || !image.naturalWidth) return;
    const ratio = window.devicePixelRatio || 1;
    const size = Math.round(LOUPE_CSS_PX * ratio);
    if (target.width !== size) {
      target.width = size;
      target.height = size;
    }
    // Screen pixels per canvas pixel at the current zoom, then the span of
    // canvas pixels that fills the loupe at its magnification.
    const shown = image.getBoundingClientRect().width / canvas.width;
    const span = LOUPE_CSS_PX / (shown * LOUPE_MAGNIFICATION);
    // The img element may be a downsized copy: draw from its own pixels.
    const toNatural = image.naturalWidth / canvas.width;
    const sx = (point.x - span / 2) * toNatural;
    const sy = (point.y - span / 2) * toNatural;
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, size, size);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(image, sx, sy, span * toNatural, span * toNatural, 0, 0, size, size);
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 3 * ratio;
    ctx.beginPath();
    ctx.moveTo(size / 2, 0);
    ctx.lineTo(size / 2, size);
    ctx.moveTo(0, size / 2);
    ctx.lineTo(size, size / 2);
    ctx.stroke();
    ctx.strokeStyle = "#c0392b";
    ctx.lineWidth = 1 * ratio;
    ctx.stroke();
  }, [image, point, canvas]);

  return (
    <canvas
      ref={ref}
      className="cf-loupe"
      data-testid="loupe"
      data-side={side}
      style={{ width: LOUPE_CSS_PX, height: LOUPE_CSS_PX }}
      aria-hidden="true"
    />
  );
}
