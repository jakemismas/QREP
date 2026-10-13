/**
 * Your pattern (C2a, issue #96; SPEC.md section 2.1, screen 4): the quilt
 * true to scale beside the photo it was read from (stacked below it under
 * 720 px), the method in one line, the one pattern PDF, the flagged squares
 * and the fabric census. The sample pattern has no photo: the quilt shows
 * alone, with no Compare and no flagged line.
 *
 * One layout serves every width (web-17, ux-22): on a phone the heading,
 * method and PDF button come first, so the button is on screen without
 * scrolling; from 720 px the photo-and-quilt row sticks under the header while
 * the details scroll beneath it, and on a wide desktop the photo and quilt
 * form a sticky media column that stays in view while the side column
 * scrolls. A one-finger drag on the quilt scrolls the page while the quilt is
 * at Fit and pans it once zoomed:
 * the stylesheet relaxes QuiltCanvas's touch-action under data-zoomed
 * "false", which this screen keeps in step with the canvas's zoom label.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import type { RefObject } from "react";
import type { PatternSummary } from "../engine/contract";
import { useEngineStatus } from "../engine/engineStatus";
import { Lightbox } from "../shell/photo/Lightbox";
import type { LbTab } from "../shell/photo/Lightbox";
import { useModel } from "../state/model";
import { useYourPattern } from "../state/pattern";
import { usePhoto } from "../state/photo";
import { QuiltCanvas } from "../viewer";
import { FabricCensus } from "./FabricCensus";
import { readFlags } from "./flags";
import { FlaggedOverlay } from "./FlaggedOverlay";
import { MethodLine } from "./MethodLine";
import { PatternPdfButton } from "./PatternPdfButton";
import { patternError } from "./patternError";
import type { SummaryView } from "./patternPdf";
import { PatternSettings } from "./PatternSettings";
import { canvasModel, sizeLine } from "./patternSize";
import { ShoppingLines } from "./ShoppingLines";
import { SizeControl } from "./SizeControl";
import "./YourPatternScreen.css";

/** Tracks whether the quilt view has left Fit, from QuiltCanvas's zoom label,
 * and keeps a one-finger drag at Fit for the page. */
function useZoomed(rootRef: RefObject<HTMLElement | null>, mounted: boolean): boolean {
  const [zoomed, setZoomed] = useState(false);
  useEffect(() => {
    const label = rootRef.current?.querySelector(".qc-zlabel");
    if (!label) return;
    // The label reads exactly "Fit" while the view is fitted; any zoom or pan
    // replaces it with a percentage.
    const sync = () => setZoomed(label.textContent !== "Fit");
    sync();
    const observer = new MutationObserver(sync);
    observer.observe(label, { childList: true, characterData: true, subtree: true });
    return () => observer.disconnect();
  }, [rootRef, mounted]);

  // At Fit the browser scrolls the page for a one-finger drag, but the moves
  // before it takes over still reach QuiltCanvas, which would pan the quilt
  // off Fit and turn every later drag into a pan. A capture listener on the
  // wrapper keeps those moves from the canvas; two fingers still pinch.
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const touches = new Set<number>();
    const down = (event: PointerEvent) => {
      if (event.pointerType === "touch") touches.add(event.pointerId);
    };
    const up = (event: PointerEvent) => {
      touches.delete(event.pointerId);
    };
    const move = (event: PointerEvent) => {
      if (event.pointerType === "touch" && touches.size === 1 && root.dataset.zoomed === "false") {
        event.stopPropagation();
      }
    };
    root.addEventListener("pointerdown", down, true);
    root.addEventListener("pointerup", up, true);
    root.addEventListener("pointercancel", up, true);
    root.addEventListener("pointermove", move, true);
    return () => {
      root.removeEventListener("pointerdown", down, true);
      root.removeEventListener("pointerup", up, true);
      root.removeEventListener("pointercancel", up, true);
      root.removeEventListener("pointermove", move, true);
    };
  }, [rootRef, mounted]);

  return zoomed;
}

/** The summary to show: the newest one, kept on screen while a new size or
 * width asks for the next, so the details do not blank out on each change.
 * A failure or another quilt drops it. */
function useShownSummary(view: SummaryView): { shown: PatternSummary | null; updating: boolean } {
  const last = useRef<PatternSummary | null>(null);
  if (view.status === "ready") last.current = view.summary;
  else if (view.status !== "loading") last.current = null;
  return { shown: last.current, updating: view.status === "loading" && last.current !== null };
}

export function YourPatternScreen() {
  const { model, summary: census, censusFailed } = useModel();
  const photo = usePhoto();
  const pattern = useYourPattern();
  const engineStatus = useEngineStatus();
  const [showFlags, setShowFlags] = useState(true);
  const [lightbox, setLightbox] = useState<LbTab | null>(null);
  const quiltRef = useRef<HTMLElement>(null);

  const flags = useMemo(() => readFlags(pattern.source, photo.result), [pattern.source, photo.result]);
  const zoomed = useZoomed(quiltRef, model !== null);
  const { shown, updating } = useShownSummary(pattern.summary);

  // The screen it replaces may have been scrolled; Your pattern opens at the
  // top, where the PDF button is.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  if (model === null) return null;

  // The read's own model carries the cell confidences the outlines need; a
  // size you set redraws the quilt at that size, true to scale.
  const quiltModel = canvasModel(pattern.sizer.sized?.model ?? null, model, flags.model);
  const photoUrl = pattern.source === "photo" ? photo.photoUrl : null;
  const showFlagged = flags.model !== null;
  const { summary, pdf } = pattern;

  // Your pattern opens a quilt fresh, which drops the old census, so a null
  // census that has not failed is one still to land.
  const censusState = censusFailed ? "failed" : census === null ? "waiting" : "ready";
  const error = patternError(engineStatus.phase === "failed", summary, pdf, censusState);
  const retryAction = error?.retry ?? null;
  const retry = retryAction !== null ? () => pattern.retry(retryAction) : null;

  return (
    <div
      className="yp-root"
      data-testid="your-pattern"
      data-source={pattern.source}
      data-screen-label="Your pattern"
    >
      <section className="yp-head">
        <h1 className="yp-title">Your pattern</h1>
        {/* Beside a stalled engine a working line would say the wait goes on;
            a failed PDF leaves the summary's own call running. */}
        <MethodLine summary={summary} working={error?.retry !== "engine"} />
        {/* With the engine down the PDF waits on Retry, so no spinner. */}
        <PatternPdfButton
          pdf={pdf}
          working={error?.retry !== "engine"}
          onSave={pattern.savePdf}
        />
        {error !== null ? (
          <div className="yp-error" role="alert" data-testid="pattern-error">
            <p className="yp-error-text">{error.message}</p>
            {retry !== null ? (
              <button
                type="button"
                className="btn btn--secondary yp-retry"
                data-testid="pattern-retry"
                onClick={retry}
              >
                Retry
              </button>
            ) : null}
          </div>
        ) : null}
      </section>

      <section className={photoUrl ? "yp-media yp-media--pair" : "yp-media"}>
        {photoUrl ? (
          <figure className="yp-figure" data-testid="pattern-photo">
            <figcaption className="yp-eyebrow">Your photo</figcaption>
            <img className="yp-photo-img" src={photoUrl} alt="Your quilt photo" />
            <button
              type="button"
              className="btn btn--secondary yp-compare"
              data-testid="open-lightbox"
              onClick={() => setLightbox("side")}
            >
              Compare with your photo
            </button>
          </figure>
        ) : null}
        <figure
          className="yp-figure yp-quilt"
          data-testid="pattern-quilt"
          data-zoomed={zoomed ? "true" : "false"}
          ref={quiltRef}
        >
          {photoUrl ? <figcaption className="yp-eyebrow">Recovered quilt</figcaption> : null}
          <QuiltCanvas model={quiltModel} showUncertain={showFlagged && showFlags} />
        </figure>
      </section>

      <section className="yp-details">
        {showFlagged ? (
          <FlaggedOverlay
            count={flags.count}
            shown={showFlags}
            onToggle={() => setShowFlags((value) => !value)}
          />
        ) : null}
        <SizeControl
          line={
            shown !== null
              ? sizeLine(
                  pattern.model ?? model,
                  { width: shown.finished_width, height: shown.finished_height },
                  pattern.sizer.sized,
                  pattern.source,
                )
              : null
          }
          presets={pattern.presets}
          status={pattern.sizer.status}
          message={pattern.sizer.message}
          onSize={pattern.setSize}
        />
        {shown !== null ? (
          <div className="yp-amounts" aria-busy={updating}>
            <FabricCensus
              lines={shown.fabrics}
              palette={model.palette.fabrics}
              census={census}
              countFailed={censusFailed}
            />
            <ShoppingLines summary={shown} />
          </div>
        ) : null}
        <PatternSettings
          stripWidth={pattern.widths.strip ?? shown?.strip_width ?? null}
          backingWidth={pattern.widths.backing ?? shown?.backing_width ?? null}
          disabled={shown === null}
          onChange={pattern.setWidths}
        />
      </section>

      {lightbox !== null ? (
        <Lightbox
          photoUrl={photoUrl}
          model={quiltModel}
          tab={lightbox}
          onTab={setLightbox}
          onClose={() => setLightbox(null)}
          showUncertain={showFlagged && showFlags}
        />
      ) : null}
    </div>
  );
}
