/**
 * Contract version check (E1a, issue #174): the worker reads the engine's
 * contract_version() envelope at boot and refuses to finish booting when it
 * differs from this app's CONTRACT_VERSION.
 */
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  assertEngineContract,
  bridgeArgs,
  CONTRACT_VERSION,
  contractMismatch,
  engineAssetUrl,
  engineContractVersion,
  OUTCOMES,
  OutcomeError,
  PATTERN_OUTCOMES,
  parseOutcome,
  parsePatternResult,
  parseReadResult,
  parseSizeResult,
  READ_OUTCOMES,
  SIZE_OUTCOMES,
} from "./contract";

const envelope = (version: unknown) =>
  JSON.stringify({ ok: true, result: { contract_version: version } });

describe("engineContractVersion", () => {
  it("reads the version from an ok envelope", () => {
    expect(engineContractVersion('{"ok": true, "result": {"contract_version": 2}}')).toBe(2);
  });

  it("reads no version from a wheel that predates contract_version()", () => {
    // The worker passes undefined when qrep.bridge has no contract_version.
    expect(engineContractVersion(undefined)).toBeNull();
  });

  it("reads no version from a malformed or error envelope", () => {
    expect(engineContractVersion("{not json")).toBeNull();
    expect(engineContractVersion('{"ok": false, "error": {"kind": "internal", "message": "x"}}')).toBeNull();
    expect(engineContractVersion('{"ok": true, "result": {}}')).toBeNull();
    expect(engineContractVersion('{"ok": true, "result": {"contract_version": "2"}}')).toBeNull();
    expect(engineContractVersion('{"ok": true, "result": {"contract_version": 2.5}}')).toBeNull();
    expect(engineContractVersion("null")).toBeNull();
  });
});

describe("contractMismatch", () => {
  it("passes an engine that speaks this app's version", () => {
    expect(contractMismatch(CONTRACT_VERSION)).toBeNull();
    expect(contractMismatch(2, 2)).toBeNull();
  });

  it("names both versions and asks for a reload on a mismatch", () => {
    const message = contractMismatch(1, 2);
    expect(message).toContain("contract version 2");
    expect(message).toContain("version 1");
    expect(message).toMatch(/reload/i);
  });

  it("names an engine that reports no version", () => {
    const message = contractMismatch(null, 2);
    expect(message).toContain("contract version 2");
    expect(message).toContain("no contract version");
    expect(message).toMatch(/reload/i);
  });

  it("refuses an engine newer than the app, not only an older one", () => {
    const message = contractMismatch(3, 2);
    expect(message).toContain("contract version 2");
    expect(message).toContain("version 3");
  });
});

describe("assertEngineContract", () => {
  it("passes when the engine reports this app's version", () => {
    expect(() => assertEngineContract(() => envelope(CONTRACT_VERSION))).not.toThrow();
  });

  it("asks the engine through contract_version()", () => {
    const asked: string[] = [];
    assertEngineContract((code) => {
      asked.push(code);
      return envelope(CONTRACT_VERSION);
    });
    expect(asked).toHaveLength(1);
    expect(asked[0]).toContain("qrep.bridge.contract_version()");
  });

  it("throws the mismatch message for another version", () => {
    expect(() => assertEngineContract(() => envelope(CONTRACT_VERSION + 1))).toThrow(
      `version ${CONTRACT_VERSION + 1}`,
    );
  });

  it("throws for a wheel that predates contract_version()", () => {
    // Python None reaches JS as undefined.
    expect(() => assertEngineContract(() => undefined)).toThrow("no contract version");
  });
});

describe("bridgeArgs", () => {
  it("turns null into undefined so Pyodide passes None", () => {
    expect(bridgeArgs(["{}", 240, null])).toEqual(["{}", 240, undefined]);
  });

  it("leaves every other value alone", () => {
    const bytes = new Uint8Array([1, 2]);
    const args = ["text", 0, false, "", bytes, undefined];
    const out = bridgeArgs(args);
    expect(out).toEqual(args);
    expect(out[4]).toBe(bytes);
  });
});

describe("worker boot", () => {
  // The worker module needs a Pyodide runtime, so this pins the wiring in its
  // source: removing the check, or moving it after boot-done, fails here.
  const source = readFileSync(new URL("./worker.ts", import.meta.url), "utf8");
  const boot = source.slice(source.indexOf("async function boot("), source.indexOf("async function serve("));

  it("checks the contract after importing the bridge and before returning", () => {
    const imported = boot.indexOf('pyodide.runPython("import qrep.bridge")');
    const checked = boot.indexOf("assertEngineContract(");
    const returned = boot.indexOf("return pyodide;");
    expect(imported).toBeGreaterThan(-1);
    expect(checked).toBeGreaterThan(imported);
    expect(returned).toBeGreaterThan(checked);
  });

  it("passes every bridge call through bridgeArgs", () => {
    expect(source).toContain("bridge[method](...bridgeArgs(args))");
  });
});

describe("parseOutcome", () => {
  // SPEC.md section 12.1: a missing or unknown outcome is an error, never a
  // success (the verdictStory.ts:82 hazard, where a missing verdict read as
  // readable).
  it("rejects a result with no outcome", () => {
    expect(() => parseOutcome({}, OUTCOMES)).toThrow(OutcomeError);
    expect(() => parseOutcome({ outcome: null }, OUTCOMES)).toThrow("states no outcome");
    expect(() => parseOutcome({ pdf_b64: "JVBERi0=" }, PATTERN_OUTCOMES)).toThrow(OutcomeError);
  });

  it("rejects a result that is not an object", () => {
    for (const result of [undefined, null, "pattern_ready", ["pattern_ready"], 1]) {
      expect(() => parseOutcome(result, OUTCOMES)).toThrow("no result object");
    }
  });

  it("rejects an unknown outcome", () => {
    expect(() => parseOutcome({ outcome: "readable" }, OUTCOMES)).toThrow("unknown outcome");
    expect(() => parseOutcome({ outcome: 1 }, OUTCOMES)).toThrow("unknown outcome: 1");
  });

  it("accepts each known outcome", () => {
    for (const outcome of OUTCOMES) {
      expect(parseOutcome({ outcome }, OUTCOMES)).toBe(outcome);
    }
    expect([...READ_OUTCOMES, ...SIZE_OUTCOMES, ...PATTERN_OUTCOMES].sort()).toEqual(
      [...OUTCOMES, "refused"].sort(),
    );
  });

  it("rejects a known outcome that this call does not return", () => {
    expect(() => parseOutcome({ outcome: "read" }, PATTERN_OUTCOMES)).toThrow(
      "this call returns pattern_ready or refused",
    );
  });
});

describe("per-call result parsers", () => {
  const reason = { code: "too_many_fabrics", message: "More than 12 fabrics." };
  const summary = { finished_width: 600 };

  it("passes complete results through", () => {
    const ready = { outcome: "pattern_ready", pdf_b64: "JVBERi0=", summary, reason: null };
    expect(parsePatternResult(ready)).toBe(ready);
    const refused = { outcome: "refused", reason };
    expect(parsePatternResult(refused)).toBe(refused);
    expect(parseReadResult({ outcome: "read", model: {} }).outcome).toBe("read");
    expect(parseReadResult({ outcome: "held", reason }).outcome).toBe("held");
    expect(parseSizeResult({ outcome: "sized", model: {}, basis: {} }).outcome).toBe("sized");
  });

  it("never treats an incomplete success as success", () => {
    expect(() => parsePatternResult({ outcome: "pattern_ready", summary })).toThrow("pdf_b64");
    expect(() => parsePatternResult({ outcome: "pattern_ready", pdf_b64: "x" })).toThrow(
      "summary",
    );
    expect(() => parseReadResult({ outcome: "read", model: null })).toThrow("model");
    expect(() => parseSizeResult({ outcome: "sized", model: {} })).toThrow("basis");
  });

  it("needs a reason on a hold or a refusal", () => {
    expect(() => parsePatternResult({ outcome: "refused" })).toThrow("reason");
    expect(() => parseReadResult({ outcome: "held", reason: { code: "x" } })).toThrow("reason");
  });

  it("rejects another call's outcome", () => {
    expect(() => parseSizeResult({ outcome: "pattern_ready", pdf_b64: "x", summary })).toThrow(
      "this call returns sized",
    );
    expect(() => parseReadResult({ outcome: "sized", model: {}, basis: {} })).toThrow(
      "this call returns read or held or refused",
    );
  });

  it("throws the typed OutcomeError", () => {
    let thrown: unknown;
    try {
      parseOutcome({}, OUTCOMES);
    } catch (error) {
      thrown = error;
    }
    expect(typeof OutcomeError).toBe("function");
    expect(thrown).toBeInstanceOf(OutcomeError);
    expect((thrown as Error).name).toBe("OutcomeError");
  });
});

describe("engineAssetUrl", () => {
  it("tags a wheels-folder file with the contract version", () => {
    expect(engineAssetUrl("/QREP/", "manifest.json")).toBe(
      `/QREP/wheels/manifest.json?contract=${CONTRACT_VERSION}`,
    );
    expect(engineAssetUrl("/", "qrep-0.3.0-py3-none-any.whl")).toBe(
      `/wheels/qrep-0.3.0-py3-none-any.whl?contract=${CONTRACT_VERSION}`,
    );
  });
});

describe("worker v2 wiring", () => {
  const source = readFileSync(new URL("./worker.ts", import.meta.url), "utf8");

  it("fetches the manifest and every wheel through engineAssetUrl", () => {
    expect(source).toContain('fetch(engineAssetUrl(baseUrl, "manifest.json"))');
    expect(source).toContain("engineAssetUrl(baseUrl, file)");
    expect(source).not.toContain("wheels/manifest.json");
  });

  it("loads the vision wheel before the confirmed read", () => {
    const vision = source.slice(source.indexOf("const VISION_METHODS"), source.indexOf("]);", source.indexOf("const VISION_METHODS")));
    expect(vision).toContain('"read_confirmed"');
  });
});
