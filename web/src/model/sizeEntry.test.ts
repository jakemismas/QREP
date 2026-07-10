/**
 * S7 size-entry state machine (sprint 3, issue #73).
 *
 * PINNED RULE (frozen by the approval record): cm converts at entry via
 * eighths = round(cm * 8 / 2.54); the model stays integer eighths
 * everywhere. Every expectation below is hand-computed in its comment.
 */
import { describe, expect, it } from "vitest";
import { SizeEntryState, cmToEighths, formatCmEquivalent } from "./sizeEntry";

describe("cmToEighths (the pinned conversion)", () => {
  it("converts by round(cm * 8 / 2.54), hand cases", () => {
    // 2.54 cm = 1 in = 8 eighths exactly
    expect(cmToEighths(2.54)).toBe(8);
    // 100 cm: 100 * 8 / 2.54 = 314.96... -> 315
    expect(cmToEighths(100)).toBe(315);
    // 67.5 cm: 67.5 * 8 / 2.54 = 212.598... -> 213
    expect(cmToEighths(67.5)).toBe(213);
    // 30 cm: 30 * 8 / 2.54 = 94.488... -> 94
    expect(cmToEighths(30)).toBe(94);
  });
});

describe("SizeEntryState", () => {
  it("starts empty with source none and no options", () => {
    const s = new SizeEntryState();
    expect(s.source).toBe("none");
    expect(s.sizeOptions()).toBeNull();
  });

  it("inch entry accepts decimal and mixed, stores eighths, source user", () => {
    const s = new SizeEntryState();
    // 86 in = 688 eighths; 67.5 in = 540 eighths (hand)
    expect(s.editInput("width", "86")).toBe(true);
    expect(s.editInput("height", "67 1/2")).toBe(true);
    expect(s.widthEighths).toBe(688);
    expect(s.heightEighths).toBe(540);
    expect(s.source).toBe("user");
    expect(s.sizeOptions()).toEqual({ finished_width: 688, finished_height: 540 });
  });

  it("decimal entry equals mixed entry (67.5 == 67 1/2)", () => {
    const a = new SizeEntryState();
    const b = new SizeEntryState();
    a.editInput("height", "67.5");
    b.editInput("height", "67 1/2");
    expect(a.heightEighths).toBe(b.heightEighths);
  });

  it("cm entry converts via the pinned rule at entry time", () => {
    const s = new SizeEntryState();
    s.toggleUnit(); // in -> cm
    expect(s.unit).toBe("cm");
    expect(s.editInput("width", "100")).toBe(true);
    expect(s.widthEighths).toBe(315); // hand: round(100 * 8 / 2.54)
    expect(s.enteredInCm).toBe(true);
  });

  it("invalid entry is rejected and state unchanged", () => {
    const s = new SizeEntryState();
    expect(s.editInput("width", "abc")).toBe(false);
    expect(s.widthEighths).toBeNull();
    expect(s.source).toBe("none");
  });

  it("chip tap sets both dims from PRESETS and is a user gesture", () => {
    const s = new SizeEntryState();
    s.tapChip("Queen"); // Queen 90 x 108 in = 720 x 864 eighths (hand)
    expect(s.widthEighths).toBe(720);
    expect(s.heightEighths).toBe(864);
    expect(s.source).toBe("user");
  });

  it("suggestion prefills ONLY empty inputs and ships as guess untouched", () => {
    const s = new SizeEntryState();
    s.suggest("Queen");
    expect(s.suggestedPreset).toBe("Queen");
    // prefilled for display (720 x 864) but NOT user provenance
    expect(s.widthEighths).toBe(720);
    expect(s.source).toBe("suggested");
    // an untouched suggestion sends nothing to the engine
    expect(s.sizeOptions()).toBeNull();
  });

  it("suggestion never overwrites a user-entered value", () => {
    const s = new SizeEntryState();
    s.editInput("width", "40");
    s.suggest("Queen");
    expect(s.widthEighths).toBe(320); // the user's 40 in stands
    expect(s.suggestedPreset).toBe("Queen"); // chip may still highlight
    expect(s.source).toBe("user");
  });

  it("touching a suggested value promotes provenance to user", () => {
    const s = new SizeEntryState();
    s.suggest("Queen");
    s.editInput("width", "90"); // confirms/edits the suggested width
    expect(s.source).toBe("user");
    expect(s.sizeOptions()).toEqual({ finished_width: 720, finished_height: 864 });
  });

  it("width-only user entry sends width only", () => {
    const s = new SizeEntryState();
    s.editInput("width", "30");
    expect(s.sizeOptions()).toEqual({ finished_width: 240, finished_height: null });
  });

  it("reset clears everything", () => {
    const s = new SizeEntryState();
    s.tapChip("Crib");
    s.reset();
    expect(s.widthEighths).toBeNull();
    expect(s.source).toBe("none");
    expect(s.sizeOptions()).toBeNull();
  });
});

describe("formatCmEquivalent", () => {
  it("shows one-decimal cm from eighths, hand cases", () => {
    // 688 eighths = 86 in = 218.44 cm -> "218.4"
    expect(formatCmEquivalent(688)).toBe("218.4");
    // 8 eighths = 1 in = 2.54 cm -> "2.5"
    expect(formatCmEquivalent(8)).toBe("2.5");
  });
});
