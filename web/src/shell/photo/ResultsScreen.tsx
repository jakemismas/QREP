/*
 * Results (photo.state === "results"): side-by-side photo and recovered
 * quilt, per-stage confidence meters, the overall pill, the uncertain toggle,
 * the lightbox and the timing line.
 */
import { useMemo, useState } from "react";
import { QuiltCanvas } from "../../viewer";
import { verdictStory } from "../../model/verdictStory";
import type { QuiltModel } from "../../model/types";
import { useUncertainty } from "../../state/photo";
import type { PhotoApi } from "../photoApi";
import { Lightbox } from "./Lightbox";
import type { LbTab } from "./Lightbox";
import { SizeStory } from "./SizeBlock";
import { STAGES, confWord, stageConf } from "./stages";
import type { Tone } from "./stages";
import "./shared.css";
import "./ResultsScreen.css";

// Overall pill = the mock's rule: the MEAN of the six stage confidences,
// rounded to a percent, tiered. (Documented choice: average, not min, to match
// QREP.dc.html line 1655-1657.)
function overallPill(confs: number[]): { pct: number; word: string; tone: Tone } {
  const avg = confs.length ? confs.reduce((a, b) => a + b, 0) / confs.length : 0;
  const pct = Math.round(avg * 100);
  if (pct >= 92) return { pct, word: "very sure", tone: "sage" };
  if (pct >= 84) return { pct, word: "solid", tone: "sage" };
  if (pct >= 78) return { pct, word: "good - check the flags", tone: "amber" };
  return { pct, word: "needs your eye", tone: "accent" };
}

function parseModel(json: string | undefined | null): QuiltModel | null {
  if (!json) return null;
  try {
    return JSON.parse(json) as QuiltModel;
  } catch {
    return null;
  }
}

export function ResultsScreen({ photo }: { photo: PhotoApi }) {
  const uncertainty = useUncertainty();
  const [lb, setLb] = useState<LbTab | null>(null);

  const result = photo.result;
  const model = useMemo(() => parseModel(result?.modelJson), [result?.modelJson]);

  if (!result || !model) {
    return (
      <div className="pf-wrap" data-testid="photo-results">
        <p className="pf-lede">The recovered quilt could not be read. Try another photo.</p>
      </div>
    );
  }

  const confs = STAGES.map((stage) => stageConf(result.stageConfidence, stage));
  const pill = overallPill(confs);
  const story = verdictStory(result, {
    cols: model.center.cols,
    rows: model.center.rows,
    cellSize: model.center.cell_size,
  });
  const uncCount = uncertainty?.count ?? result.uncertainCount;
  const showUncertain = uncertainty?.showUncertain ?? false;
  const showToggle = uncCount > 0;

  return (
    <div
      className="pf-wrap"
      data-testid="photo-results"
      data-screen-label="Photo results"
      data-verdict={result.verdict ?? "readable"}
    >
      <div className="pf-results-head">
        <h1 className="pf-h1">Here&rsquo;s what we found</h1>
        {story.pill.mode === "failure" ? (
          <span className="pf-pill pf-pill--accent" data-testid="overall-pill" data-failure>
            {story.pill.text}
          </span>
        ) : story.pill.mode === "nonsquare" ? (
          <span
            className={`pf-pill pf-pill--${pill.tone}`}
            data-testid="overall-pill"
            data-value={pill.pct / 100}
          >
            {story.pill.text} ({pill.pct}%)
          </span>
        ) : (
          <span
            className={`pf-pill pf-pill--${pill.tone}`}
            data-testid="overall-pill"
            data-value={pill.pct / 100}
          >
            Overall confidence {pill.pct}% - {pill.word}
          </span>
        )}
      </div>

      <div className="pf-results-grid">
        <div className="pf-panel">
          <div className="pf-panel-eyebrow">Your photo</div>
          {photo.photoUrl ? (
            <img className="pf-photo" src={photo.photoUrl} alt="Your uploaded quilt" />
          ) : (
            <div className="pf-photo pf-photo--gone">Photo cleared</div>
          )}
        </div>

        <div className="pf-panel">
          <div className="pf-panel-eyebrow">Recovered quilt</div>
          {story.failurePanel ? (
            <div className="pf-fail" data-testid="failure-panel">
              <h2 className="pf-fail-title">{story.failurePanel.title}</h2>
              <p className="pf-fail-reason">{story.failurePanel.reason}</p>
              <div className="pf-fail-actions">
                <button
                  type="button"
                  className="pf-btn pf-btn--primary"
                  data-testid="failure-adjust-crop"
                  onClick={() => photo.toCrop()}
                >
                  Adjust the crop
                </button>
                <details className="pf-tips" data-testid="failure-tips">
                  <summary>Photo tips</summary>
                  <ul>
                    <li>Fill the frame with the quilt.</li>
                    <li>Shoot square-on, not at an angle.</li>
                    <li>Even light beats a bright window behind the quilt.</li>
                  </ul>
                </details>
                <button
                  type="button"
                  className="pf-btn pf-btn--secondary"
                  data-testid="failure-start-editor"
                  onClick={() => photo.startInEditorFromFailure()}
                >
                  Start in the editor
                </button>
              </div>
            </div>
          ) : null}
          {story.infoPanel ? (
            <div className="pf-info" data-testid="nonsquare-panel">
              <h2 className="pf-info-title">{story.infoPanel.title}</h2>
              {story.infoPanel.period ? (
                <p className="pf-info-line">{story.infoPanel.period}</p>
              ) : null}
              {story.infoPanel.sizeInvite ? (
                <p className="pf-info-line">Know the size? Add it for a better answer.</p>
              ) : null}
            </div>
          ) : null}
          {story.disclosure ? (
            <details className="pf-disclose" data-testid="verdict-disclosure">
              <summary data-testid="verdict-disclosure-summary">{story.disclosure.label}</summary>
              <div className="pf-wrong-banner" data-testid="wrong-banner">
                {story.disclosure.banner}
              </div>
              <div className="pf-recovered">
                <QuiltCanvas model={model} showUncertain={showUncertain} />
              </div>
              <div className="pf-recovered-cap">
                <SizeStory photo={photo} model={model} />
                <span>
                  {model.center.cols} &times; {model.center.rows} squares
                </span>
              </div>
            </details>
          ) : (
            <>
              <div className="pf-recovered">
                <QuiltCanvas model={model} showUncertain={showUncertain} />
              </div>
              <div className="pf-recovered-cap">
                <SizeStory photo={photo} model={model} />
                <span>
                  {model.center.cols} &times; {model.center.rows} squares
                </span>
              </div>
              {story.caption ? (
                <p className="pf-caption" data-testid="verdict-caption">
                  {story.caption}
                </p>
              ) : null}
            </>
          )}
        </div>

        <div className="pf-side">
          <div className="pf-card">
            <h2 className="pf-h2">How sure are we?</h2>
            <p className="pf-hint">
              Computer vision guesses; it does not know. Anything you fix by hand in the editor
              becomes 100%.
            </p>
            {STAGES.map((stage, i) => {
              const conf = confs[i];
              const pct = Math.round(conf * 100);
              const { word, tone } = confWord(conf);
              return (
                <div key={stage.ui} className="pf-conf-row">
                  <span className="pf-conf-label">{stage.label}</span>
                  <span
                    className="pf-conf-meter"
                    data-testid={`confidence-${stage.ui}`}
                    data-value={conf}
                  >
                    <span
                      className={`pf-meter-fill pf-tone--${tone}`}
                      style={{ width: `${pct}%` }}
                    />
                  </span>
                  <span className="pf-conf-pct">{pct}%</span>
                  <span className={`pf-conf-word pf-tone-text--${tone}`}>{word}</span>
                </div>
              );
            })}

            {showToggle ? (
              <button
                type="button"
                className="pf-toggle"
                data-testid="uncertain-toggle"
                data-on={showUncertain || undefined}
                aria-pressed={showUncertain}
                onClick={() => uncertainty?.toggle()}
              >
                <span className="pf-toggle-track" data-on={showUncertain || undefined}>
                  <span className="pf-toggle-knob" data-on={showUncertain || undefined} />
                </span>
                <span className="pf-toggle-label">
                  Highlight the {uncCount} squares to double-check
                </span>
              </button>
            ) : null}
          </div>

          <div className="pf-actions">
            {story.failurePanel ? null : (
              <button
                type="button"
                className="pf-btn pf-btn--primary"
                data-testid="open-in-editor"
                onClick={() => photo.openInEditor()}
              >
                Open in the editor
              </button>
            )}
            <button
              type="button"
              className="pf-btn pf-btn--secondary"
              data-testid="adjust-corners"
              onClick={() => photo.toCrop()}
            >
              Adjust the crop
            </button>
            {photo.photoUrl ? (
              <button
                type="button"
                className="pf-link"
                data-testid="open-lightbox"
                onClick={() => setLb("side")}
              >
                Compare side by side, full size
              </button>
            ) : null}
            <span
              className="pf-timing"
              data-testid="reverse-timing"
              data-ms={result.reverseMs}
            >
              Reversed in {Math.round(result.reverseMs)} ms, all in your browser.
            </span>
          </div>
        </div>
      </div>

      {lb ? (
        <Lightbox
          photoUrl={photo.photoUrl}
          model={model}
          tab={lb}
          onTab={setLb}
          onClose={() => setLb(null)}
          showUncertain={showUncertain}
        />
      ) : null}
    </div>
  );
}
