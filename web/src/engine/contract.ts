/**
 * Bridge v2 contract (E1a, issue #174): the TypeScript half of
 * qrep/contract.py. It holds the contract version and the worker's boundary
 * helpers; E1b adds the v2 request and result types here, the single TS
 * result-types file (plan section 4.2).
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

// hasattr keeps a wheel that predates contract_version() from raising here;
// it returns None, which reaches JS as undefined and reads as no version.
const CONTRACT_PROBE =
  "import qrep.bridge\n" +
  "qrep.bridge.contract_version() if hasattr(qrep.bridge, 'contract_version') else None";

/**
 * Throws the boot-failed message unless the imported engine speaks this
 * app's contract. The worker calls it after `import qrep.bridge` and before
 * boot-done, passing Pyodide's runPython.
 */
export function assertEngineContract(runPython: (code: string) => unknown): void {
  const mismatch = contractMismatch(engineContractVersion(runPython(CONTRACT_PROBE)));
  if (mismatch !== null) throw new Error(mismatch);
}

/**
 * Bridge call arguments with each null swapped for undefined. Pyodide 0.28
 * converts JS null to jsnull, not None, so an optional argument the UI
 * leaves null would reach the bridge as a wrong type; undefined becomes None.
 */
export function bridgeArgs(args: readonly unknown[]): unknown[] {
  return args.map((arg) => (arg === null ? undefined : arg));
}
