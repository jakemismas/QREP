/*
 * The confirm screen (photo.state === "crop"; C3b, issue #101): the decoded
 * photo with four corner pins, the live grid, the frame choice, border bands
 * and counts, built from C3a's components (web/src/confirm/). The pins start
 * at a neutral inset and nothing is detected for you (criteria U3-4).
 * Continue stages the confirmed crop; "Adjust the crop" on results returns
 * here with the confirmed frame kept.
 */
import { useLayoutEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import type { Point } from "../../engine/contract";
import { bandHandles, roundWidth, widthFromHandle, type BandSide } from "../../confirm/bands";
import { BandsControl } from "../../confirm/BandsControl";
import { CountsPanel } from "../../confirm/CountsPanel";
import { totalSquares } from "../../confirm/counts";
import {
  CORNER_LABELS,
  CORNER_NAMES,
  cornersToQuad,
  quadProblem,
  type CornerName,
  type FrameMode,
} from "../../confirm/frame";
import { squareToQuad } from "../../confirm/geometry";
import { GridOverlay } from "../../confirm/GridOverlay";
import { PinLayer, type PinSpec } from "../../confirm/PinLayer";
import type { PhotoApi } from "../photoApi";
import { SizeBlock } from "./SizeBlock";
import "./shared.css";
import "./CropScreen.css";

// The photo's share of the height: what is left of the window below the
// photo's top, less the action bar, the grid gap above it (CropScreen.css
// .pf-confirm gap) and a margin under it. CropScreen.css subtracts PinLayer's
// own chrome (its stage padding and the zoom row) from this.
const ROW_GAP_PX = 14;
const BOTTOM_MARGIN_PX = 12;
// A short landscape window still gets a photo worth pinning; the page scrolls.
const MIN_AVAILABLE_PX = 240;

/** The element's top in document pixels, transforms ignored (the screen fades in). */
function documentTop(el: HTMLElement): number {
  let top = 0;
  for (let node: HTMLElement | null = el; node; node = node.offsetParent as HTMLElement | null) {
    top += node.offsetTop;
  }
  return top;
}

const BAND_SIDES: BandSide[] = ["top", "right", "bottom", "left"];

export function CropScreen({ photo }: { photo: PhotoApi }) {
  const confirm = photo.confirm;
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activeBand, setActiveBand] = useState<number | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const headRef = useRef<HTMLDivElement>(null);
  const photoRef = useRef<HTMLDivElement>(null);
  const barRef = useRef<HTMLDivElement>(null);

  // Written straight to the root's style, so a resize re-lays out the photo
  // without a React render.
  useLayoutEffect(() => {
    const root = rootRef.current;
    const box = photoRef.current;
    const bar = barRef.current;
    if (!root || !box || !bar) return;
    const measure = () => {
      const available = window.innerHeight - documentTop(box) - bar.offsetHeight - ROW_GAP_PX - BOTTOM_MARGIN_PX;
      root.style.setProperty("--pf-avail", `${Math.max(MIN_AVAILABLE_PX, Math.floor(available))}px`);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(bar);
    if (headRef.current) observer.observe(headRef.current);
    const header = document.querySelector(".qrep-header");
    if (header) observer.observe(header);
    window.addEventListener("resize", measure);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, []);

  const size = confirm.size;
  const corners = confirm.corners;
  // Bound to this render's photo, so a late load of an older photo's img changes nothing.
  const seq = confirm.seq;
  const outer = confirm.mode === "outer_edge";
  const bands = useMemo(() => (outer ? confirm.bands : []), [outer, confirm.bands]);
  const problem = corners ? quadProblem(corners) : null;
  const homography = useMemo(
    () => (corners && !problem ? squareToQuad(cornersToQuad(corners)) : null),
    [corners, problem],
  );
  const cols = totalSquares(confirm.across);
  const rows = totalSquares(confirm.down);
  const band = outer && activeBand !== null && activeBand < bands.length ? activeBand : null;

  const pins: PinSpec[] = [];
  if (corners) {
    CORNER_NAMES.forEach((name, i) => {
      pins.push({
        id: `corner.${name}`,
        testId: `corner-pin-${i}`,
        point: corners[name],
        label: `${outer ? "Outer edge" : "Field"}, ${CORNER_LABELS[name]}`,
        tone: outer ? "corner" : "field",
      });
    });
  }
  if (homography && band !== null) {
    const handles = bandHandles(homography, cols, rows, bands, band);
    for (const side of BAND_SIDES) {
      pins.push({ id: `band.${side}`, point: handles[side], label: `Band ${band + 1} inner line, ${side}`, tone: "band" });
    }
  }

  const onMove = (id: string, point: Point) => {
    const [set, part] = id.split(".");
    if (set === "corner") {
      confirm.setCorner(part as CornerName, point);
    } else if (set === "band" && homography && band !== null) {
      // A handle past the center or off the edge gives no width; the band keeps its last one.
      const width = widthFromHandle(homography, part as BandSide, point, cols, rows, bands, band);
      if (width !== null) {
        confirm.setBands(bands.map((b, i) => (i === band ? { width_squares: roundWidth(width) } : b)));
      }
    }
  };

  const changeMode = (mode: FrameMode) => {
    confirm.setMode(mode);
    setActiveBand(null);
  };

  // Crossed or folded pins block Continue; say why next to it.
  const blockedByPins = confirm.status === "ready" && !confirm.staging ? confirm.blocked : null;
  const photoStyle = size ? ({ "--pf-aspect": size.width / size.height } as CSSProperties) : undefined;

  return (
    <div
      ref={rootRef}
      className="pf-confirm"
      data-testid="crop-screen"
      data-screen-label="Confirm the corners and squares"
      data-canvas-width={size?.width}
      data-canvas-height={size?.height}
      data-frame-mode={confirm.mode}
      data-status={confirm.status}
    >
      <div ref={headRef} className="pf-confirm__head">
        <h1 className="pf-h1 pf-h1--sm">Pin the corners and count the squares</h1>
        <p className="pf-confirm__lede">
          {size
            ? "Drag each pin onto a corner of the quilt, then set the counts until the grid lines sit on the seams."
            : "There is no photo to pin here. Go back and choose a photo."}
        </p>
      </div>

      <div ref={photoRef} className="pf-confirm__photo" style={photoStyle}>
        {size && photo.photoUrl ? (
          <PinLayer
            src={photo.photoUrl}
            canvas={size}
            pins={pins}
            activeId={activeId}
            onActivate={setActiveId}
            onMove={onMove}
            onImageLoad={(natural) => confirm.displayLoaded(seq, natural)}
            onImageError={() => confirm.displayFailed(seq)}
            overlay={
              homography ? (
                <GridOverlay
                  homography={homography}
                  across={confirm.across}
                  down={confirm.down}
                  bands={bands}
                  activeBand={band}
                />
              ) : null
            }
          />
        ) : null}
      </div>

      {size ? (
        <div className="pf-confirm__side">
          {/* Inert while Continue stages: a change made now could not reach
              the read in flight, yet would show afterwards as if read. */}
          <fieldset className="pf-confirm__controls" disabled={confirm.staging}>
            <section className="pf-confirm__group" aria-labelledby="pf-confirm-frame">
              <h2 className="pf-confirm__h2" id="pf-confirm-frame">
                Frame
              </h2>
              <label className="pf-confirm__field">
                <span>The pins mark</span>
                <select
                  className="pf-confirm__select"
                  data-testid="frame-mode"
                  value={confirm.mode}
                  onChange={(e) => changeMode(e.target.value as FrameMode)}
                >
                  <option value="outer_edge">The outer edge, with any borders</option>
                  <option value="field">The corners of the pieced field, no border</option>
                </select>
              </label>
            </section>

            <section className="pf-confirm__group" aria-labelledby="pf-confirm-counts">
              <h2 className="pf-confirm__h2" id="pf-confirm-counts">
                Squares
              </h2>
              <CountsPanel
                across={confirm.across}
                down={confirm.down}
                onChange={(across, down) => confirm.setCounts(across, down)}
              />
            </section>

            {outer ? (
              <section className="pf-confirm__group" aria-labelledby="pf-confirm-bands">
                <h2 className="pf-confirm__h2" id="pf-confirm-bands">
                  Borders
                </h2>
                <BandsControl
                  bands={confirm.bands}
                  onChange={confirm.setBands}
                  activeBand={band}
                  onSelect={setActiveBand}
                  squareEighths={confirm.squareEighths}
                />
              </section>
            ) : null}

            <SizeBlock photo={photo} />
          </fieldset>
        </div>
      ) : null}

      <div ref={barRef} className="pf-confirm__bar" data-testid="confirm-bar">
        {blockedByPins ? (
          <p className="pf-confirm__blocked" data-testid="crop-blocked" role="status">
            {blockedByPins}
          </p>
        ) : null}
        <div className="pf-confirm__actions">
          <button
            type="button"
            className="pf-btn pf-btn--secondary"
            data-testid="crop-back"
            onClick={() => photo.backFromCrop()}
          >
            Back
          </button>
          <button
            type="button"
            className="pf-btn pf-btn--primary"
            data-testid="crop-analyze"
            disabled={!confirm.canContinue}
            aria-busy={confirm.staging || undefined}
            onClick={() => void photo.analyze()}
          >
            {confirm.staging ? <span className="pf-stage-spin pf-confirm__spin" aria-hidden="true" /> : null}
            Continue
          </button>
        </div>
      </div>
    </div>
  );
}
