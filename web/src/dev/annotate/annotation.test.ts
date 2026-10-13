/**
 * The dev annotate page's file handling (C3a, issue #149; plan section 8.2):
 * it reads D3a's annotation format (corpus/schema/annotation.schema.json) and
 * writes verified-jake claims beside the proposals, never over them.
 */
import { describe, expect, it } from "vitest";
import type { Corners } from "../../engine/contract";
import {
  aspectMatches,
  annotatedFrame,
  AnnotationError,
  frameProvenances,
  isNoBorderFrame,
  newAnnotation,
  sameStem,
  parseAnnotation,
  photoProblem,
  photoStem,
  saveProblems,
  serializeAnnotation,
  startingValues,
  withVerified,
  type Annotation,
} from "./annotation";

const SHA = "3ceb4eeb83a38a3d78576eb4282554ddd1c51644e8c212502800ec995672996e";
const OUTER: Corners = {
  top_left: { x: 100, y: 50 },
  top_right: { x: 500, y: 50 },
  bottom_right: { x: 500, y: 450 },
  bottom_left: { x: 100, y: 450 },
};
const FIELD: Corners = {
  top_left: { x: 140, y: 90 },
  top_right: { x: 460, y: 90 },
  bottom_right: { x: 460, y: 410 },
  bottom_left: { x: 140, y: 410 },
};
const COUNTS = { blocks_across: 8, blocks_down: 8, squares_per_block_across: 1, squares_per_block_down: 1 };

function proposed(): Annotation {
  return {
    schema_version: 1,
    photo: "images/lacma-54871.jpg",
    sha256: SHA,
    canvas: [800, 600],
    frame: [
      {
        value: { outer_edge: { kind: "outer_edge", corners: OUTER, bands: [{ width_squares: 1 }] }, field: null },
        provenance: "proposed-a",
      },
      {
        value: { outer_edge: { kind: "outer_edge", corners: FIELD, bands: [] }, field: null },
        provenance: "proposed-b",
      },
    ],
    counts: [{ value: COUNTS, provenance: "proposed-a" }],
    construction_class: [{ value: "hst", provenance: "proposed-b" }],
    finished_size: [
      {
        value: { width_in: 70, height_in: 80, approximate: true, source_text: "70 x 80 in." },
        provenance: "source-record",
      },
    ],
  };
}

describe("reading an annotation", () => {
  it("parses a file and keeps fields the page does not edit", () => {
    const parsed = parseAnnotation(JSON.stringify(proposed()));
    expect(parsed).toEqual(proposed());
  });

  it("refuses text that is not an annotation, with a plain sentence", () => {
    expect(() => parseAnnotation("{")).toThrow(AnnotationError);
    expect(() => parseAnnotation("{")).toThrow(/not JSON/);
    expect(() => parseAnnotation(JSON.stringify({ ...proposed(), schema_version: 2 }))).toThrow(/version/);
    expect(() => parseAnnotation(JSON.stringify({ ...proposed(), sha256: "abc" }))).toThrow(/sha256/);
    expect(() => parseAnnotation(JSON.stringify({ ...proposed(), canvas: [800] }))).toThrow(/canvas/);
    expect(() => parseAnnotation(JSON.stringify({ ...proposed(), frame: {} }))).toThrow(/frame/);
  });

  it("refuses what the annotation model refuses, before it reaches a saved file", () => {
    // Self-review findings on #149: a string band width concatenated in
    // bandTotal; a count of 1e300 made the overlay loop without end; a
    // __proto__ key or an unknown code was carried into the saved file.
    const frame = proposed().frame!;
    const stringBand = [{ ...frame[0], value: { outer_edge: { ...frame[0].value.outer_edge, bands: [{ width_squares: "2" }] } } }];
    expect(() => parseAnnotation(JSON.stringify({ ...proposed(), frame: stringBand }))).toThrow(/frame claim/);
    const huge = [{ value: { ...COUNTS, blocks_across: 1e300 }, provenance: "proposed-a" }];
    expect(() => parseAnnotation(JSON.stringify({ ...proposed(), counts: huge }))).toThrow(/counts claim/);
    expect(() => parseAnnotation('{"schema_version":1,"photo":"a.jpg","sha256":"' + SHA + '","canvas":[1,1],"__proto__":[]}')).toThrow(
      /does not define: __proto__/,
    );
    const unknownCode = [{ value: "hst", provenance: "proposed-c" }];
    expect(() => parseAnnotation(JSON.stringify({ ...proposed(), construction_class: unknownCode }))).toThrow(/list of claims/);
    const twice = [...proposed().counts!, ...proposed().counts!];
    expect(() => parseAnnotation(JSON.stringify({ ...proposed(), counts: twice }))).toThrow(/one provenance code/);
    const badClass = [{ value: "diamond", provenance: "proposed-a" }];
    expect(() => parseAnnotation(JSON.stringify({ ...proposed(), construction_class: badClass }))).toThrow(/class claim/);
  });

  it("matches a photo file to its annotation by stem, ignoring case and folders", () => {
    expect(sameStem("images/lacma-54871.jpg", "lacma-54871.JPG")).toBe(true);
    expect(sameStem("private/cache/met-13596.jpg", "met-13597.jpg")).toBe(false);
  });

  it("knows a no-border frame saved from field corners", () => {
    expect(isNoBorderFrame(annotatedFrame("field", FIELD, [], null))).toBe(true);
    expect(isNoBorderFrame(annotatedFrame("outer_edge", OUTER, [], FIELD))).toBe(false);
    expect(isNoBorderFrame(annotatedFrame("outer_edge", OUTER, [], null))).toBe(false);
  });

  it("starts from the verified claim, else proposer A, else proposer B", () => {
    const start = startingValues(proposed());
    expect(start.provenance).toBe("proposed-a");
    expect(start.frame?.outer_edge.corners).toEqual(OUTER);
    expect(start.counts).toEqual(COUNTS);
    // No proposed-a class: the class falls back to proposed-b's.
    expect(start.constructionClass).toBe("hst");
    // A chosen provenance wins.
    expect(startingValues(proposed(), "proposed-b").frame?.outer_edge.corners).toEqual(FIELD);
  });

  it("starts from the first claim when no claim has a default code, so Start from can pick it", () => {
    // Source: PR #247 review of 0b7e9a3 (AnnotatePage.tsx:504): with only
    // other codes the page started from nothing, and the Start from list
    // showed its first code as chosen while it was not.
    const other: Annotation = {
      ...proposed(),
      frame: [
        { value: { outer_edge: { kind: "outer_edge", corners: FIELD, bands: [] }, field: null }, provenance: "adjudicated" },
        { value: { outer_edge: { kind: "outer_edge", corners: OUTER, bands: [] }, field: null }, provenance: "screened" },
      ],
      counts: [{ value: COUNTS, provenance: "adjudicated" }],
    };
    expect(frameProvenances(other)).toEqual(["adjudicated", "screened"]);
    const start = startingValues(other);
    expect(start.provenance).toBe("adjudicated");
    expect(start.frame?.outer_edge.corners).toEqual(FIELD);
    expect(start.counts).toEqual(COUNTS);
    expect(startingValues(other, "screened").frame?.outer_edge.corners).toEqual(OUTER);
  });

  it("refuses a full-size photo whose sha256 is not the annotation's", () => {
    // Source: PR #247 review of 0b7e9a3 (AnnotatePage.tsx:173). The
    // annotation's sha256 is the source image's (corpus/README.md,
    // Annotations), so only a photo of the canvas's size can be compared; a
    // downsized copy has its own bytes and passes on its shape alone.
    const annotation = proposed();
    const other = "0".repeat(64);
    expect(photoProblem(annotation, { width: 800, height: 600 }, SHA)).toBeNull();
    expect(photoProblem(annotation, { width: 800, height: 600 }, other)).toBe(
      `This photo's sha256 is ${other}, but the annotation names ${SHA}: it is another photo.`,
    );
    // Half size, 400 x 300: a downsized copy, not compared.
    expect(photoProblem(annotation, { width: 400, height: 300 }, other)).toBeNull();
    // Larger, 1000 x 750 (the same shape): neither the photo nor a downsized
    // copy of it, so it is refused whatever its hash.
    expect(photoProblem(annotation, { width: 1000, height: 750 }, SHA)).toBe(
      "This photo is 1000 x 750 px, larger than the annotation's canvas of 800 x 600 px: it is another photo.",
    );
  });

  it("names its photo file by the manifest path's stem", () => {
    expect(photoStem("private/cache/met-13596.jpg")).toBe("met-13596");
    expect(photoStem("images/lacma-54871.jpg")).toBe("lacma-54871");
    expect(photoStem("quilt photo.JPEG")).toBe("quilt photo");
  });

  it("matches a downsized copy to its canvas by shape, within 1 percent", () => {
    // Same rule as scripts/eval/qrep_eval/annotation.py to_read_request.
    // Arithmetic: 2000 / 1500 = 1.3333 and 800 / 600 = 1.3333, equal;
    //             600 / 800 = 0.75, which is 44 percent off 1.3333;
    //             1005 / 750 = 1.34, (1.34 - 1.3333) / 1.3333 = 0.5 percent, inside;
    //             1020 / 750 = 1.36, (1.36 - 1.3333) / 1.3333 = 2 percent, outside
    expect(aspectMatches([2000, 1500], { width: 800, height: 600 })).toBe(true);
    expect(aspectMatches([2000, 1500], { width: 600, height: 800 })).toBe(false);
    expect(aspectMatches([2000, 1500], { width: 1005, height: 750 })).toBe(true);
    expect(aspectMatches([2000, 1500], { width: 1020, height: 750 })).toBe(false);
  });
});

describe("the saved frame", () => {
  it("records the outer edge with its bands, and the field when pinned", () => {
    expect(annotatedFrame("outer_edge", OUTER, [{ width_squares: 1 }], FIELD)).toEqual({
      outer_edge: { kind: "outer_edge", corners: OUTER, bands: [{ width_squares: 1 }] },
      field: { kind: "field", corners: FIELD },
    });
    expect(annotatedFrame("outer_edge", OUTER, [], null)).toEqual({
      outer_edge: { kind: "outer_edge", corners: OUTER, bands: [] },
      field: null,
    });
  });

  it("records field corners with no border as an outer edge equal to the field", () => {
    // corpus/README.md: no border means no bands, and the field lies on the
    // outer edge when there is no border.
    expect(annotatedFrame("field", FIELD, [{ width_squares: 2 }], null)).toEqual({
      outer_edge: { kind: "outer_edge", corners: FIELD, bands: [] },
      field: { kind: "field", corners: FIELD },
    });
  });
});

describe("saving", () => {
  const verified = {
    frame: annotatedFrame("outer_edge", OUTER, [{ width_squares: 1 }], FIELD),
    counts: COUNTS,
    constructionClass: "squares" as const,
  };

  it("adds verified-jake claims and keeps every proposal unchanged", () => {
    const before = proposed();
    const after = withVerified(before, verified);
    expect(before).toEqual(proposed());
    expect(after.frame?.slice(0, 2)).toEqual(proposed().frame);
    expect(after.frame?.[2]).toEqual({ value: verified.frame, provenance: "verified-jake" });
    expect(after.counts).toEqual([...proposed().counts!, { value: COUNTS, provenance: "verified-jake" }]);
    expect(after.construction_class).toEqual([
      ...proposed().construction_class!,
      { value: "squares", provenance: "verified-jake" },
    ]);
    expect(after.finished_size).toEqual(proposed().finished_size);
  });

  it("replaces an earlier verified-jake claim, since a field holds one claim per provenance", () => {
    const once = withVerified(proposed(), verified);
    const twice = withVerified(once, { ...verified, constructionClass: "hst" });
    expect(twice.construction_class?.filter((c) => c.provenance === "verified-jake")).toEqual([
      { value: "hst", provenance: "verified-jake" },
    ]);
    expect(twice.frame).toHaveLength(3);
  });

  it("starts a new file from the photo's identity", () => {
    expect(newAnnotation("quilt.jpg", SHA, [4032, 3024])).toEqual({
      schema_version: 1,
      photo: "quilt.jpg",
      sha256: SHA,
      canvas: [4032, 3024],
    });
  });

  it("writes two-space JSON ending in a newline", () => {
    const text = serializeAnnotation(newAnnotation("quilt.jpg", SHA, [10, 20]));
    expect(text.endsWith("}\n")).toBe(true);
    expect(text).toContain('\n  "photo": "quilt.jpg"');
  });

  it("refuses to save what the annotation model would refuse to load", () => {
    const canvas: [number, number] = [800, 600];
    expect(saveProblems(verified, canvas)).toEqual([]);
    const swapped = { ...OUTER, top_left: OUTER.top_right, top_right: OUTER.top_left };
    expect(saveProblems({ ...verified, frame: annotatedFrame("outer_edge", swapped, [], null) }, canvas)).toEqual([
      "The outer edge corners are out of order: pin the top left, top right, bottom right and bottom left corners.",
    ]);
    const offCanvas = { ...OUTER, bottom_right: { x: 900, y: 450 } };
    expect(
      saveProblems({ ...verified, frame: annotatedFrame("outer_edge", offCanvas, [], null) }, canvas)[0],
    ).toMatch(/off the photo/);
    expect(saveProblems({ ...verified, constructionClass: null }, canvas)).toEqual([
      "Choose a construction class before you save.",
    ]);
  });
});
