/**
 * S8 verdict story (sprint 3, issue #74): every verdict variant pinned
 * from fixed PhotoResult fixtures, red-first. The Results and Progress
 * components render this structure 1:1 (UI-SPEC sections 3-5).
 */
import { describe, expect, it } from "vitest";
import { PALETTE_TRUST_MIN, paletteGate, verdictStory } from "./verdictStory";

const BASE = {
  modelJson: "{}",
  stageConfidence: { straighten: 0.9, colors: 0.9, grid: 0.9, squares: 0.9, repeats: 0.9, borders: 0.9 },
  uncertainCount: 0,
  reverseMs: 100,
};

function result(over: Record<string, unknown>) {
  return { ...BASE, ...over } as never;
}

describe("verdictStory", () => {
  it("no_grid: failure pill with NO percentage, panel + disclosure + banner", () => {
    const story = verdictStory(
      result({ verdict: "no_grid", diagnostics: { grid_diagnosis: "anisotropic_pitch", size_source: "guess" } }),
      { cols: 43, rows: 13, cellSize: 12 },
    );
    expect(story.pill.mode).toBe("failure");
    expect(story.pill.text).toBe("Could not read this photo");
    expect(story.pill.text).not.toMatch(/%|\d/);
    expect(story.failurePanel).not.toBeNull();
    expect(story.failurePanel!.title).toBe("We could not find a square grid in this photo");
    expect(story.disclosure).toEqual({
      label: "Show what we saw anyway",
      banner: "This reading is wrong - shown only to help you see what went wrong.",
    });
    // rectify succeeded, grid failed: dashes from the grid row onward
    expect(story.dashedStages).toEqual(["grid", "squares", "repeats", "borders"]);
  });

  it("no_grid from a rectify failure dashes every row", () => {
    const story = verdictStory(
      result({ verdict: "no_grid", diagnostics: { grid_diagnosis: "no_quilt_found" } }),
      { cols: 2, rows: 2, cellSize: 12 },
    );
    expect(story.dashedStages).toEqual([
      "straighten", "colors", "grid", "squares", "repeats", "borders",
    ]);
  });

  it("non_square_repeat: softened copy, unsized period phrasing, disclosure", () => {
    // 24 cols with a 4-cell block period: repeats about 6 times across
    const story = verdictStory(
      result({
        verdict: "non_square_repeat",
        diagnostics: { block_period_cells: [4, 4], size_source: "guess" },
      }),
      { cols: 24, rows: 28, cellSize: 12 },
    );
    expect(story.pill.mode).toBe("nonsquare");
    expect(story.pill.text).toContain("blocks repeat");
    expect(story.infoPanel!.title).toContain("blocks repeat");
    expect(story.infoPanel!.title).toContain("may use shapes");
    expect(story.infoPanel!.period).toBe("It repeats about 6 times across its width.");
    expect(story.infoPanel!.sizeInvite).toBe(true);
    expect(story.disclosure!.label).toBe("Show the squares approximation");
  });

  it("non_square_repeat sized: period in inches from cells x cell size", () => {
    // user-sized, block 4 cells x cell 18 eighths = 72 eighths = 9 in
    const story = verdictStory(
      result({
        verdict: "non_square_repeat",
        diagnostics: { block_period_cells: [4, 4], size_source: "user" },
      }),
      { cols: 24, rows: 28, cellSize: 18 },
    );
    expect(story.infoPanel!.period).toBe("It repeats every 9 in.");
    expect(story.infoPanel!.sizeInvite).toBe(false);
  });

  it("readable_no_repeat: NORMAL result with the sampler caption", () => {
    const story = verdictStory(
      result({ verdict: "readable_no_repeat", diagnostics: { size_source: "guess" } }),
      { cols: 20, rows: 20, cellSize: 12 },
    );
    expect(story.pill.mode).toBe("percent");
    expect(story.failurePanel).toBeNull();
    expect(story.caption).toBe(
      "No repeating block found - common for samplers and medallion quilts.",
    );
    expect(story.dashedStages).toEqual([]);
  });

  it("readable with a confirmed repeat: positive caption", () => {
    // unsized: 45 cols / 10-cell period = repeats 4 times (floor 4.5 -> about 4)
    const story = verdictStory(
      result({
        verdict: "readable",
        diagnostics: { repeat_period: [10, 10], block_period_cells: [10, 10], size_source: "guess" },
      }),
      { cols: 45, rows: 55, cellSize: 12 },
    );
    expect(story.caption).toBe("It repeats about 4 times across its width.");
    // sized: 10 cells x 12 eighths = 120 eighths = 15 in
    const sized = verdictStory(
      result({
        verdict: "readable",
        diagnostics: { repeat_period: [10, 10], block_period_cells: [10, 10], size_source: "user" },
      }),
      { cols: 45, rows: 55, cellSize: 12 },
    );
    expect(sized.caption).toBe("It repeats every 15 in.");
  });

  it("missing verdict (pre-S4 result) behaves as readable", () => {
    const story = verdictStory(result({}), { cols: 10, rows: 10, cellSize: 12 });
    expect(story.pill.mode).toBe("percent");
    expect(story.failurePanel).toBeNull();
  });
});

describe("paletteGate (frozen: confidence >= 0.80 and 2 <= k <= 6)", () => {
  it("passes a confident small palette", () => {
    expect(paletteGate(0.9, 2)).toBe(true);
    expect(paletteGate(PALETTE_TRUST_MIN, 6)).toBe(true);
  });
  it("rejects junk: low confidence or phantom-heavy k", () => {
    expect(paletteGate(0.64, 2)).toBe(false); // the lighting-gradient class
    expect(paletteGate(0.89, 8)).toBe(false); // the solid-fabric class
    expect(paletteGate(0.9, 1)).toBe(false);
  });
});
