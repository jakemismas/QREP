/**
 * Contract version check (E1a, issue #174): the worker reads the engine's
 * contract_version() envelope at boot and refuses to finish booting when it
 * differs from this app's CONTRACT_VERSION.
 */
import { describe, expect, it } from "vitest";
import { CONTRACT_VERSION, contractMismatch, engineContractVersion } from "./contract";

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
});
