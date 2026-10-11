/*
 * The S7 size block (UI-SPEC section 2) and the results size line that hosts
 * it (UI-SPEC 2.4). One block, two hosts: the crop screen and the results
 * inline editor. Squares vocabulary; mixed fractions everywhere.
 */
import { useEffect, useState } from "react";
import { formatEighths } from "../../model/units";
import { formatCmEquivalent } from "../../model/sizeEntry";
import { PRESETS } from "../../model/sizing";
import type { QuiltModel } from "../../model/types";
import type { PhotoApi } from "../photoApi";
import "./shared.css";
import "./SizeBlock.css";

/** PRESET chips, W x H fraction inputs, in/cm toggle. */
export function SizeBlock({ photo, compact }: { photo: PhotoApi; compact?: boolean }) {
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
export function SizeStory({ photo, model }: { photo: PhotoApi; model: QuiltModel }) {
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
