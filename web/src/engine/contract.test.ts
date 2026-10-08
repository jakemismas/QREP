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
  engineContractVersion,
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
