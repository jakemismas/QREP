/*
 * Progress (photo.state === "progress"): staged analysis with the vision
 * engine's loading, cached and retry states and the six stage rows.
 */
import { useEffect, useState } from "react";
import { verdictStory } from "../../model/verdictStory";
import type { PhotoApi } from "../photoApi";
import { STAGES, confWord, stageConf } from "./stages";
import type { Tone } from "./stages";
import "./shared.css";
import "./ProgressScreen.css";

const VISION_CACHE_KEY = "qrep-vision-cached";

function visionMb(bytes: number): string {
  return (bytes / (1024 * 1024)).toFixed(1);
}

export function ProgressScreen({ photo }: { photo: PhotoApi }) {
  const [cached, setCached] = useState<boolean>(() => {
    try {
      return localStorage.getItem(VISION_CACHE_KEY) != null;
    } catch {
      return false;
    }
  });

  // Remember a successful vision load so repeat runs show the cached notice
  // instead of the loading bar (PARITY 17).
  useEffect(() => {
    if (photo.visionState !== "ready") return;
    try {
      localStorage.setItem(VISION_CACHE_KEY, "1");
    } catch {
      /* storage blocked: cached notice is best-effort */
    }
    setCached(true);
  }, [photo.visionState]);

  const result = photo.result;
  // S8 (issue #74, UI-SPEC section 5): rows at/after the failure point show
  // a neutral dash. Only dashedStages is read here; the grid arg is unused
  // by that field, so a placeholder grid is passed.
  const dashed = result
    ? verdictStory(result, { cols: 1, rows: 1, cellSize: 8 }).dashedStages
    : [];
  const sized =
    photo.visionBytes != null ? ` - about ${visionMb(photo.visionBytes)} MB` : "";
  const showCached = cached && photo.visionState !== "loading";

  return (
    <div
      className="pf-wrap pf-wrap--narrow"
      data-testid="photo-progress"
      data-screen-label="Analysis progress"
    >
      <div className="pf-card">
        <h1 className="pf-h1 pf-h1--sm">Reading your quilt&hellip;</h1>
        <p className="pf-lede pf-lede--sm">The vision stages fill in as each one lands.</p>

        {photo.visionState === "loading" ? (
          <div className="pf-vision" data-testid="vision-loading">
            <div className="pf-vision-row">
              <span>
                Loading the vision engine{sized}, first time only
              </span>
            </div>
            <div className="pf-vision-track">
              <span className="pf-vision-bar" />
            </div>
          </div>
        ) : null}

        {showCached ? (
          <div className="pf-vision-cached" data-testid="vision-cached">
            <svg width="14" height="14" aria-hidden="true" className="pf-check">
              <path d="M2 7.5l3.5 3.5L12 3.5" />
            </svg>
            Vision engine ready, it loaded in the background.
          </div>
        ) : null}

        {photo.visionState === "failed" ? (
          <button
            type="button"
            className="pf-vision-retry"
            data-testid="vision-retry"
            onClick={() => photo.retryVision?.()}
          >
            The vision engine didn&rsquo;t load. Try again
          </button>
        ) : null}

        <div className="pf-stages">
          {STAGES.map((stage) => {
            if (dashed.includes(stage.ui)) {
              return (
                <div
                  key={stage.ui}
                  className="pf-stage"
                  data-testid={`stage-${stage.ui}`}
                  data-dashed
                >
                  <span className="pf-stage-icon pf-stage-dash" aria-hidden="true">
                    &ndash;
                  </span>
                  <span className="pf-stage-label">{stage.label}</span>
                </div>
              );
            }
            const conf = result ? stageConf(result.stageConfidence, stage) : null;
            const done = conf != null;
            const pct = done ? Math.round(conf * 100) : 0;
            const tone: Tone = done ? confWord(conf).tone : "accent";
            return (
              <div
                key={stage.ui}
                className="pf-stage"
                data-testid={`stage-${stage.ui}`}
                data-done={done || undefined}
              >
                <span className="pf-stage-icon">
                  {done ? (
                    <svg width="17" height="17" aria-hidden="true" className="pf-stage-check">
                      <path d="M2.5 9l4 4L14.5 4" />
                    </svg>
                  ) : (
                    <span className="pf-stage-spin" aria-hidden="true" />
                  )}
                </span>
                <span className="pf-stage-label">{stage.label}</span>
                {done ? (
                  <>
                    <span className="pf-stage-meter">
                      <span
                        className={`pf-meter-fill pf-tone--${tone}`}
                        style={{ width: `${pct}%` }}
                      />
                    </span>
                    <span className="pf-stage-pct">{pct}%</span>
                  </>
                ) : null}
              </div>
            );
          })}
        </div>

        <div className="pf-progress-actions">
          <button
            type="button"
            className="pf-link"
            data-testid="photo-cancel"
            onClick={() => photo.cancel()}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
