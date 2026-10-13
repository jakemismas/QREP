/*
 * Dropzone (photo.state === "idle"): file input, drag and drop, and the
 * sample photo.
 */
import { useRef } from "react";
import type { PhotoApi } from "../photoApi";
import "./shared.css";
import "./DropzoneScreen.css";

export function DropzoneScreen({ photo, onHome }: { photo: PhotoApi; onHome: () => void }) {
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
