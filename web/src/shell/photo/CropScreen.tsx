/*
 * Crop (photo.state === "crop"): the photo with draggable pins BEFORE any
 * analysis; the detected quad snaps in unless the user already moved a pin.
 * "Adjust the crop" on results returns here seeded with the confirmed quad
 * (UI-SPEC section 1).
 */
import type { PhotoApi } from "../photoApi";
import { PinOverlay } from "./PinOverlay";
import { SizeBlock } from "./SizeBlock";
import "./shared.css";
import "./CropScreen.css";

export function CropScreen({ photo }: { photo: PhotoApi }) {
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
