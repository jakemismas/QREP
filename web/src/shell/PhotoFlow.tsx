/*
 * Photo-reverse screens (S6 issue #46; S2 sprint 3 issue #68; PARITY items
 * 6, 7, 14, 17 + the sprint 3 amendment). Renders the four photo-flow
 * screens off useProject().photo.state:
 *   idle     -> dropzone (file input, drag/drop, sample photo)
 *   crop     -> the photo with draggable pins BEFORE any analysis; the
 *               detected quad snaps in unless the user already moved a pin
 *   progress -> staged analysis (vision-loading/cached/retry, six stage rows)
 *   results  -> side-by-side photo + recovered quilt, per-stage confidence
 *               meters, overall pill, uncertain toggle, lightbox, timing
 * The post-results corners screen is retired: "Adjust the crop" returns to
 * the crop screen seeded with the confirmed quad (UI-SPEC section 1).
 *
 * Also exports RoundTripPanel (the Pattern-tab round-trip check) and Lightbox
 * (reusable Photo / Side by side / Quilt viewer).
 *
 * Squares, never cells. Loading copy never says the banned asset-fetch verbs
 * (copy-audit enforces). Styling is design-tokens only; colors come from the
 * token set or the user fabric data.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent, ReactNode } from "react";
import { useProject } from "../state/project";
import { QuiltCanvas } from "../viewer";
import { formatEighths } from "../model/units";
import { formatCmEquivalent } from "../model/sizeEntry";
import { verdictStory } from "../model/verdictStory";
import { PRESETS } from "../model/sizing";
import type { QuiltModel } from "../model/types";
import { usePhoto, useRoundTrip, useUncertainty } from "./photoApi";
import type { PhotoApi } from "./photoApi";

type Tone = "sage" | "amber" | "accent";

// Engine stage key -> UI stage key + display label (1:1 with the pipeline's
// provenance.stage_confidence). rectify/palette/cells/repeat/border read as
// straighten/colors/squares/repeats/borders.
const STAGES: { ui: string; engine: string; label: string }[] = [
  { ui: "straighten", engine: "rectify", label: "Straighten" },
  { ui: "colors", engine: "palette", label: "Fabric colors" },
  { ui: "grid", engine: "grid", label: "Grid" },
  { ui: "squares", engine: "cells", label: "Squares" },
  { ui: "repeats", engine: "repeat", label: "Repeats" },
  { ui: "borders", engine: "border", label: "Borders" },
];

const VISION_CACHE_KEY = "qrep-vision-cached";

function stageConf(sc: Record<string, number>, stage: { ui: string; engine: string }): number {
  const value = sc[stage.engine] ?? sc[stage.ui];
  return typeof value === "number" ? value : 0;
}

function confWord(conf: number): { word: string; tone: Tone } {
  if (conf >= 0.95) return { word: "Very sure", tone: "sage" };
  if (conf >= 0.85) return { word: "Solid", tone: "sage" };
  if (conf >= 0.8) return { word: "Good", tone: "amber" };
  return { word: "Check it", tone: "accent" };
}

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

function visionMb(bytes: number): string {
  return (bytes / (1024 * 1024)).toFixed(1);
}



// ---------------------------------------------------------------------------
// Dropzone (photo.state === "idle")
// ---------------------------------------------------------------------------

function Dropzone({ photo, onHome }: { photo: PhotoApi; onHome: () => void }) {
  const inputRef = useRef<HTMLInputElement>(null);

  const takeFiles = (files: FileList | null): void => {
    const file = files?.[0];
    if (file) void photo.stage(file);
  };

  return (
    <div className="pf-wrap pf-wrap--narrow" data-screen-label="Photo dropzone">
      <button type="button" className="pf-home" onClick={onHome}>
        &larr; Home
      </button>
      <h1 className="pf-h1">Start from a photo</h1>
      <p className="pf-lede">
        Flat, straight-on shots in daylight work best. QREP straightens small angles for you. A
        photo, a screenshot, or a shop listing picture all work.
      </p>

      <div
        className="pf-dropzone"
        data-testid="photo-dropzone"
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
        }}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          takeFiles(e.dataTransfer.files);
        }}
      >
        <svg width="52" height="44" aria-hidden="true" className="pf-camera">
          <rect x="1.25" y="7.25" width="49.5" height="35.5" rx="5" />
          <path d="M17 7l4-5.75h10L35 7" />
          <circle cx="26" cy="24.5" r="9" />
        </svg>
        <span className="pf-dz-title">Drop your quilt photo here</span>
        <span className="pf-dz-sub">JPG or PNG, or tap to browse</span>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        data-testid="photo-file-input"
        className="pf-file-input"
        onChange={(e) => takeFiles(e.target.files)}
      />

      <div className="pf-or">or</div>

      <button
        type="button"
        className="pf-sample"
        data-testid="photo-sample"
        onClick={() => void photo.startSample()}
      >
        <span className="pf-sample-title">Use the sample photo</span>
        <span className="pf-sample-sub">Reverse the Double Irish Chain demo, no upload needed.</span>
      </button>

      <p className="pf-privacy">
        Your photo is read right here in the browser and never leaves this device.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Progress (photo.state === "progress")
// ---------------------------------------------------------------------------

function Progress({ photo }: { photo: PhotoApi }) {
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

// ---------------------------------------------------------------------------
// Results (photo.state === "results")
// ---------------------------------------------------------------------------

type LbTab = "photo" | "side" | "quilt";

function Results({ photo }: { photo: PhotoApi }) {
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

// ---------------------------------------------------------------------------
// Shared pin/quad overlay (S2: one pin surface, one behavior) + crop screen
// ---------------------------------------------------------------------------

function quadPath(corners: [number, number][]): string {
  const pts = corners.map(([x, y]) => `${(x * 100).toFixed(2)} ${(y * 100).toFixed(2)}`);
  return `M${pts[0]}L${pts[1]}L${pts[2]}L${pts[3]}Z`;
}

/** The draggable pin/quad overlay, extracted from the retired corner editor
 * so the crop screen and any future pin surface share one behavior. Pin
 * drag is pure JS: it never waits on the engine (cold-start contract). */
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

/** The S7 size block (UI-SPEC section 2): PRESET chips, W x H fraction
 * inputs, in/cm toggle. One component, two hosts: the crop screen and the
 * results inline editor. Squares vocabulary; mixed fractions everywhere. */
function SizeBlock({ photo, compact }: { photo: PhotoApi; compact?: boolean }) {
  const size = photo.size;
  const [widthDraft, setWidthDraft] = useState("");
  const [heightDraft, setHeightDraft] = useState("");

  // resync drafts from committed state (chip taps, suggestions, seeds)
  useEffect(() => {
    setWidthDraft(size.widthEighths === null ? "" : formatEighths(size.widthEighths));
    setHeightDraft(size.heightEighths === null ? "" : formatEighths(size.heightEighths));
  }, [size.widthEighths, size.heightEighths]);

  const commit = (which: "width" | "height", draft: string) => {
    if (!draft.trim()) return;
    size.editInput(which, draft);
  };

  return (
    <div className="pf-size" data-testid="size-block" data-compact={compact || undefined}>
      {!compact ? (
        <>
          <h2 className="pf-size-h">How big is it?</h2>
          <p className="pf-size-sub">
            Skip this if you&rsquo;re not sure &mdash; you can set it any time.
          </p>
        </>
      ) : null}
      <div className="pf-size-chips">
        {PRESETS.map((preset) => {
          const suggested = size.suggestedPreset === preset.name;
          return (
            <button
              key={preset.name}
              type="button"
              className="pf-chip"
              data-testid={`size-chip-${preset.name.toLowerCase()}`}
              data-suggested={suggested || undefined}
              title={`${formatEighths(preset.width)} \u00d7 ${formatEighths(preset.height)}`}
              onClick={() => size.tapChip(preset.name)}
            >
              {preset.name}
              {suggested ? <span className="pf-chip-hint">looks about right?</span> : null}
            </button>
          );
        })}
      </div>
      <div className="pf-size-row">
        <input
          className="pf-size-input"
          data-testid="size-width"
          data-suggested={size.source === "suggested" || undefined}
          placeholder={size.unit === "in" ? "width in" : "width cm"}
          value={widthDraft}
          onChange={(e) => setWidthDraft(e.target.value)}
          onBlur={() => commit("width", widthDraft)}
          onKeyDown={(e) => {
            if (e.key === "Enter") commit("width", widthDraft);
          }}
        />
        <span className="pf-size-x">&times;</span>
        <input
          className="pf-size-input"
          data-testid="size-height"
          data-suggested={size.source === "suggested" || undefined}
          placeholder={size.unit === "in" ? "height in" : "height cm"}
          value={heightDraft}
          onChange={(e) => setHeightDraft(e.target.value)}
          onBlur={() => commit("height", heightDraft)}
          onKeyDown={(e) => {
            if (e.key === "Enter") commit("height", heightDraft);
          }}
        />
        <button
          type="button"
          className="pf-size-unit"
          data-testid="size-unit-toggle"
          data-unit={size.unit}
          onClick={() => size.toggleUnit()}
        >
          in / cm
        </button>
      </div>
    </div>
  );
}

/** The results size line + asked-vs-got (UI-SPEC 2.4). */
function SizeStory({ photo, model }: { photo: PhotoApi; model: QuiltModel }) {
  const [editing, setEditing] = useState(false);
  const result = photo.result;
  const sized = result?.diagnostics?.["size_source"] === "user";
  const achieved = result?.sizeAchieved ?? null;
  const requested = result?.sizeRequested ?? null;
  const bandTotal = model.borders.reduce((sum, b) => sum + b.width, 0);
  const width = achieved?.width ?? model.center.cols * model.center.cell_size + 2 * bandTotal;
  const height = achieved?.height ?? model.center.rows * model.center.cell_size + 2 * bandTotal;
  const line = `${formatEighths(width)} \u00d7 ${formatEighths(height)} finished`;
  const cm = photo.size.enteredInCm
    ? ` (${formatCmEquivalent(width)} \u00d7 ${formatCmEquivalent(height)} cm)`
    : "";
  const askedDiffers =
    sized &&
    requested !== null &&
    ((requested.width !== null && requested.width !== width) ||
      (requested.height !== null && requested.height !== height));
  return (
    <div className="pf-size-story">
      <button
        type="button"
        className="pf-size-line"
        data-testid="size-line"
        data-sized={sized || undefined}
        onClick={() => {
          photo.size.seedForEdit(width, height);
          setEditing((v) => !v);
        }}
      >
        {sized ? `${line}${cm} \u2014 tap to edit` : `${line} \u2014 our guess, tap to set the real size`}
      </button>
      {askedDiffers && requested ? (
        <div className="pf-size-asked" data-testid="size-asked-got">
          You asked for {requested.width !== null ? formatEighths(requested.width) : "?"}
          {" \u00d7 "}
          {requested.height !== null ? formatEighths(requested.height) : "?"} &mdash; the squares
          work out to {formatEighths(width)} &times; {formatEighths(height)}.
        </div>
      ) : null}
      {editing ? (
        <div className="pf-size-inline" data-testid="size-inline-editor">
          <SizeBlock photo={photo} compact />
          <button
            type="button"
            className="pf-btn pf-btn--secondary pf-size-apply"
            data-testid="size-apply"
            disabled={!photo.size.canApply}
            onClick={() => {
              void photo.applySizeFromResults().then(() => setEditing(false));
            }}
          >
            Apply size
          </button>
        </div>
      ) : null}
    </div>
  );
}

function CropScreen({ photo }: { photo: PhotoApi }) {
  // Reset to auto is meaningful only when the pins differ from their auto
  // target (UI-SPEC section 1); a user move is exactly that condition.
  const canReset = photo.quadSource === "user";
  return (
    <div className="pf-wrap pf-wrap--mid" data-testid="crop-screen" data-screen-label="Check the crop">
      <div className="pf-card">
        <h1 className="pf-h1 pf-h1--sm">Check the crop</h1>
        <p className="pf-lede pf-lede--sm">
          Drag the pins so they sit on the quilt&rsquo;s corners.
        </p>

        <PinOverlay photoUrl={photo.photoUrl} corners={photo.corners} onMovePin={photo.setCorner} />

        {photo.detectPending ? (
          <div className="pf-detecting" data-testid="crop-detecting">
            <span className="pf-stage-spin" aria-hidden="true" />
            Finding your quilt&hellip;
          </div>
        ) : null}

        <SizeBlock photo={photo} />

        <div className="pf-corner-actions">
          <button
            type="button"
            className="pf-btn pf-btn--primary"
            data-testid="crop-analyze"
            onClick={() => void photo.analyze()}
          >
            Analyze
          </button>
          <button
            type="button"
            className="pf-btn pf-btn--secondary"
            data-testid="crop-reset"
            disabled={!canReset}
            onClick={() => photo.resetToAuto()}
          >
            Reset to auto
          </button>
          <button
            type="button"
            className="pf-link"
            data-testid="crop-back"
            onClick={() => photo.backFromCrop()}
          >
            Back
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Lightbox (reusable Photo / Side by side / Quilt viewer)
// ---------------------------------------------------------------------------

export function Lightbox({
  photoUrl,
  model,
  tab,
  onTab,
  onClose,
  showUncertain = false,
}: {
  photoUrl: string | null;
  model: QuiltModel | null;
  tab: LbTab;
  onTab: (tab: LbTab) => void;
  onClose: () => void;
  showUncertain?: boolean;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const tabs: { id: LbTab; label: string }[] = [
    { id: "photo", label: "Photo" },
    { id: "side", label: "Side by side" },
    { id: "quilt", label: "Quilt" },
  ];

  const photoEl = photoUrl ? (
    <img className="pf-lb-photo" src={photoUrl} alt="Your uploaded quilt" />
  ) : (
    <div className="pf-lb-photo pf-photo--gone">Photo cleared</div>
  );
  const quiltEl = model ? (
    <div className="pf-lb-quilt">
      <QuiltCanvas model={model} showUncertain={showUncertain} />
    </div>
  ) : null;

  return (
    <div className="pf-lb" data-testid="lightbox" data-noprint>
      <div className="pf-lb-scrim" onClick={onClose} />
      <div className="pf-lb-inner">
        <div className="pf-lb-bar">
          <span className="pf-lb-tabs">
            {tabs.map((t) => (
              <button
                key={t.id}
                type="button"
                className="pf-lb-tab"
                data-active={t.id === tab || undefined}
                data-testid={`lightbox-tab-${t.id}`}
                onClick={() => onTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </span>
          <button type="button" className="pf-lb-close" aria-label="Close" onClick={onClose}>
            &#10005;
          </button>
        </div>
        <div className="pf-lb-stage">
          {tab === "photo" ? photoEl : null}
          {tab === "quilt" ? quiltEl : null}
          {tab === "side" ? (
            <div className="pf-lb-side">
              {photoEl}
              {quiltEl}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Round-trip check (Pattern tab; render L0/L2 then compare recovered vs truth)
// ---------------------------------------------------------------------------

export function RoundTripPanel() {
  const roundtrip = useRoundTrip();
  const [level, setLevel] = useState<0 | 2>(0);
  const [busy, setBusy] = useState(false);

  const report = roundtrip?.report ?? null;

  const run = async (): Promise<void> => {
    if (!roundtrip) return;
    setBusy(true);
    try {
      await roundtrip.run(level);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="pf-rt" data-testid="roundtrip-panel">
      <div className="pf-rt-head">
        <h3 className="pf-rt-title">Round-trip check</h3>
        <span className="pf-rt-rule" />
        <span className="pf-rt-pill">render then reverse</span>
      </div>
      <p className="pf-rt-lede">
        Render this design, reverse the render back, and compare, so you can see the pipeline agree
        with itself.
      </p>
      <div className="pf-rt-controls">
        <label className="pf-rt-field">
          <span className="pf-rt-field-label">Detail level</span>
          <select
            className="pf-rt-select"
            data-testid="roundtrip-level"
            value={level}
            onChange={(e) => setLevel(Number(e.target.value) === 2 ? 2 : 0)}
          >
            <option value={0}>Level 0, exact grid</option>
            <option value={2}>Level 2, textured</option>
          </select>
        </label>
        <button
          type="button"
          className="pf-btn pf-btn--secondary"
          data-testid="roundtrip-run"
          disabled={busy || !roundtrip}
          onClick={() => void run()}
        >
          {busy ? "Checking…" : "Run round-trip check"}
        </button>
      </div>
      {report ? (
        <div
          className={`pf-rt-report pf-rt-report--${report.dimsMatch ? "ok" : "bad"}`}
          data-testid="roundtrip-report"
        >
          <span className="pf-rt-report-line">
            Dimensions {report.dimsMatch ? "MATCH" : "MISMATCH"}
          </span>
          <span className="pf-rt-report-line">
            Square accuracy {(report.cellAccuracy * 100).toFixed(0)}% (
            {report.cellAccuracy.toFixed(4)})
          </span>
        </div>
      ) : null}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------

export default function PhotoFlow() {
  const { goHome } = useProject();
  const photo = usePhoto();

  switch (photo.state) {
    case "crop":
      return (
        <PhotoStyle>
          <CropScreen photo={photo} />
        </PhotoStyle>
      );
    case "progress":
      return (
        <PhotoStyle>
          <Progress photo={photo} />
        </PhotoStyle>
      );
    case "results":
      return (
        <PhotoStyle>
          <Results photo={photo} />
        </PhotoStyle>
      );
    case "idle":
    default:
      return (
        <PhotoStyle>
          <Dropzone photo={photo} onHome={goHome} />
        </PhotoStyle>
      );
  }
}

function PhotoStyle({ children }: { children: ReactNode }) {
  return (
    <>
      {children}
      <style>{PF_CSS}</style>
    </>
  );
}

const PF_CSS = `
.pf-wrap { animation: qFade .35s ease; margin: 14px auto 0; }
.pf-wrap--narrow { max-width: 620px; }
.pf-wrap--mid { max-width: 760px; }
.pf-home { background: none; border: none; padding: 2px 0; font: 500 15px var(--sans); color: var(--accent); cursor: pointer; }
.pf-h1 { margin: 8px 0 6px; font: 700 30px var(--serif); color: var(--denim); }
.pf-h1--sm { margin: 0 0 4px; font-size: 27px; }
.pf-h2 { margin: 0 0 4px; font: 700 21px var(--serif); color: var(--denim); }
.pf-lede { margin: 0 0 18px; font-size: 16.5px; line-height: 1.55; color: var(--mut); }
.pf-lede--sm { font-size: 15px; margin-bottom: 16px; }
.pf-hint { margin: 0 0 10px; font-size: 14px; line-height: 1.5; color: var(--faint); }
.pf-card { background: var(--card); border: 1px solid var(--line); border-radius: 18px; box-shadow: 0 2px 10px var(--shadow); padding: 24px; }

.pf-dropzone { display: flex; flex-direction: column; align-items: center; gap: 10px; border: 2.5px dashed var(--line2); border-radius: 18px; background: var(--card2); padding: 40px 26px; text-align: center; cursor: pointer; }
.pf-dropzone:hover { border-color: var(--accent); background: var(--card); }
.pf-dropzone:focus-visible { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(165,80,47,0.25); }
.pf-camera { color: var(--mut); }
.pf-camera rect, .pf-camera path, .pf-camera circle { fill: none; stroke: currentColor; stroke-width: 2.5; }
.pf-dz-title { font: 700 20px var(--serif); color: var(--ink); }
.pf-dz-sub { font-size: 14.5px; color: var(--mut); }
.pf-file-input { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
.pf-or { text-align: center; font-size: 13.5px; color: var(--faint); margin: 14px 0; }
.pf-sample { display: flex; flex-direction: column; gap: 3px; width: 100%; text-align: left; padding: 14px 16px; border-radius: 12px; border: 1.5px solid var(--line2); background: var(--card); color: var(--ink2); cursor: pointer; }
.pf-sample:hover { background: var(--card2); border-color: var(--accent); }
.pf-sample-title { font: 600 16px var(--sans); color: var(--ink); }
.pf-sample-sub { font-size: 13.5px; color: var(--mut); }
.pf-privacy { margin: 16px 0 0; font-size: 13px; color: var(--faint); text-align: center; }

.pf-vision { background: var(--card3); border: 1px dashed var(--line2); border-radius: 12px; padding: 14px 16px; margin-bottom: 16px; }
.pf-vision-row { display: flex; justify-content: space-between; gap: 12px; font-size: 14.5px; color: var(--ink2); margin-bottom: 9px; }
.pf-vision-track { height: 12px; background: var(--card); border: 1px solid var(--line); border-radius: 999px; overflow: hidden; }
.pf-vision-bar { display: block; height: 100%; width: 45%; background: var(--denim); border-radius: 999px; animation: pfIndeterminate 1.3s ease-in-out infinite; }
@keyframes pfIndeterminate { 0% { margin-left: -45%; } 100% { margin-left: 100%; } }
.pf-vision-cached { display: flex; align-items: center; gap: 9px; font-size: 14px; color: var(--sage); margin-bottom: 14px; }
.pf-check { color: var(--sage); }
.pf-check path { fill: none; stroke: currentColor; stroke-width: 2.5; }
.pf-vision-retry { display: inline-flex; align-items: center; margin-bottom: 14px; padding: 10px 16px; border-radius: 10px; border: 1.5px solid var(--accent); background: var(--card); color: var(--accent); font: 600 14.5px var(--sans); cursor: pointer; }
.pf-vision-retry:hover { background: var(--card2); }

.pf-stages { display: flex; flex-direction: column; }
.pf-stage { display: flex; align-items: center; gap: 13px; padding: 11px 2px; border-bottom: 1px dashed var(--line); }
.pf-stage-icon { width: 22px; height: 22px; flex: none; display: flex; align-items: center; justify-content: center; }
.pf-stage-spin { width: 15px; height: 15px; border-radius: 50%; border: 2.4px solid var(--line2); border-top-color: var(--accent); animation: qSpin .8s linear infinite; }
.pf-stage-check { color: var(--sage); }
.pf-stage-check path { fill: none; stroke: currentColor; stroke-width: 2.8; }
.pf-stage-label { flex: 1; font-size: 16px; color: var(--ink2); }
.pf-stage-meter { width: 86px; height: 9px; background: var(--card3); border: 1px solid var(--line); border-radius: 999px; overflow: hidden; flex: none; }
.pf-stage-pct { width: 44px; text-align: right; font-size: 13.5px; font-weight: 600; color: var(--mut); flex: none; }
.pf-meter-fill { display: block; height: 100%; border-radius: 999px; transition: width .25s ease; }
.pf-tone--sage { background: var(--sage); }
.pf-tone--amber { background: var(--amber); }
.pf-tone--accent { background: var(--accent); }
.pf-progress-actions { display: flex; align-items: center; gap: 16px; margin-top: 18px; }
.pf-link { background: none; border: none; padding: 4px 0; font-size: 15px; color: var(--accent); cursor: pointer; text-decoration: underline; text-underline-offset: 3px; }

.pf-results-head { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin-bottom: 16px; }
.pf-pill { font-size: 14px; font-weight: 700; border-radius: 999px; padding: 8px 15px; border: 1.5px solid var(--pillLn); background: var(--pill); }
.pf-pill--sage { color: var(--sage); border-color: var(--sageLn); background: var(--sageBg); }
.pf-pill--amber { color: var(--amber); }
.pf-pill--accent { color: var(--accent); }
.pf-results-grid { display: flex; gap: 18px; flex-wrap: wrap; align-items: flex-start; }
.pf-panel { flex: 0 1 auto; max-width: 340px; background: var(--card); border: 1px solid var(--line); border-radius: 16px; box-shadow: 0 2px 10px var(--shadow); padding: 14px; }
.pf-panel-eyebrow { font-size: 13px; letter-spacing: .14em; text-transform: uppercase; color: var(--faint); font-weight: 700; margin-bottom: 10px; }
.pf-photo { display: block; max-width: 320px; max-height: 380px; width: auto; height: auto; border-radius: 4px; border: 1px solid var(--line); }
.pf-photo--gone { display: flex; align-items: center; justify-content: center; width: 240px; height: 180px; color: var(--faint); background: var(--card3); border: 1px dashed var(--line2); }
.pf-recovered { width: 320px; max-width: 100%; }
.pf-recovered-cap { display: flex; justify-content: space-between; gap: 10px; font-size: 13.5px; color: var(--mut); padding-top: 8px; }
.pf-side { flex: 1 1 300px; min-width: 280px; display: flex; flex-direction: column; gap: 16px; }
.pf-conf-row { display: flex; align-items: center; gap: 11px; padding: 8px 0; border-bottom: 1px dashed var(--line); }
.pf-conf-label { flex: 1; font-size: 15px; color: var(--ink2); }
.pf-conf-meter { width: 96px; height: 10px; background: var(--card3); border: 1px solid var(--line); border-radius: 999px; overflow: hidden; flex: none; }
.pf-conf-pct { width: 38px; text-align: right; font-size: 13.5px; font-weight: 700; color: var(--ink2); flex: none; }
.pf-conf-word { width: 64px; text-align: right; font-size: 12px; font-weight: 700; flex: none; }
.pf-tone-text--sage { color: var(--sage); }
.pf-tone-text--amber { color: var(--amber); }
.pf-tone-text--accent { color: var(--accent); }
.pf-toggle { display: flex; align-items: center; gap: 12px; background: none; border: none; padding: 14px 0 4px; cursor: pointer; text-align: left; width: 100%; }
.pf-toggle-track { width: 46px; height: 27px; flex: none; border-radius: 999px; position: relative; transition: background .15s; background: var(--card3); border: 1.5px solid var(--line2); }
.pf-toggle-track[data-on] { background: var(--accent); border-color: var(--accent); }
.pf-toggle-knob { position: absolute; top: 2px; left: 3px; width: 20px; height: 20px; border-radius: 50%; background: var(--toggle-knob); box-shadow: 0 1px 4px rgba(0,0,0,0.3); transition: left .15s; }
.pf-toggle-knob[data-on] { left: 22px; }
.pf-toggle-label { flex: 1; font-size: 15px; color: var(--ink2); line-height: 1.4; }
.pf-actions { display: flex; flex-direction: column; gap: 10px; }
.pf-btn { width: 100%; border-radius: 12px; cursor: pointer; font-family: var(--sans); }
.pf-btn--primary { padding: 16px; font-weight: 600; font-size: 17.5px; background: var(--accent); color: var(--accentInk); border: none; box-shadow: 0 4px 12px var(--shadow); }
.pf-btn--primary:hover:not(:disabled) { background: var(--accentB); }
.pf-btn--secondary { padding: 13px; font-weight: 600; font-size: 16px; background: var(--card); border: 1.5px solid var(--line2); color: var(--ink2); }
.pf-btn--secondary:hover:not(:disabled) { background: var(--card2); }
.pf-btn:disabled { opacity: 0.6; cursor: wait; }
.pf-timing { font-size: 12.5px; color: var(--faint); padding-top: 2px; }

.pf-fail { border: 1.5px solid var(--accent); border-radius: 14px; padding: 14px; margin-bottom: 12px; background: var(--card2); }
.pf-fail-title { margin: 0 0 6px; font: 700 19px var(--serif); color: var(--denim); }
.pf-fail-reason { margin: 0 0 12px; font-size: 14px; color: var(--mut); }
.pf-fail-actions { display: flex; flex-direction: column; gap: 8px; }
.pf-tips summary { cursor: pointer; color: var(--accent); font-size: 13.5px; }
.pf-tips ul { margin: 6px 0 0 18px; padding: 0; font-size: 13px; color: var(--mut); }
.pf-info { border: 1px solid var(--line2); border-radius: 14px; padding: 12px 14px; margin-bottom: 12px; background: var(--card2); }
.pf-info-title { margin: 0 0 6px; font: 700 15.5px var(--serif); color: var(--denim); }
.pf-info-line { margin: 0 0 4px; font-size: 13.5px; color: var(--mut); }
.pf-disclose summary { cursor: pointer; color: var(--accent); font-size: 13.5px; padding: 4px 0; }
.pf-wrong-banner { background: var(--pill); border: 1px solid var(--accent); color: var(--accent); border-radius: 9px; padding: 7px 10px; font-size: 12.5px; font-weight: 600; margin: 8px 0; }
.pf-caption { margin: 6px 0 0; font-size: 13.5px; color: var(--mut); }
.pf-stage-dash { color: var(--faint); font-weight: 700; }
.pf-size { margin-top: 16px; }
.pf-size-h { margin: 0 0 2px; font: 700 18px var(--serif); color: var(--denim); }
.pf-size-sub { margin: 0 0 10px; font-size: 13px; color: var(--faint); }
.pf-size-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
.pf-chip { display: inline-flex; flex-direction: column; align-items: center; gap: 1px; padding: 7px 13px; border-radius: 999px; border: 1.5px solid var(--line2); background: var(--card); color: var(--ink2); font: 600 13.5px var(--sans); cursor: pointer; }
.pf-chip:hover { border-color: var(--accent); }
.pf-chip[data-suggested] { border-color: var(--accent); box-shadow: 0 0 0 2px rgba(165,80,47,0.18); }
.pf-chip-hint { font: 500 10.5px var(--sans); color: var(--accent); }
.pf-size-row { display: flex; align-items: center; gap: 8px; }
.pf-size-input { width: 108px; padding: 9px 10px; font: 500 14.5px var(--sans); color: var(--ink); background: var(--card); border: 1.5px solid var(--line2); border-radius: 9px; }
.pf-size-input[data-suggested] { color: var(--faint); }
.pf-size-x { color: var(--faint); }
.pf-size-unit { padding: 8px 11px; border-radius: 9px; border: 1.5px solid var(--line2); background: var(--card2); color: var(--ink2); font: 600 12.5px var(--sans); cursor: pointer; }
.pf-size-unit[data-unit="cm"] { color: var(--accent); border-color: var(--accent); }
.pf-size-story { display: flex; flex-direction: column; gap: 6px; }
.pf-size-line { background: none; border: none; padding: 0; text-align: left; font-size: 13.5px; color: var(--accent); cursor: pointer; text-decoration: underline; text-underline-offset: 3px; }
.pf-size-asked { font-size: 12.5px; color: var(--mut); }
.pf-size-inline { margin-top: 6px; padding: 10px; border: 1px dashed var(--line2); border-radius: 10px; }
.pf-size-apply { width: auto; margin-top: 8px; padding: 9px 14px; font-size: 14px; }
@media (max-width: 400px) { .pf-size-chips { max-width: 100%; } }
@media (max-width: 720px) { .pf-corner-img { max-height: 48vh; } }

.pf-detecting { display: flex; align-items: center; gap: 9px; margin-top: 12px; font-size: 14px; color: var(--mut); }
.pf-corner-stage { display: flex; justify-content: center; }
.pf-corner-box { position: relative; display: inline-block; background: var(--stage); padding: 14px; border-radius: 8px; touch-action: none; max-width: 100%; }
.pf-corner-img { display: block; max-width: min(560px, 78vw); max-height: 60vh; width: auto; height: auto; border-radius: 3px; }
.pf-corner-quad { position: absolute; inset: 14px; width: calc(100% - 28px); height: calc(100% - 28px); pointer-events: none; }
.pf-corner-quad path { fill: rgba(165,80,47,0.07); stroke: var(--accent); stroke-width: 2; stroke-dasharray: 7 5; vector-effect: non-scaling-stroke; }
.pf-pin { position: absolute; width: 30px; height: 30px; margin: -15px 0 0 -15px; border-radius: 50%; background: var(--accent); border: 3px solid var(--toggle-knob); box-shadow: 0 3px 8px rgba(0,0,0,0.35); cursor: grab; padding: 0; touch-action: none; }
.pf-pin:active { cursor: grabbing; }
.pf-corner-actions { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-top: 18px; }

.pf-lb { position: fixed; inset: 0; z-index: 60; }
.pf-lb-scrim { position: absolute; inset: 0; background: var(--modal-backdrop); }
.pf-lb-inner { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px; padding: 18px; pointer-events: none; }
.pf-lb-bar { display: flex; align-items: center; gap: 10px; pointer-events: auto; }
.pf-lb-tabs { display: flex; background: var(--card2); border: 1px solid var(--line2); border-radius: 11px; padding: 4px; gap: 4px; }
.pf-lb-tab { padding: 8px 14px; border: none; border-radius: 8px; background: none; color: var(--ink2); font: 600 14px var(--sans); cursor: pointer; }
.pf-lb-tab[data-active] { background: var(--card); color: var(--accent); box-shadow: 0 2px 6px var(--shadow); }
.pf-lb-close { width: 42px; height: 42px; background: var(--card2); border: 1px solid var(--line2); border-radius: 11px; color: var(--ink2); font-size: 17px; cursor: pointer; }
.pf-lb-stage { pointer-events: auto; max-width: 92vw; max-height: 78vh; overflow: auto; background: var(--card); border-radius: 10px; padding: 14px; box-shadow: 0 24px 60px rgba(0,0,0,0.5); }
.pf-lb-photo { display: block; max-width: 84vw; max-height: 70vh; width: auto; height: auto; border-radius: 4px; }
.pf-lb-quilt { width: min(560px, 84vw); }
.pf-lb-side { display: flex; gap: 16px; flex-wrap: wrap; align-items: flex-start; }

.pf-rt { display: flex; flex-direction: column; gap: 8px; margin-top: 6px; padding-top: 12px; border-top: 2px dashed var(--line2); }
.pf-rt-head { display: flex; align-items: center; gap: 12px; }
.pf-rt-title { margin: 0; font: 700 17.5px var(--serif); color: var(--denim); }
.pf-rt-rule { flex: 1; border-top: 2px dashed var(--line2); }
.pf-rt-pill { font-size: 12.5px; color: var(--mut); border: 1px solid var(--pillLn); border-radius: 999px; padding: 3px 10px; background: var(--pill); }
.pf-rt-lede { margin: 0; font-size: 13px; color: var(--faint); line-height: 1.5; }
.pf-rt-controls { display: flex; gap: 10px; align-items: flex-end; flex-wrap: wrap; }
.pf-rt-field { display: flex; flex-direction: column; gap: 4px; }
.pf-rt-field-label { font-size: 11px; text-transform: uppercase; letter-spacing: .08em; color: var(--faint); }
.pf-rt-select { padding: 9px 10px; font: 500 14px var(--sans); color: var(--ink2); background: var(--card); border: 1.5px solid var(--line2); border-radius: 9px; cursor: pointer; }
.pf-rt .pf-btn--secondary { width: auto; }
.pf-rt-report { display: flex; flex-direction: column; gap: 2px; margin-top: 4px; padding: 10px 12px; border-radius: 10px; font-size: 14px; border: 1px solid var(--line); background: var(--card3); }
.pf-rt-report--ok { border-color: var(--sageLn); background: var(--sageBg); color: var(--sage); }
.pf-rt-report--bad { border-color: var(--accent); color: var(--accent); }
.pf-rt-report-line { font-weight: 700; }
`;
