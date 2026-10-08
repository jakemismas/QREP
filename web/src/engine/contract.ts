/**
 * Bridge v2 contract (E1a, issue #174): the TypeScript half of
 * qrep/contract.py, and the single home for the bridge's result types.
 *
 * Any change to the bridge's request or response shapes bumps
 * CONTRACT_VERSION here and in qrep/contract.py in the same commit;
 * tests/test_bridge.py fails when the two literals differ.
 */

export const CONTRACT_VERSION = 2;

/**
 * The version in bridge.contract_version()'s raw envelope, or null when the
 * engine reports none: a wheel that predates the function (raw is
 * undefined), or an envelope that is malformed, an error, or carries no
 * whole-number version.
 */
export function engineContractVersion(raw: unknown): number | null {
  if (typeof raw !== "string") return null;
  let envelope: unknown;
  try {
    envelope = JSON.parse(raw);
  } catch {
    return null;
  }
  if (typeof envelope !== "object" || envelope === null) return null;
  const { ok, result } = envelope as { ok?: unknown; result?: unknown };
  if (ok !== true || typeof result !== "object" || result === null) return null;
  const version = (result as { contract_version?: unknown }).contract_version;
  return typeof version === "number" && Number.isInteger(version) ? version : null;
}

/**
 * The boot-failed message when the engine's contract differs from this
 * app's, or null when they agree. A mismatch means the browser holds a page
 * and an engine wheel from different releases, so a reload fetches a
 * matching pair.
 */
export function contractMismatch(
  engineVersion: number | null,
  appVersion = CONTRACT_VERSION,
): string | null {
  if (engineVersion === appVersion) return null;
  const reported = engineVersion === null ? "no contract version" : `version ${engineVersion}`;
  return (
    `This app needs engine contract version ${appVersion}, but the loaded engine reports ` +
    `${reported}. Reload the page to load a matching engine.`
  );
}
