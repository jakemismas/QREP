/**
 * SHA-256 in plain JavaScript (C3a, issue #149). The annotate page names a
 * photo by its sha256, and a phone served the page over the home network is
 * not in a secure context, so crypto.subtle is missing there.
 *
 * Expected values: the FIPS 180-2 test vectors (NIST, Secure Hash Standard,
 * appendix B.1 to B.3) and the published digest of the empty message.
 */
import { describe, expect, it } from "vitest";
import { sha256Hex } from "./sha256";

const ascii = (text: string) => new TextEncoder().encode(text);

describe("sha256Hex", () => {
  it("hashes the one-block message abc (FIPS 180-2 B.1)", () => {
    expect(sha256Hex(ascii("abc"))).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  });

  it("hashes the two-block 448-bit message (FIPS 180-2 B.2)", () => {
    expect(sha256Hex(ascii("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"))).toBe(
      "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1",
    );
  });

  it("hashes one million a's (FIPS 180-2 B.3)", () => {
    expect(sha256Hex(new Uint8Array(1_000_000).fill(0x61))).toBe(
      "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0",
    );
  });

  it("hashes the empty message", () => {
    expect(sha256Hex(new Uint8Array(0))).toBe("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
  });
});
