/**
 * S2 crop-flow transition matrix (sprint 3, issue #68).
 *
 * The machine is pure state: engine effects (stage_photo, detect_quad,
 * reverse) live in the provider; detection results arrive via
 * detectionResolved(seq, ...) so the user-pin-wins race and the
 * second-photo staleness rule are testable without React or a worker.
 * Every expected value below is the hand-written contract from the plan
 * and UI-SPEC section 1, never observed output.
 */
import { describe, expect, it } from "vitest";
import { DEFAULT_PIN_CORNERS, PhotoFlowMachine } from "./photoFlow";

const DETECTED: [number, number][] = [
  [0.1, 0.2],
  [0.9, 0.2],
  [0.9, 0.8],
  [0.1, 0.8],
];

describe("PhotoFlowMachine", () => {
  it("stage enters crop with default inset pins and detection pending", () => {
    const m = new PhotoFlowMachine();
    const seq = m.enterCrop();
    expect(m.state).toBe("crop");
    expect(m.corners).toEqual(DEFAULT_PIN_CORNERS);
    expect(m.quadSource).toBe("default");
    expect(m.detectPending).toBe(true);
    expect(seq).toBe(1);
  });

  it("detection snap-in: untouched pins adopt the detected quad", () => {
    const m = new PhotoFlowMachine();
    const seq = m.enterCrop();
    m.detectionResolved(seq, { quad: DETECTED, tier: 1, confidence: 0.9 });
    expect(m.corners).toEqual(DETECTED);
    expect(m.quadSource).toBe("detected");
    expect(m.detectPending).toBe(false);
    expect(m.detectedQuad).toEqual(DETECTED);
  });

  it("user wins the race: a moved pin is never overwritten by detection", () => {
    const m = new PhotoFlowMachine();
    const seq = m.enterCrop();
    m.movePin(0, [0.3, 0.3]);
    m.detectionResolved(seq, { quad: DETECTED, tier: 1, confidence: 0.9 });
    // pin 0 keeps the user's position; detection is recorded for Reset to auto
    expect(m.corners[0]).toEqual([0.3, 0.3]);
    expect(m.quadSource).toBe("user");
    expect(m.detectedQuad).toEqual(DETECTED);
    expect(m.detectPending).toBe(false);
  });

  it("analyze passes corners ONLY when the user moved a pin", () => {
    const m = new PhotoFlowMachine();
    const seq = m.enterCrop();
    m.detectionResolved(seq, { quad: DETECTED, tier: 1, confidence: 0.9 });
    // untouched (detected) pins: the pipeline re-detects the same quad, so
    // no corners ride along and frozen results stay bit-identical
    expect(m.analyze()).toBeNull();
    expect(m.state).toBe("progress");
  });

  it("analyze passes the moved pins verbatim", () => {
    const m = new PhotoFlowMachine();
    m.enterCrop();
    m.movePin(2, [0.7, 0.6]);
    const passed = m.analyze();
    expect(passed).not.toBeNull();
    expect(passed![2]).toEqual([0.7, 0.6]);
  });

  it("results then Adjust-the-crop seeds the confirmed quad", () => {
    const m = new PhotoFlowMachine();
    const seq = m.enterCrop();
    m.detectionResolved(seq, { quad: DETECTED, tier: 1, confidence: 0.9 });
    m.analyze();
    m.results();
    m.seedFromConfirmed();
    expect(m.state).toBe("crop");
    // the confirmed quad is what the analyze ran with: the detected pins
    expect(m.corners).toEqual(DETECTED);
    expect(m.quadSource).toBe("seeded");
    // seeded-but-unmoved re-analyze passes nothing (deterministic re-run)
    expect(m.analyze()).toBeNull();
  });

  it("cancel from progress returns to idle and clears the session", () => {
    // PARITY item 14 (sprint 2, frozen): cancel returns to the dropzone
    const m = new PhotoFlowMachine();
    m.enterCrop();
    m.analyze();
    m.cancel();
    expect(m.state).toBe("idle");
    expect(m.detectedQuad).toBeNull();
    expect(m.quadSource).toBe("default");
  });

  it("back from crop returns to idle and clears the session", () => {
    const m = new PhotoFlowMachine();
    m.enterCrop();
    m.movePin(0, [0.5, 0.5]);
    m.backFromCrop();
    expect(m.state).toBe("idle");
    expect(m.corners).toEqual(DEFAULT_PIN_CORNERS);
  });

  it("a second photo starts from ITS detection, never the previous corners", () => {
    const m = new PhotoFlowMachine();
    const seq1 = m.enterCrop();
    m.movePin(0, [0.4, 0.4]);
    m.cancel();
    const seq2 = m.enterCrop();
    expect(seq2).toBe(seq1 + 1);
    expect(m.corners).toEqual(DEFAULT_PIN_CORNERS);
    expect(m.quadSource).toBe("default");
    // a stale detection from photo 1 resolving late is ignored entirely
    m.detectionResolved(seq1, { quad: DETECTED, tier: 1, confidence: 0.9 });
    expect(m.corners).toEqual(DEFAULT_PIN_CORNERS);
    expect(m.detectedQuad).toBeNull();
    // photo 2's own detection still snaps in
    m.detectionResolved(seq2, { quad: DETECTED, tier: 2, confidence: 0.7 });
    expect(m.corners).toEqual(DETECTED);
  });

  it("Reset to auto restores the detected quad after a user move", () => {
    const m = new PhotoFlowMachine();
    const seq = m.enterCrop();
    m.detectionResolved(seq, { quad: DETECTED, tier: 1, confidence: 0.9 });
    m.movePin(1, [0.5, 0.5]);
    m.resetToAuto();
    expect(m.corners).toEqual(DETECTED);
    expect(m.quadSource).toBe("detected");
    // analyze after reset passes nothing again (back to the detected basis)
    expect(m.analyze()).toBeNull();
  });

  it("Reset to auto without a detection restores the default pins", () => {
    const m = new PhotoFlowMachine();
    m.enterCrop();
    m.movePin(3, [0.2, 0.9]);
    m.resetToAuto();
    expect(m.corners).toEqual(DEFAULT_PIN_CORNERS);
    expect(m.quadSource).toBe("default");
  });

  it("sample bypass: straight to progress, no crop, default pins untouched", () => {
    const m = new PhotoFlowMachine();
    m.bypassToProgress();
    expect(m.state).toBe("progress");
    expect(m.corners).toEqual(DEFAULT_PIN_CORNERS);
    expect(m.quadSource).toBe("default");
    m.results();
    expect(m.state).toBe("results");
    m.cancel();
    expect(m.state).toBe("idle");
  });

  it("detection failure just clears the pending flag; pins stay usable", () => {
    const m = new PhotoFlowMachine();
    const seq = m.enterCrop();
    m.detectionFailed(seq);
    expect(m.detectPending).toBe(false);
    expect(m.corners).toEqual(DEFAULT_PIN_CORNERS);
    expect(m.analyze()).toBeNull();
  });
});
