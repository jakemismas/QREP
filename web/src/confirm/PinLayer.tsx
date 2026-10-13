/**
 * The photo with its pins (C3a, issue #149): drag a pin, nudge it with the
 * arrow keys, and pinch or use the zoom buttons to look closer.
 *
 * - Pins live in source-image pixels (canvas) and map through the img
 *   element's own rect (geometry.ts; ux-06). The rect already includes the
 *   zoom transform, so the mapping holds at any zoom.
 * - Each pin's hit area is 44 x 44 CSS px at every zoom (criteria U3-3;
 *   ux-12: 30 x 30 px pins), and each pin is a button, so a keyboard moves it
 *   too (web-16: pins worked only with a pointer).
 * - A one-finger drag moves a pin only when it starts on one; two fingers
 *   pinch to zoom and pan (Critique: CR-product-07).
 * - The loupe magnifies the area under the pin while you drag, because the
 *   finger hides it.
 */
import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from "react";
import type { Point } from "../engine/contract";
import { displayToSource, snapToPixel, sourceToDisplay, type Size } from "./geometry";
import { Loupe } from "./Loupe";
import "./confirm.css";

export type PinInput = "pointer" | "key";

export interface PinSpec {
  id: string;
  point: Point;
  /** Spoken name, for example "Outer edge, top left". */
  label: string;
  tone?: "corner" | "field" | "band" | "square";
}

interface Props {
  src: string;
  /** The pin space: source-image pixels. */
  canvas: Size;
  pins: PinSpec[];
  activeId: string | null;
  onActivate: (id: string) => void;
  onMove: (id: string, point: Point, input: PinInput) => void;
  /** A placement: the end of a drag, or one arrow-key nudge. */
  onPlace?: (id: string, point: Point, input: PinInput) => void;
  onImageLoad?: (natural: Size) => void;
  onImageError?: () => void;
  /** SVG content drawn in canvas coordinates over the photo. */
  overlay?: ReactNode;
}

interface View {
  scale: number;
  x: number;
  y: number;
}

interface Drag {
  id: string;
  pointerId: number;
  /** Pointer minus pin center, in client pixels, so the pin does not jump to the finger. */
  offset: Point;
  last: Point;
  moved: boolean;
}

interface Pinch {
  distance: number;
  mid: Point;
  view: View;
}

const ZOOM_MAX = 8;
const ZOOM_STEP = 1.5;
const FIT: View = { scale: 1, x: 0, y: 0 };

function clampView(view: View, width: number, height: number): View {
  const scale = Math.min(ZOOM_MAX, Math.max(1, view.scale));
  return {
    scale,
    x: Math.min(0, Math.max(width * (1 - scale), view.x)),
    y: Math.min(0, Math.max(height * (1 - scale), view.y)),
  };
}

/** The view after zooming to scale about a point in stage pixels. */
function zoomAbout(view: View, scale: number, about: Point, width: number, height: number): View {
  const content = { x: (about.x - view.x) / view.scale, y: (about.y - view.y) / view.scale };
  return clampView({ scale, x: about.x - content.x * scale, y: about.y - content.y * scale }, width, height);
}

const NUDGES: Record<string, Point> = {
  ArrowLeft: { x: -1, y: 0 },
  ArrowRight: { x: 1, y: 0 },
  ArrowUp: { x: 0, y: -1 },
  ArrowDown: { x: 0, y: 1 },
};

export function PinLayer({
  src,
  canvas,
  pins,
  activeId,
  onActivate,
  onMove,
  onPlace,
  onImageLoad,
  onImageError,
  overlay,
}: Props) {
  const stageRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const pointers = useRef(new Map<number, Point>());
  const drag = useRef<Drag | null>(null);
  const pinch = useRef<Pinch | null>(null);
  const [view, setView] = useState<View>(FIT);
  const [dragging, setDragging] = useState<string | null>(null);
  const viewRef = useRef(view);
  viewRef.current = view;

  // A new photo opens at the fit view.
  useEffect(() => setView(FIT), [src]);

  const pinPoint = useCallback((id: string) => pins.find((pin) => pin.id === id)?.point ?? null, [pins]);

  const toCanvas = (client: Point): Point | null => {
    const img = imgRef.current;
    if (!img) return null;
    const r = img.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return null;
    return snapToPixel(displayToSource(client, r, canvas), canvas);
  };

  const stageSize = () => {
    const r = stageRef.current?.getBoundingClientRect();
    return { left: r?.left ?? 0, top: r?.top ?? 0, width: r?.width ?? 0, height: r?.height ?? 0 };
  };

  const endDrag = (place: boolean) => {
    const current = drag.current;
    if (!current) return;
    drag.current = null;
    setDragging(null);
    // A tap that never moved the pin places nothing, so the drill logs only real placements.
    if (place && current.moved) onPlace?.(current.id, current.last, "pointer");
  };

  const startPinch = () => {
    const [a, b] = [...pointers.current.values()];
    const stage = stageSize();
    pinch.current = {
      distance: Math.max(1, Math.hypot(b.x - a.x, b.y - a.y)),
      mid: { x: (a.x + b.x) / 2 - stage.left, y: (a.y + b.y) / 2 - stage.top },
      view: viewRef.current,
    };
  };

  const handlePointerDown = (event: PointerEvent<HTMLDivElement>) => {
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pointers.current.size === 2) {
      // A second finger turns a drag into a pinch; the pin keeps where it got to.
      endDrag(true);
      startPinch();
      stageRef.current?.setPointerCapture(event.pointerId);
      return;
    }
    if (pointers.current.size !== 1) return;
    const pinEl = (event.target as Element).closest<HTMLElement>("[data-pin-id]");
    const id = pinEl?.dataset.pinId;
    const point = id ? pinPoint(id) : null;
    const img = imgRef.current;
    if (!id || !point || !img) return;
    event.preventDefault();
    const center = sourceToDisplay(point, img.getBoundingClientRect(), canvas);
    drag.current = {
      id,
      pointerId: event.pointerId,
      offset: { x: event.clientX - center.x, y: event.clientY - center.y },
      last: point,
      moved: false,
    };
    setDragging(id);
    onActivate(id);
    pinEl?.focus({ preventScroll: true });
    stageRef.current?.setPointerCapture(event.pointerId);
  };

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (!pointers.current.has(event.pointerId)) return;
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const current = drag.current;
    if (current && current.pointerId === event.pointerId) {
      const point = toCanvas({ x: event.clientX - current.offset.x, y: event.clientY - current.offset.y });
      if (point && (point.x !== current.last.x || point.y !== current.last.y)) {
        current.last = point;
        current.moved = true;
        onMove(current.id, point, "pointer");
      }
      return;
    }
    const start = pinch.current;
    if (start && pointers.current.size >= 2) {
      const [a, b] = [...pointers.current.values()];
      const stage = stageSize();
      const distance = Math.max(1, Math.hypot(b.x - a.x, b.y - a.y));
      const mid = { x: (a.x + b.x) / 2 - stage.left, y: (a.y + b.y) / 2 - stage.top };
      // The content point under the first midpoint follows the fingers' midpoint.
      const scale = Math.min(ZOOM_MAX, Math.max(1, (start.view.scale * distance) / start.distance));
      const content = { x: (start.mid.x - start.view.x) / start.view.scale, y: (start.mid.y - start.view.y) / start.view.scale };
      setView(clampView({ scale, x: mid.x - content.x * scale, y: mid.y - content.y * scale }, stage.width, stage.height));
    }
  };

  const handlePointerEnd = (event: PointerEvent<HTMLDivElement>) => {
    pointers.current.delete(event.pointerId);
    if (drag.current?.pointerId === event.pointerId) endDrag(event.type === "pointerup");
    if (pointers.current.size < 2) pinch.current = null;
  };

  const handleKeyDown = (id: string, event: KeyboardEvent<HTMLButtonElement>) => {
    const nudge = NUDGES[event.key];
    const point = pinPoint(id);
    if (!nudge || !point) return;
    event.preventDefault();
    const step = event.shiftKey ? 10 : 1;
    const next = snapToPixel({ x: point.x + nudge.x * step, y: point.y + nudge.y * step }, canvas);
    onMove(id, next, "key");
    onPlace?.(id, next, "key");
  };

  const zoomBy = (factor: number) => {
    const stage = stageSize();
    const center = { x: stage.width / 2, y: stage.height / 2 };
    setView((v) => zoomAbout(v, v.scale * factor, center, stage.width, stage.height));
  };

  const dragPoint = dragging ? pinPoint(dragging) : null;
  const loupeSide = dragPoint && dragPoint.x < canvas.width / 2 && dragPoint.y < canvas.height / 2 ? "right" : "left";

  return (
    <div className="cf-pins">
      <div
        ref={stageRef}
        className="cf-pins__stage"
        data-testid="pin-stage"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerEnd}
        onPointerCancel={handlePointerEnd}
      >
        <div
          className="cf-pins__view"
          data-testid="pin-view"
          data-scale={view.scale.toFixed(3)}
          style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})` }}
        >
          <img
            ref={imgRef}
            className="cf-pins__img"
            src={src}
            alt="The quilt photo"
            draggable={false}
            data-testid="pin-image"
            onLoad={(e) => onImageLoad?.({ width: e.currentTarget.naturalWidth, height: e.currentTarget.naturalHeight })}
            onError={() => onImageError?.()}
          />
          <svg
            className="cf-pins__overlay"
            viewBox={`0 0 ${canvas.width} ${canvas.height}`}
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            {overlay}
          </svg>
          {pins.map((pin) => (
            <button
              key={pin.id}
              type="button"
              className="cf-pin"
              data-pin-id={pin.id}
              data-testid={`pin-${pin.id}`}
              data-tone={pin.tone ?? "corner"}
              data-x={pin.point.x}
              data-y={pin.point.y}
              aria-label={`${pin.label}, at ${pin.point.x}, ${pin.point.y}. Arrow keys move it.`}
              aria-pressed={pin.id === activeId}
              style={{
                left: `${(pin.point.x / canvas.width) * 100}%`,
                top: `${(pin.point.y / canvas.height) * 100}%`,
                transform: `translate(-50%, -50%) scale(${1 / view.scale})`,
              }}
              onFocus={() => onActivate(pin.id)}
              onKeyDown={(e) => handleKeyDown(pin.id, e)}
            />
          ))}
        </div>
        {dragPoint && (
          <Loupe image={imgRef.current} point={dragPoint} canvas={canvas} side={loupeSide} />
        )}
      </div>
      <div className="cf-pins__zoom" role="group" aria-label="Zoom">
        <button type="button" className="cf-btn" onClick={() => zoomBy(1 / ZOOM_STEP)} disabled={view.scale <= 1}>
          Zoom out
        </button>
        <button type="button" className="cf-btn" onClick={() => setView(FIT)} disabled={view.scale === 1}>
          Fit
        </button>
        <button type="button" className="cf-btn" onClick={() => zoomBy(ZOOM_STEP)} disabled={view.scale >= ZOOM_MAX}>
          Zoom in
        </button>
      </div>
    </div>
  );
}
