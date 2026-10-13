/*
 * Dropzone (photo.state === "idle"): file input, drag and drop, capture tips
 * and the sample photo. A dropped file is decoded here; only a photo the
 * browser can open moves on to the confirm screen (C3b, issue #101; ux-16).
 */
import { useRef } from "react";
import type { PhotoApi } from "../photoApi";
import "./shared.css";
import "./DropzoneScreen.css";

// ---- Accepted formats -------------------------------------------------------
// The picker's accept list and the copy that names its formats change together
// (ux-16: the list said image/* while the copy said JPG or PNG). The HEIC
// research on #101 (plan risk 4) kept JPEG and PNG. To change the formats,
// edit these two constants and DECODE_ERROR in confirm/stagePhoto.ts, which
// names the same formats.
export const PHOTO_ACCEPT = "image/jpeg,image/png";
export const PHOTO_FORMATS = "JPG or PNG";
// ---------------------------------------------------------------------------

export function DropzoneScreen({ photo, onHome }: { photo: PhotoApi; onHome: () => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const decoding = photo.confirm.status === "decoding";
  const error = photo.confirm.status === "failed" ? photo.confirm.error : null;

  const takeFile = (file: File | undefined): void => {
    if (file) void photo.stage(file);
  };

  return (
    <div className="pf-wrap pf-wrap--dz" data-screen-label="Photo dropzone">
      <button type="button" className="pf-home" onClick={onHome}>
        &larr; Home
      </button>
      <h1 className="pf-h1">Start from a photo</h1>
      <p className="pf-lede">
        Photograph a traditional or antique quilt, or one you own, lying flat.
        A photo, a screenshot, or a shop listing picture all work.
      </p>

      <div className="pf-dz-row">
        <div className="pf-dz-pick">
          <div
            className="pf-dropzone"
            data-testid="photo-dropzone"
            role="button"
            tabIndex={0}
            aria-busy={decoding || undefined}
            onClick={() => inputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
            }}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              takeFile(e.dataTransfer.files?.[0]);
            }}
          >
            <svg width="52" height="44" aria-hidden="true" className="pf-camera">
              <rect x="1.25" y="7.25" width="49.5" height="35.5" rx="5" />
              <path d="M17 7l4-5.75h10L35 7" />
              <circle cx="26" cy="24.5" r="9" />
            </svg>
            <span className="pf-dz-title">Drop your quilt photo here</span>
            <span className="pf-dz-sub">{PHOTO_FORMATS}, or tap to browse</span>
          </div>
          <input
            ref={inputRef}
            type="file"
            accept={PHOTO_ACCEPT}
            data-testid="photo-file-input"
            className="pf-file-input"
            onChange={(e) => {
              const file = e.target.files?.[0];
              // Cleared, so choosing the same file again after an error still fires a change.
              e.target.value = "";
              takeFile(file);
            }}
          />
          {decoding ? (
            <p className="pf-dz-status" data-testid="photo-decoding" role="status">
              <span className="pf-stage-spin" aria-hidden="true" />
              Opening your photo&hellip;
            </p>
          ) : null}
          {error ? (
            <p className="pf-dz-error" data-testid="photo-error" role="alert">
              {error}
            </p>
          ) : null}
        </div>

        <aside className="pf-capture" data-testid="capture-tips" aria-labelledby="pf-capture-title">
          <h2 className="pf-capture-title" id="pf-capture-title">
            For the best result
          </h2>
          <ul className="pf-capture-list">
            <li>Lay the whole quilt flat and photograph it square-on, with a margin around it.</li>
            <li>Use even light without glare.</li>
            <li>For a screenshot, zoom in until the quilt fills the screen before you capture it.</li>
          </ul>
        </aside>
      </div>

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
