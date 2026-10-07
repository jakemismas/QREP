/**
 * Wheel freshness stamp (scripts/wheel-hash.mjs): the build, the Pyodide
 * suite and the local e2e run must refuse a qrep wheel built from other
 * sources. Runs the real helpers against a throwaway repo layout.
 */
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import * as path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  qrepSourceHash,
  wheelStampProblem,
  writeWheelStamp,
} from "../scripts/wheel-hash.mjs";

let repo: string;
let wheels: string;
const WHEEL = "qrep-9.9.9-py3-none-any.whl";

function write(rel: string, text: string) {
  const file = path.join(repo, rel);
  mkdirSync(path.dirname(file), { recursive: true });
  writeFileSync(file, text);
}

beforeEach(() => {
  repo = mkdtempSync(path.join(tmpdir(), "qrep-stamp-"));
  wheels = path.join(repo, "wheels");
  write("pyproject.toml", '[project]\nversion = "9.9.9"\n');
  write("qrep/__init__.py", '__version__ = "9.9.9"\n');
  write("qrep/vision/read.py", "def read():\n    return 1\n");
  write(`wheels/${WHEEL}`, "wheel bytes");
  writeWheelStamp(wheels, WHEEL, qrepSourceHash(repo));
});

afterEach(() => {
  rmSync(repo, { recursive: true, force: true });
});

describe("qrep wheel stamp", () => {
  it("accepts a wheel stamped from the current sources", () => {
    expect(wheelStampProblem(wheels, repo)).toBeNull();
  });

  it("refuses the wheel after a qrep source edit", () => {
    write("qrep/vision/read.py", "def read():\n    return 2\n");
    expect(wheelStampProblem(wheels, repo)).toMatch(/built from other qrep sources/);
  });

  it("refuses the wheel after a new qrep module appears", () => {
    write("qrep/vision/extra.py", "X = 1\n");
    expect(wheelStampProblem(wheels, repo)).toMatch(/built from other qrep sources/);
  });

  it("refuses the wheel after a pyproject edit", () => {
    write("pyproject.toml", '[project]\nversion = "9.9.10"\n');
    expect(wheelStampProblem(wheels, repo)).toMatch(/built from other qrep sources/);
  });

  it("ignores bytecode caches, which never reach the wheel", () => {
    write("qrep/__pycache__/read.cpython-313.pyc", "bytecode");
    write("qrep/vision/stale.pyc", "bytecode");
    expect(wheelStampProblem(wheels, repo)).toBeNull();
  });

  it("refuses a missing stamp and a missing stamped wheel", () => {
    rmSync(path.join(wheels, WHEEL));
    expect(wheelStampProblem(wheels, repo)).toMatch(/is missing from/);
    rmSync(path.join(wheels, "qrep-source-hash.json"));
    expect(wheelStampProblem(wheels, repo)).toMatch(/is missing$/);
  });
});
