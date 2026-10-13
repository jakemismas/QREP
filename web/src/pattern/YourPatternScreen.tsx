/**
 * Your pattern (C2a, issue #96; SPEC.md section 2.1, screen 4): the quilt
 * true to scale beside the photo it was read from (stacked below it under
 * 720 px), the method in one line, the one pattern PDF, the flagged squares
 * and the fabric census. The sample pattern has no photo: the quilt shows
 * alone, with no Compare and no flagged line.
 *
 * One layout serves every width (web-17, ux-22): on a phone the heading,
 * method and PDF button come first, so the button is on screen without
 * scrolling; from 720 px the photo and quilt form a sticky media column that
 * stays in view while the side column scrolls. A one-finger drag on the
 * quilt scrolls the page while the quilt is at Fit and pans it once zoomed:
 * the stylesheet relaxes QuiltCanvas's touch-action under data-zoomed
 * "false", which this screen keeps in step with the canvas's zoom label.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import type { RefObject } from "react";
import { useEngineStatus } from "../engine/engineStatus";
import { useEngine } from "../engine/useEngine";
import type { QuiltModel } from "../model/types";
import { Lightbox } from "../shell/photo/Lightbox";
import type { LbTab } from "../shell/photo/Lightbox";
import { useModel } from "../state/model";
import { useYourPattern } from "../state/pattern";
import { usePhoto } from "../state/photo";
import { QuiltCanvas } from "../viewer";
import { FabricCensus } from "./FabricCensus";
import { FlaggedOverlay } from "./FlaggedOverlay";
import { MethodLine } from "./MethodLine";
import { PatternPdfButton } from "./PatternPdfButton";
import "./YourPatternScreen.css";

const ENGINE_DOWN = "The pattern engine did not start, so your pattern is not ready yet.";

function parseModel(json: string | undefined): QuiltModel | null {
  if (!json) return null;
  try {
    return JSON.parse(json) as QuiltModel;
  } catch {
    return null;
  }
}

/** Tracks whether the quilt view has left Fit, from QuiltCanvas's zoom label. */
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
  return zoomed;
}

export function YourPatternScreen() {
  const { model, summary: census } = useModel();
  const photo = usePhoto();
  const pattern = useYourPattern();
  const engine = useEngine();
  const engineStatus = useEngineStatus();
  const [showFlags, setShowFlags] = useState(true);
  const [lightbox, setLightbox] = useState<LbTab | null>(null);
  const quiltRef = useRef<HTMLElement>(null);

  const read = pattern.source === "photo" ? photo.result : null;
  const readModel = useMemo(() => parseModel(read?.modelJson), [read?.modelJson]);
  const zoomed = useZoomed(quiltRef, model !== null);

  if (model === null) return null;

  // The read's own model carries the cell confidences the outlines need.
  const quiltModel = readModel ?? model;
  const photoUrl = pattern.source === "photo" ? photo.photoUrl : null;
  const flagged = read !== null && readModel !== null ? read.uncertainCount : null;
  const { summary, pdf } = pattern;

  // A failed boot leaves queued calls waiting forever, so a wait on it gets
  // the sentence and a Retry that reboots the engine.
  const waiting = summary.status === "loading" || pdf.status === "busy";
  let error: { message: string; retry: () => void } | null = null;
  if (engineStatus.phase === "failed" && waiting) {
    error = {
      message: ENGINE_DOWN,
      retry: () => {
        engine.retry();
        if (summary.status !== "ready") pattern.retrySummary();
      },
    };
  } else if (pdf.status === "failed") {
    error = { message: pdf.message ?? "", retry: pattern.retryPdf };
  } else if (summary.status === "failed") {
    error = { message: summary.message, retry: pattern.retrySummary };
  }

  return (
    <div
      className="yp-root"
      data-testid="your-pattern"
      data-source={pattern.source}
      data-screen-label="Your pattern"
    >
      <section className="yp-head">
        <h1 className="yp-title">Your pattern</h1>
        <MethodLine summary={summary} />
        <PatternPdfButton pdf={pdf} onSave={pattern.savePdf} />
        {error !== null ? (
          <div className="yp-error" role="alert" data-testid="pattern-error">
            <p className="yp-error-text">{error.message}</p>
            <button
              type="button"
              className="btn btn--secondary yp-retry"
              data-testid="pattern-retry"
              onClick={error.retry}
            >
              Retry
            </button>
          </div>
        ) : null}
      </section>

      <section className={photoUrl ? "yp-media yp-media--pair" : "yp-media"}>
        {photoUrl ? (
          <figure className="yp-figure" data-testid="pattern-photo">
            <figcaption className="yp-eyebrow">Your photo</figcaption>
            <img className="yp-photo-img" src={photoUrl} alt="Your uploaded quilt" />
          </figure>
        ) : null}
        <figure
          className="yp-figure yp-quilt"
          data-testid="pattern-quilt"
          data-zoomed={zoomed ? "true" : "false"}
          ref={quiltRef}
        >
          {photoUrl ? <figcaption className="yp-eyebrow">Recovered quilt</figcaption> : null}
          <QuiltCanvas model={quiltModel} showUncertain={flagged !== null && showFlags} />
        </figure>
        {photoUrl ? (
          <button
            type="button"
            className="btn btn--secondary yp-compare"
            data-testid="open-lightbox"
            onClick={() => setLightbox("side")}
          >
            Compare with your photo
          </button>
        ) : null}
      </section>

      <section className="yp-details">
        {flagged !== null ? (
          <FlaggedOverlay
            count={flagged}
            shown={showFlags}
            onToggle={() => setShowFlags((value) => !value)}
          />
        ) : null}
        {summary.status === "ready" ? (
          <FabricCensus
            lines={summary.summary.fabrics}
            palette={model.palette.fabrics}
            census={census}
          />
        ) : null}
      </section>

      {lightbox !== null ? (
        <Lightbox
          photoUrl={photoUrl}
          model={quiltModel}
          tab={lightbox}
          onTab={setLightbox}
          onClose={() => setLightbox(null)}
          showUncertain={flagged !== null && showFlags}
        />
      ) : null}
    </div>
  );
}
