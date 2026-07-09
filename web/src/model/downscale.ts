/**
 * Device-classed downscale caps (S6, issue #46). Photos are downscaled in
 * JS before any bytes reach the pipeline: a 12MP original would peak at
 * hundreds of MB of float32 intermediates in wasm. Phones get a tighter
 * cap than desktop/tablet.
 */

export const CAP_PHONE = 1400;
export const CAP_DESKTOP = 2000;

export type DeviceClass = "phone" | "desktop";

export function capFor(deviceClass: DeviceClass): number {
  return deviceClass === "phone" ? CAP_PHONE : CAP_DESKTOP;
}

/** The phone class matches the app's <720px layout breakpoint. */
export function classifyDevice(viewportWidth: number): DeviceClass {
  return viewportWidth < 720 ? "phone" : "desktop";
}

export function targetSize(
  width: number,
  height: number,
  deviceClass: DeviceClass,
): { width: number; height: number; scaled: boolean } {
  const cap = capFor(deviceClass);
  const longest = Math.max(width, height);
  if (longest <= cap) return { width, height, scaled: false };
  const factor = cap / longest;
  return {
    width: Math.round(width * factor),
    height: Math.round(height * factor),
    scaled: true,
  };
}
