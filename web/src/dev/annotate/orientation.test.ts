/**
 * The page shows a photo's pixels as the file stores them (PR #247 review of
 * 0b7e9a3, major 4): corpus annotations index the stored pixels, read by a
 * decoder that ignores orientation (scripts/eval/corpus_screen.py:50-52).
 * Every byte below is built by hand from the JPEG and EXIF layouts: a segment
 * is FF, a marker byte and a two-byte big-endian length that counts itself;
 * the APP1 body is "Exif" 00 00 and a TIFF header ("MM" big-endian or "II"
 * little-endian, 42, the offset of IFD0 from the header); an IFD is a two-byte
 * count of twelve-byte entries (tag, type, count, value) and a four-byte next
 * offset. Orientation is tag 0x0112, type 3 (SHORT), count 1.
 */
import { describe, expect, it } from "vitest";
import { readOrientation, withoutOrientation } from "./orientation";

const SOI = [0xff, 0xd8];
const EOI = [0xff, 0xd9];
// "Exif" 00 00
const EXIF_ID = [0x45, 0x78, 0x69, 0x66, 0x00, 0x00];

/**
 * An APP1 segment whose IFD0 holds a 0x0100 ImageWidth entry (LONG 800)
 * first, then Orientation. Length: 2 (itself) + 6 (Exif id) + 8 (TIFF
 * header) + 2 (count) + 2 x 12 (entries) + 4 (next offset) = 46 = 0x2e.
 */
function app1(order: "MM" | "II", orientation: number): number[] {
  if (order === "MM") {
    return [
      0xff, 0xe1, 0x00, 0x2e, ...EXIF_ID,
      0x4d, 0x4d, 0x00, 0x2a, 0x00, 0x00, 0x00, 0x08,
      0x00, 0x02,
      0x01, 0x00, 0x00, 0x04, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x03, 0x20,
      0x01, 0x12, 0x00, 0x03, 0x00, 0x00, 0x00, 0x01, 0x00, orientation, 0x00, 0x00,
      0x00, 0x00, 0x00, 0x00,
    ];
  }
  return [
    0xff, 0xe1, 0x00, 0x2e, ...EXIF_ID,
    0x49, 0x49, 0x2a, 0x00, 0x08, 0x00, 0x00, 0x00,
    0x02, 0x00,
    0x00, 0x01, 0x04, 0x00, 0x01, 0x00, 0x00, 0x00, 0x20, 0x03, 0x00, 0x00,
    0x12, 0x01, 0x03, 0x00, 0x01, 0x00, 0x00, 0x00, orientation, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00,
  ];
}

// A JFIF APP0 segment: length 16 = 2 + "JFIF" 00 (5) + version (2) + units (1)
// + densities (4) + thumbnail size (2).
const APP0 = [0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00];

// The Orientation value's offset. SOI (2) + APP1 marker and length (4) +
// Exif id (6) = 12, where the TIFF header starts; IFD0 at 12 + 8 = 20; its
// count takes 20 and 21; the first entry 22 to 33; the second entry starts at
// 34, its tag 34-35, type 36-37, count 38-41, value 42-45. A SHORT value sits
// in the value field's first two bytes, in the header's byte order.
const VALUE_AT = 42;

describe("reading and clearing a JPEG's EXIF orientation", () => {
  it("reads orientation 6 from a big-endian IFD0 entry that is not the first", () => {
    const bytes = new Uint8Array([...SOI, ...app1("MM", 6), ...EOI]);
    expect(readOrientation(bytes)).toBe(6);
  });

  it("sets a big-endian orientation to 1 in a copy and changes no other byte", () => {
    const bytes = new Uint8Array([...SOI, ...app1("MM", 6), ...EOI]);
    const before = Array.from(bytes);
    const shown = withoutOrientation(bytes);
    // Big-endian SHORT 1 is 00 01, at 42 and 43.
    const expected = [...before];
    expected[VALUE_AT] = 0x00;
    expected[VALUE_AT + 1] = 0x01;
    expect(Array.from(shown)).toEqual(expected);
    expect(readOrientation(shown)).toBe(1);
    // The input keeps its bytes, so its sha256 is the file's.
    expect(Array.from(bytes)).toEqual(before);
  });

  it("sets a little-endian orientation to 1", () => {
    const bytes = new Uint8Array([...SOI, ...app1("II", 8), ...EOI]);
    expect(readOrientation(bytes)).toBe(8);
    const shown = withoutOrientation(bytes);
    // Little-endian SHORT 1 is 01 00, at 42 and 43.
    expect(shown[VALUE_AT]).toBe(0x01);
    expect(shown[VALUE_AT + 1]).toBe(0x00);
    expect(readOrientation(shown)).toBe(1);
  });

  it("finds the APP1 segment after a JFIF APP0 segment", () => {
    const bytes = new Uint8Array([...SOI, ...APP0, ...app1("MM", 3), ...EOI]);
    expect(readOrientation(bytes)).toBe(3);
    const shown = withoutOrientation(bytes);
    // APP0 takes 18 bytes, so the value moves from 42 to 42 + 18 = 60.
    expect(shown[VALUE_AT + 18]).toBe(0x00);
    expect(shown[VALUE_AT + 18 + 1]).toBe(0x01);
  });

  it("returns a file with no orientation to clear as it is", () => {
    const plain = new Uint8Array([...SOI, ...APP0, ...EOI]);
    expect(readOrientation(plain)).toBeNull();
    expect(withoutOrientation(plain)).toBe(plain);
    const upright = new Uint8Array([...SOI, ...app1("MM", 1), ...EOI]);
    expect(withoutOrientation(upright)).toBe(upright);
    // A PNG signature: 89 "PNG" 0D 0A 1A 0A.
    const png = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
    expect(readOrientation(png)).toBeNull();
    expect(withoutOrientation(png)).toBe(png);
  });

  it("leaves a truncated EXIF segment alone instead of throwing", () => {
    // The APP1 segment cut after 40 bytes, so the file ends at 2 + 40 = 42:
    // the Orientation entry keeps its tag, type and count (34 to 41) but loses
    // its value at 42. Read past the end, the value would come out as 0.
    const cut = new Uint8Array([...SOI, ...app1("MM", 6).slice(0, 40)]);
    expect(readOrientation(cut)).toBeNull();
    expect(withoutOrientation(cut)).toBe(cut);
  });

  it("reads an EXIF id whose sixth byte is not 00", () => {
    // "Exif" 00 FF: byte 11, the id's sixth, set to FF.
    const bytes = new Uint8Array([...SOI, ...app1("MM", 6), ...EOI]);
    bytes[11] = 0xff;
    expect(readOrientation(bytes)).toBe(6);
    expect(readOrientation(withoutOrientation(bytes))).toBe(1);
  });
});
