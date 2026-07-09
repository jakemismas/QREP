"""Photoreal fixture generator (sprint 3 S0, issue #66).

Deterministic, seeded scene composer for the photo-reality evidence base.
Fixtures are GENERATED ONCE and COMMITTED as PNGs; tests regenerate the
pixel arrays in memory and compare against the decoded committed files.

Determinism rules (why this module looks the way it does):
- numpy + PIL PNG I/O only. No cv2: the native venv runs cv2 5.x while the
  wasm wheel is 4.11, and their resampling kernels are not byte-promised.
- No trigonometry: libm sin/cos differ in the last ulp across platforms.
  Directions use exact 3-4-5 vectors (0.8, 0.6); textures use triangle
  waves (pure arithmetic).
- The perspective warp solves its homography with local Gaussian
  elimination and applies it with explicit elementwise expressions, so no
  BLAS reduction order can flip a pixel.
- Every random draw comes from a per-fixture-per-cap seeded Generator.
- The ONE exception, per the plan's determinism spec: the JPEG stage of
  render_perspective_jpeg goes through PIL's libjpeg, whose bytes are not
  stable across builds. Its committed PNG is canonical; regeneration
  asserts the numpy-generated pre-JPEG stage plus bounded JPEG error, not
  byte equality.

Run `python tests/fixtures/photoreal/generator.py write` to (re)generate
the committed PNGs and ground-truth sidecars in place; git diff is the
review surface. Committed files are frozen after the S0 landing.
"""

import io
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
FIXTURE_MODEL_PATH = ROOT.parent / "double_irish_chain.json"

CAPS = (1400, 2000)  # staged resolution caps: phone / desktop longest side
SEED = 42
JPEG_QUALITY = 82
RENDER_BACKGROUND = (0x40, 0x40, 0x40)  # the sprint 1 renderer margin color

# content palettes (hex without '#', as RGB tuples)
STAR_NAVY = (43, 58, 103)
STAR_CENTER = (146, 110, 174)  # contrasting center so the block reads as a star
STAR_CREAM = (242, 234, 216)
LOWC_A = (182, 176, 162)  # low-contrast HST pair: close L, same hue family
LOWC_B = (194, 188, 174)
DP_TEAL = (63, 127, 122)
DP_IVORY = (239, 231, 214)
BUSY_RED = (143, 59, 59)
BUSY_NAVY = (40, 52, 94)
CHECKER_RED = (166, 61, 64)
CHECKER_WHITE = (244, 241, 234)
SOLID_GREEN = (122, 139, 111)
CHROME_DARK = (30, 33, 36)
PAGE_WHITE = (250, 250, 250)


def _rng(name: str, cap: int) -> np.random.Generator:
    return np.random.default_rng([SEED, cap, *name.encode()])


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    """'#rrggbb' to an RGB tuple."""
    return tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _load_irish_chain():
    """Cells as an int label grid plus palette, straight from the committed
    sprint 1 fixture (the ground truth model the metrics compare against)."""
    from qrep.model import load

    quilt = load(FIXTURE_MODEL_PATH)
    fabric_ids = [f.id for f in quilt.palette.fabrics]
    colors = [_hex_to_rgb(f.color) for f in quilt.palette.fabrics]
    labels = np.array(
        [[fabric_ids.index(fid) for fid in row] for row in quilt.center.cells], dtype=np.int64
    )
    border_pitches = quilt.borders[0].width / quilt.center.cell_size  # 30/12 = 2.5
    border_label = fabric_ids.index(quilt.borders[0].fabric_id)
    return labels, colors, border_pitches, border_label, [f.color for f in quilt.palette.fabrics]


# ---------------------------------------------------------------------------
# deterministic drawing primitives
# ---------------------------------------------------------------------------


def _ramp(h: int, w: int, low: float, high: float) -> np.ndarray:
    """Linear brightness ramp along the exact (0.8, 0.6) direction."""
    ys = np.arange(h, dtype=np.float64)[:, None] / max(h - 1, 1)
    xs = np.arange(w, dtype=np.float64)[None, :] / max(w - 1, 1)
    t = 0.8 * xs + 0.6 * ys
    t = t / t.max()
    return low + (high - low) * t


def _tri(values: np.ndarray) -> np.ndarray:
    """Triangle wave in [0, 1] with period 1 (pure arithmetic, no trig)."""
    frac = values - np.floor(values)
    return 1.0 - np.abs(2.0 * frac - 1.0)


def _apply_factor(image: np.ndarray, factor: np.ndarray) -> np.ndarray:
    out = image.astype(np.float64) * factor[:, :, None]
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)


def _flat(h: int, w: int, color: tuple[int, int, int]) -> np.ndarray:
    return np.tile(np.array(color, dtype=np.uint8), (h, w, 1))


def _wood(h: int, w: int, rng: np.random.Generator) -> np.ndarray:
    """Horizontal oak planks: per-plank base tone, triangle-wave grain
    streaks, and dark seam lines between boards."""
    base = np.array([154, 107, 63], dtype=np.float64)
    image = np.zeros((h, w, 3), dtype=np.float64)
    plank_h = max(24, h // 9)
    y = 0
    while y < h:
        tone = base + rng.uniform(-18, 18, size=3)
        ph = int(plank_h * rng.uniform(0.85, 1.15))
        ys = np.arange(y, min(h, y + ph))
        # grain: two triangle waves at different vertical frequencies whose
        # phase drifts along x, imitating cathedral grain without trig
        xs = np.arange(w, dtype=np.float64)
        phase = rng.uniform(0, 1)
        freq = rng.uniform(0.006, 0.012)
        drift = rng.uniform(0.05, 0.12)
        rows = (ys - y).astype(np.float64)[:, None]
        wave = _tri(xs[None, :] * freq + rows * drift + phase)
        wave2 = _tri(xs[None, :] * freq * 3.7 + rows * drift * 0.4 + phase * 2.0)
        streak = 1.0 - 0.10 * wave - 0.05 * wave2
        image[ys, :, :] = tone[None, None, :] * streak[:, :, None]
        if y + ph < h:
            image[min(h - 1, y + ph - 1), :, :] *= 0.55  # board seam
        y += ph
    return np.clip(np.rint(image), 0, 255).astype(np.uint8)


def _cell_indexed(
    field_h: int,
    field_w: int,
    labels: np.ndarray,
    per_cell_rgb: np.ndarray,
) -> np.ndarray:
    """Rasterize a label grid into a field image via per-cell colors."""
    rows, cols = labels.shape
    row_of = np.minimum((np.arange(field_h) * rows) // field_h, rows - 1)
    col_of = np.minimum((np.arange(field_w) * cols) // field_w, cols - 1)
    return per_cell_rgb[row_of[:, None], col_of[None, :]]


def _tinted_cell_colors(
    labels: np.ndarray, colors: list[tuple[int, int, int]], rng: np.random.Generator, amp: int
) -> np.ndarray:
    """Per-cell tinted color lookup (the L1-style per-patch variance)."""
    base = np.array(colors, dtype=np.int64)[labels]
    tint = rng.integers(-amp, amp + 1, size=base.shape)
    return np.clip(base + tint, 0, 255).astype(np.uint8)


def _irish_chain_content(
    box_h: int, box_w: int, rng: np.random.Generator, tint_amp: int = 6
) -> tuple[np.ndarray, dict]:
    """The Double Irish Chain quilt (border included) rasterized to a box.

    Pitch spans: 45 + 2*2.5 = 50 across, 55 + 2*2.5 = 60 down.
    """
    labels, colors, border_pitches, border_label, palette_hex = _load_irish_chain()
    rows, cols = labels.shape  # 55, 45
    span_x, span_y = cols + 2 * border_pitches, rows + 2 * border_pitches
    pitch_x, pitch_y = box_w / span_x, box_h / span_y
    u = (np.arange(box_w, dtype=np.float64) + 0.5) / pitch_x
    v = (np.arange(box_h, dtype=np.float64) + 0.5) / pitch_y
    col = np.clip(np.floor(u - border_pitches), 0, cols - 1).astype(np.int64)
    row = np.clip(np.floor(v - border_pitches), 0, rows - 1).astype(np.int64)
    in_x = (u >= border_pitches) & (u < span_x - border_pitches)
    in_y = (v >= border_pitches) & (v < span_y - border_pitches)
    per_cell = _tinted_cell_colors(labels, colors, rng, tint_amp)
    image = per_cell[row[:, None], col[None, :]]
    border_mask = ~(in_y[:, None] & in_x[None, :])
    image = image.copy()
    image[border_mask] = np.array(colors[border_label], dtype=np.uint8)
    truth = {
        "cells_ref": "double_irish_chain",
        "grid": {"rows": rows, "cols": cols, "border_pitches": border_pitches},
        "palette_hex": palette_hex,
        "repeat_cells": [10, 10],
        "character": "squares",
    }
    return image, truth


def _star_type_map(block_rows: int, block_cols: int) -> np.ndarray:
    """Variable-star block, 4x4 cells, tiled. Cell type codes:
    0 solid background, 1 solid center,
    2 HST main diagonal (star below), 3 HST anti-diagonal (star below),
    4 HST main diagonal (star above), 5 HST anti-diagonal (star above).

    Each side pair's point triangles have their legs against the center and
    meet at the shared outer-edge corner, so the points aim outward; the
    center square uses a third contrasting fabric so the block reads as a
    star rather than one merged diamond.
    """
    block = np.array(
        [
            [0, 3, 2, 0],
            [3, 1, 1, 2],
            [4, 1, 1, 5],
            [0, 4, 5, 0],
        ],
        dtype=np.int64,
    )
    return np.tile(block, (block_rows, block_cols))


def _hst_field(
    field_h: int,
    field_w: int,
    type_map: np.ndarray,
    color_a: tuple[int, int, int],
    color_b: tuple[int, int, int],
    rng: np.random.Generator,
    tint_amp: int = 5,
    color_center: tuple[int, int, int] | None = None,
) -> np.ndarray:
    """Rasterize an HST type map: per-pixel triangle membership by the cell's
    fractional coordinates. color_a = point fabric, color_b = background,
    color_center = the solid type-1 cells (defaults to color_a)."""
    rows, cols = type_map.shape
    y = np.arange(field_h, dtype=np.float64)
    x = np.arange(field_w, dtype=np.float64)
    ry = y * rows / field_h
    cx = x * cols / field_w
    row = np.minimum(ry.astype(np.int64), rows - 1)
    col = np.minimum(cx.astype(np.int64), cols - 1)
    fy = (ry - row)[:, None]
    fx = (cx - col)[None, :]
    types = type_map[row[:, None], col[None, :]]

    main_lower = fy >= fx  # below the main diagonal
    anti_lower = fy >= (1.0 - fx)  # below the anti-diagonal
    star = np.zeros((field_h, field_w), dtype=bool)
    star |= (types == 2) & main_lower
    star |= (types == 3) & anti_lower
    star |= (types == 4) & ~main_lower
    star |= (types == 5) & ~anti_lower
    center = types == 1

    tint_a = _tinted_cell_colors(np.zeros_like(type_map), [color_a], rng, tint_amp)
    tint_b = _tinted_cell_colors(np.zeros_like(type_map), [color_b], rng, tint_amp)
    tint_c = _tinted_cell_colors(
        np.zeros_like(type_map), [color_center or color_a], rng, tint_amp
    )
    img_a = tint_a[row[:, None], col[None, :]]
    img_b = tint_b[row[:, None], col[None, :]]
    img_c = tint_c[row[:, None], col[None, :]]
    out = np.where(star[:, :, None], img_a, img_b)
    return np.where(center[:, :, None], img_c, out)


def _drunkards_field(
    field_h: int,
    field_w: int,
    rows: int,
    cols: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Quarter-circle Drunkard's Path: one quarter disc per cell, the disc
    corner rotating around a 2x2 arrangement so discs join into circles."""
    y = np.arange(field_h, dtype=np.float64)
    x = np.arange(field_w, dtype=np.float64)
    ry = y * rows / field_h
    cx = x * cols / field_w
    row = np.minimum(ry.astype(np.int64), rows - 1)
    col = np.minimum(cx.astype(np.int64), cols - 1)
    fy = (ry - row)[:, None] + np.zeros((1, field_w))
    fx = (cx - col)[None, :] + np.zeros((field_h, 1))
    rr = row[:, None] + np.zeros((1, field_w), dtype=np.int64)
    cc = col[None, :] + np.zeros((field_h, 1), dtype=np.int64)
    # disc corner (cy, cx) per cell parity: circles form around odd corners
    corner_y = np.where((rr % 2) == 0, 1.0, 0.0)
    corner_x = np.where((cc % 2) == 0, 1.0, 0.0)
    inside = (fx - corner_x) ** 2 + (fy - corner_y) ** 2 <= 1.0
    tint_a = _tinted_cell_colors(np.zeros((rows, cols), dtype=np.int64), [DP_TEAL], rng, 4)
    tint_b = _tinted_cell_colors(np.zeros((rows, cols), dtype=np.int64), [DP_IVORY], rng, 4)
    img_a = tint_a[rr, cc]
    img_b = tint_b[rr, cc]
    return np.where(inside[:, :, None], img_a, img_b)


def _busy_print_field(
    field_h: int,
    field_w: int,
    labels: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Squares whose fabrics are busy prints: dots on red, stripes on navy.

    High intra-cell edge energy with genuinely square piecing - the
    stay-readable confusion direction of the S4 coherence classifier.
    """
    rows, cols = labels.shape
    per_cell = _tinted_cell_colors(labels, [BUSY_RED, BUSY_NAVY], rng, 5)
    image = _cell_indexed(field_h, field_w, labels, per_cell).astype(np.int64)
    label_img = _cell_indexed(field_h, field_w, labels, labels[..., None])[:, :, 0]
    y = np.arange(field_h, dtype=np.float64)[:, None]
    x = np.arange(field_w, dtype=np.float64)[None, :]
    pitch = field_w / cols
    # fabric 0: light polka dots on a grid at ~1/4 pitch spacing
    d = max(6.0, pitch / 4.0)
    dot = ((x % d) - d / 2) ** 2 + ((y % d) - d / 2) ** 2 <= (d * 0.22) ** 2
    image = np.where((dot & (label_img == 0))[:, :, None], image + 52, image)
    # fabric 1: thin diagonal stripes, triangle-wave thresholded
    stripe = _tri((x + y) / (d * 0.9)) > 0.72
    image = np.where((stripe & (label_img == 1))[:, :, None], image + 44, image)
    return np.clip(image, 0, 255).astype(np.uint8)


def _checker_with_border(
    box_h: int,
    box_w: int,
    rows: int,
    cols: int,
    border_pitches: float,
    rng: np.random.Generator,
) -> tuple[np.ndarray, dict]:
    """Two-fabric checkerboard with a WHITE border band (the
    white-bordered-quilt case; the border must belong to the quilt)."""
    labels = (np.add.outer(np.arange(rows), np.arange(cols)) % 2).astype(np.int64)
    span_x, span_y = cols + 2 * border_pitches, rows + 2 * border_pitches
    pitch_x, pitch_y = box_w / span_x, box_h / span_y
    u = (np.arange(box_w, dtype=np.float64) + 0.5) / pitch_x
    v = (np.arange(box_h, dtype=np.float64) + 0.5) / pitch_y
    col = np.clip(np.floor(u - border_pitches), 0, cols - 1).astype(np.int64)
    row = np.clip(np.floor(v - border_pitches), 0, rows - 1).astype(np.int64)
    in_x = (u >= border_pitches) & (u < span_x - border_pitches)
    in_y = (v >= border_pitches) & (v < span_y - border_pitches)
    per_cell = _tinted_cell_colors(labels, [CHECKER_RED, CHECKER_WHITE], rng, 5)
    image = per_cell[row[:, None], col[None, :]].copy()
    image[~(in_y[:, None] & in_x[None, :])] = np.array(CHECKER_WHITE, dtype=np.uint8)
    truth = {
        "grid": {"rows": rows, "cols": cols, "border_pitches": border_pitches},
        "palette_hex": [_rgb_to_hex(CHECKER_RED), _rgb_to_hex(CHECKER_WHITE)],
        "repeat_cells": [2, 2],
        "character": "squares",
        "cells": labels.tolist(),
    }
    return image, truth


# ---------------------------------------------------------------------------
# perspective warp (pure numpy, local Gaussian elimination)
# ---------------------------------------------------------------------------


def _solve8(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Gaussian elimination with partial pivoting; no BLAS, deterministic."""
    n = a.shape[0]
    m = np.concatenate([a.astype(np.float64), b.reshape(-1, 1).astype(np.float64)], axis=1)
    for i in range(n):
        pivot = i + int(np.argmax(np.abs(m[i:, i])))
        if pivot != i:
            m[[i, pivot]] = m[[pivot, i]]
        m[i] = m[i] / m[i, i]
        for j in range(n):
            if j != i:
                m[j] = m[j] - m[j, i] * m[i]
    return m[:, n]


def _homography(src: list[tuple[float, float]], dst: list[tuple[float, float]]) -> np.ndarray:
    """3x3 H with H @ (sx, sy, 1) ~ (dx, dy, 1), h33 = 1."""
    rows, rhs = [], []
    for (sx, sy), (dx, dy) in zip(src, dst):
        rows.append([sx, sy, 1, 0, 0, 0, -dx * sx, -dx * sy])
        rhs.append(dx)
        rows.append([0, 0, 0, sx, sy, 1, -dy * sx, -dy * sy])
        rhs.append(dy)
    h = _solve8(np.array(rows), np.array(rhs))
    return np.array([[h[0], h[1], h[2]], [h[3], h[4], h[5]], [h[6], h[7], 1.0]])


def _warp_content_onto(
    canvas: np.ndarray, content: np.ndarray, dst_quad: list[tuple[float, float]]
) -> np.ndarray:
    """Place content (image array) onto the canvas so its corners land on
    dst_quad (TL TR BR BL), bilinear-sampled, explicit elementwise math."""
    ch, cw = content.shape[:2]
    src = [(0.0, 0.0), (cw - 1.0, 0.0), (cw - 1.0, ch - 1.0), (0.0, ch - 1.0)]
    hinv = _homography(dst_quad, src)  # canvas -> content coordinates
    xs_min = max(0, int(np.floor(min(p[0] for p in dst_quad))))
    xs_max = min(canvas.shape[1], int(np.ceil(max(p[0] for p in dst_quad))) + 1)
    ys_min = max(0, int(np.floor(min(p[1] for p in dst_quad))))
    ys_max = min(canvas.shape[0], int(np.ceil(max(p[1] for p in dst_quad))) + 1)
    xs = np.arange(xs_min, xs_max, dtype=np.float64)[None, :]
    ys = np.arange(ys_min, ys_max, dtype=np.float64)[:, None]
    denom = hinv[2, 0] * xs + hinv[2, 1] * ys + hinv[2, 2]
    sx = (hinv[0, 0] * xs + hinv[0, 1] * ys + hinv[0, 2]) / denom
    sy = (hinv[1, 0] * xs + hinv[1, 1] * ys + hinv[1, 2]) / denom
    inside = (sx >= 0) & (sx <= cw - 1) & (sy >= 0) & (sy <= ch - 1)
    sxc = np.clip(sx, 0, cw - 1)
    syc = np.clip(sy, 0, ch - 1)
    x0 = np.floor(sxc).astype(np.int64)
    y0 = np.floor(syc).astype(np.int64)
    x1 = np.minimum(x0 + 1, cw - 1)
    y1 = np.minimum(y0 + 1, ch - 1)
    fx = sxc - x0
    fy = syc - y0
    out = canvas.copy()
    # per-channel to keep the wasm peak-memory footprint down
    for ch in range(content.shape[2]):
        c = content[:, :, ch].astype(np.float64)
        sample = (
            c[y0, x0] * (1 - fx) * (1 - fy)
            + c[y0, x1] * fx * (1 - fy)
            + c[y1, x0] * (1 - fx) * fy
            + c[y1, x1] * fx * fy
        )
        patch = canvas[ys_min:ys_max, xs_min:xs_max, ch].astype(np.float64)
        blended = np.where(inside, sample, patch)
        out[ys_min:ys_max, xs_min:xs_max, ch] = np.clip(np.rint(blended), 0, 255).astype(
            np.uint8
        )
    return out


# ---------------------------------------------------------------------------
# scene assembly
# ---------------------------------------------------------------------------


def _fit_box(
    canvas_h: int, canvas_w: int, span_y: float, span_x: float, fraction: float
) -> tuple[int, int, int, int]:
    pitch = min(canvas_w * fraction / span_x, canvas_h * fraction / span_y)
    w, h = int(round(span_x * pitch)), int(round(span_y * pitch))
    return (canvas_h - h) // 2, (canvas_w - w) // 2, h, w


def _paste(canvas: np.ndarray, content: np.ndarray, y0: int, x0: int) -> np.ndarray:
    out = canvas.copy()
    out[y0 : y0 + content.shape[0], x0 : x0 + content.shape[1]] = content
    return out


def _rect_quad(y0: int, x0: int, h: int, w: int) -> list[list[float]]:
    return [
        [float(x0), float(y0)],
        [float(x0 + w), float(y0)],
        [float(x0 + w), float(y0 + h)],
        [float(x0), float(y0 + h)],
    ]


def _render_margin_scene(
    cap: int, span_y: float, span_x: float
) -> tuple[np.ndarray, int, int, int, int]:
    """Renderer-style scene: #404040 background, 8 percent margin, quilt
    filling the rest. Content fixtures use this so the CURRENT pipeline can
    rectify them and the baseline isolates the downstream stage."""
    if span_y >= span_x:
        canvas_h = cap
        quilt_h = int(round(cap / (1 + 2 * 0.08)))
        quilt_w = int(round(quilt_h * span_x / span_y))
        canvas_w = quilt_w + (canvas_h - quilt_h)
    else:
        canvas_w = cap
        quilt_w = int(round(cap / (1 + 2 * 0.08)))
        quilt_h = int(round(quilt_w * span_y / span_x))
        canvas_h = quilt_h + (canvas_w - quilt_w)
    canvas = _flat(canvas_h, canvas_w, RENDER_BACKGROUND)
    y0 = (canvas_h - quilt_h) // 2
    x0 = (canvas_w - quilt_w) // 2
    return canvas, y0, x0, quilt_h, quilt_w


def _base_sidecar(name: str, cap: int, canvas: np.ndarray, quad, background: str) -> dict:
    return {
        "name": name,
        "cap": cap,
        "seed": SEED,
        "canvas": [int(canvas.shape[1]), int(canvas.shape[0])],
        "quad": [[round(float(x), 3), round(float(y), 3)] for x, y in quad],
        "background": background,
    }


# --- fixture builders (name -> fn(cap) -> (uint8 RGB array, sidecar dict)) --


def fx_render_on_white(cap: int):
    rng = _rng("render_on_white", cap)
    h, w = int(round(cap * 0.75)), cap
    canvas = _apply_factor(_flat(h, w, (248, 246, 242)), _ramp(h, w, 0.985, 1.0))
    y0, x0, bh, bw = _fit_box(h, w, 60.0, 50.0, 0.82)
    content, truth = _irish_chain_content(bh, bw, rng)
    image = _paste(canvas, content, y0, x0)
    side = _base_sidecar("render_on_white", cap, image, _rect_quad(y0, x0, bh, bw), "white")
    side.update(truth)
    return image, side


def fx_render_on_wood(cap: int):
    rng = _rng("render_on_wood", cap)
    h, w = int(round(cap * 0.75)), cap
    canvas = _wood(h, w, rng)
    y0, x0, bh, bw = _fit_box(h, w, 60.0, 50.0, 0.80)
    content, truth = _irish_chain_content(bh, bw, rng)
    image = _paste(canvas, content, y0, x0)
    side = _base_sidecar("render_on_wood", cap, image, _rect_quad(y0, x0, bh, bw), "wood")
    side.update(truth)
    return image, side


def _perspective_prejpeg(cap: int):
    rng = _rng("render_perspective_jpeg", cap)
    h, w = int(round(cap * 0.75)), cap
    canvas = _apply_factor(_flat(h, w, (243, 240, 235)), _ramp(h, w, 0.97, 1.0))
    y0, x0, bh, bw = _fit_box(h, w, 60.0, 50.0, 0.80)
    content, truth = _irish_chain_content(bh, bw, rng)
    # corners pulled inward, top more than bottom (the renderer's L2 shape)
    top_dx = rng.uniform(0.045, 0.06) * bw
    bot_dx = rng.uniform(0.02, 0.03) * bw
    dys = rng.uniform(0.02, 0.05, size=4) * bh
    quad = [
        [x0 + top_dx, y0 + dys[0]],
        [x0 + bw - top_dx, y0 + dys[1]],
        [x0 + bw - bot_dx, y0 + bh - dys[2]],
        [x0 + bot_dx, y0 + bh - dys[3]],
    ]
    image = _warp_content_onto(canvas, content, [tuple(p) for p in quad])
    side = _base_sidecar("render_perspective_jpeg", cap, image, quad, "white")
    side.update(truth)
    side["jpeg_quality"] = JPEG_QUALITY
    return image, side


def fx_render_perspective_jpeg(cap: int):
    image, side = _perspective_prejpeg(cap)
    buf = io.BytesIO()
    Image.fromarray(image).save(buf, format="JPEG", quality=JPEG_QUALITY, subsampling=2)
    buf.seek(0)
    final = np.asarray(Image.open(buf).convert("RGB"))
    return final, side


def fx_screenshot_composite(cap: int):
    rng = _rng("screenshot_composite", cap)
    h, w = cap, int(round(cap * 0.462))
    canvas = _flat(h, w, PAGE_WHITE)
    top_h, bot_h = int(round(h * 0.07)), int(round(h * 0.11))
    canvas[:top_h] = CHROME_DARK
    canvas[h - bot_h :] = CHROME_DARK
    # address pill and nav dots: light rectangles inside the chrome
    canvas[int(top_h * 0.3) : int(top_h * 0.75), int(w * 0.08) : int(w * 0.92)] = (55, 58, 62)
    for i in range(3):
        cx = int(w * (0.3 + 0.2 * i))
        canvas[h - bot_h // 2 - 6 : h - bot_h // 2 + 6, cx - 6 : cx + 6] = (90, 94, 99)
    y0, x0, bh, bw = _fit_box(h - top_h - bot_h, w, 60.0, 50.0, 0.90)
    content, truth = _irish_chain_content(bh, bw, rng, tint_amp=4)
    image = _paste(canvas, content, top_h + y0, x0)
    quad = _rect_quad(top_h + y0, x0, bh, bw)
    side = _base_sidecar("screenshot_composite", cap, image, quad, "screenshot")
    side.update(truth)
    return image, side


def fx_tall_chrome(cap: int):
    rng = _rng("tall_chrome", cap)
    h, w = cap, int(round(cap * 0.462))
    canvas = _flat(h, w, PAGE_WHITE)
    top_h, bot_h = int(round(h * 0.22)), int(round(h * 0.24))
    canvas[:top_h] = CHROME_DARK
    canvas[h - bot_h :] = CHROME_DARK
    canvas[int(top_h * 0.15) : int(top_h * 0.3), int(w * 0.08) : int(w * 0.92)] = (55, 58, 62)
    canvas[int(top_h * 0.45) : int(top_h * 0.85), int(w * 0.06) : int(w * 0.94)] = (44, 47, 51)
    canvas[h - int(bot_h * 0.8) : h - int(bot_h * 0.55), int(w * 0.1) : int(w * 0.9)] = (
        44,
        47,
        51,
    )
    y0, x0, bh, bw = _fit_box(h - top_h - bot_h, w, 60.0, 50.0, 0.72)
    content, truth = _irish_chain_content(bh, bw, rng, tint_amp=4)
    image = _paste(canvas, content, top_h + y0, x0)
    quad = _rect_quad(top_h + y0, x0, bh, bw)
    side = _base_sidecar("tall_chrome", cap, image, quad, "screenshot")
    side.update(truth)
    return image, side


def fx_edge_to_edge(cap: int):
    rng = _rng("edge_to_edge", cap)
    h = cap
    w = int(round(cap * 50.0 / 60.0))
    content, truth = _irish_chain_content(h, w, rng)
    quad = _rect_quad(0, 0, h, w)
    side = _base_sidecar("edge_to_edge", cap, content, quad, "none")
    side.update(truth)
    return content, side


def fx_white_border_on_white(cap: int):
    rng = _rng("white_border_on_white", cap)
    h, w = int(round(cap * 0.75)), cap
    canvas = _apply_factor(_flat(h, w, (247, 244, 236)), _ramp(h, w, 0.99, 1.0))
    rows, cols, border = 17, 13, 2.0
    y0, x0, bh, bw = _fit_box(h, w, rows + 2 * border, cols + 2 * border, 0.80)
    content, truth = _checker_with_border(bh, bw, rows, cols, border, rng)
    image = _paste(canvas, content, y0, x0)
    side = _base_sidecar("white_border_on_white", cap, image, _rect_quad(y0, x0, bh, bw), "white")
    side.update(truth)
    return image, side


def fx_lighting_gradient(cap: int):
    rng = _rng("lighting_gradient", cap)
    h, w = int(round(cap * 0.75)), cap
    canvas = _flat(h, w, (248, 246, 242))
    y0, x0, bh, bw = _fit_box(h, w, 60.0, 50.0, 0.82)
    content, truth = _irish_chain_content(bh, bw, rng)
    image = _paste(canvas, content, y0, x0)
    # strong gradient, far beyond the renderer's 0.88 floor, whole frame
    image = _apply_factor(image, _ramp(h, w, 0.55, 1.0))
    side = _base_sidecar("lighting_gradient", cap, image, _rect_quad(y0, x0, bh, bw), "white")
    side.update(truth)
    side["lighting_low"] = 0.55
    return image, side


def fx_fabric_print(cap: int):
    rng = _rng("fabric_print", cap)
    canvas, y0, x0, qh, qw = _render_margin_scene(cap, 60.0, 50.0)
    content, truth = _irish_chain_content(qh, qw, rng)
    # print texture over every cell: fine polka dots in a darker shade
    yy = np.arange(qh, dtype=np.float64)[:, None]
    xx = np.arange(qw, dtype=np.float64)[None, :]
    d = max(5.0, qw / 50.0 / 3.5)  # ~3.5 dots per cell pitch
    dots = ((xx % d) - d / 2) ** 2 + ((yy % d) - d / 2) ** 2 <= (d * 0.24) ** 2
    content = np.where(dots[:, :, None], np.clip(content.astype(np.int64) - 26, 0, 255), content)
    content = content.astype(np.uint8)
    image = _paste(canvas, content, y0, x0)
    side = _base_sidecar("fabric_print", cap, image, _rect_quad(y0, x0, qh, qw), "render")
    side.update(truth)
    return image, side


def fx_seam_shadows(cap: int):
    rng = _rng("seam_shadows", cap)
    canvas, y0, x0, qh, qw = _render_margin_scene(cap, 60.0, 50.0)
    content, truth = _irish_chain_content(qh, qw, rng)
    factor = np.ones((qh, qw), dtype=np.float64)
    pitch_x, pitch_y = qw / 50.0, qh / 60.0
    xx = np.arange(qw, dtype=np.float64)
    yy = np.arange(qh, dtype=np.float64)
    # seam shadows: darken within ~0.06 pitch of every cell boundary
    dist_x = np.abs((xx / pitch_x) - np.rint(xx / pitch_x))
    dist_y = np.abs((yy / pitch_y) - np.rint(yy / pitch_y))
    factor *= np.where(dist_y < 0.06, 0.82, 1.0)[:, None]
    factor *= np.where(dist_x < 0.06, 0.82, 1.0)[None, :]
    # quilting: soft diagonal lines every 1.5 pitches (triangle-wave dip)
    diag = _tri((xx[None, :] / pitch_x + yy[:, None] / pitch_y) / 3.0)
    factor *= 1.0 - 0.08 * (diag > 0.93)
    content = _apply_factor(content, factor)
    image = _paste(canvas, content, y0, x0)
    side = _base_sidecar("seam_shadows", cap, image, _rect_quad(y0, x0, qh, qw), "render")
    side.update(truth)
    return image, side


def fx_hst_star(cap: int):
    rng = _rng("hst_star", cap)
    rows, cols = 28, 24  # 7x6 sawtooth star blocks of 4x4 cells
    canvas, y0, x0, qh, qw = _render_margin_scene(cap, float(rows), float(cols))
    content = _hst_field(
        qh, qw, _star_type_map(7, 6), STAR_NAVY, STAR_CREAM, rng, color_center=STAR_CENTER
    )
    image = _paste(canvas, content, y0, x0)
    side = _base_sidecar("hst_star", cap, image, _rect_quad(y0, x0, qh, qw), "render")
    side.update(
        {
            "grid": {"rows": rows, "cols": cols, "border_pitches": 0.0},
            "palette_hex": [
                _rgb_to_hex(STAR_NAVY),
                _rgb_to_hex(STAR_CENTER),
                _rgb_to_hex(STAR_CREAM),
            ],
            "repeat_cells": [4, 4],
            "character": "non_square",
        }
    )
    return image, side


def fx_low_contrast_hst(cap: int):
    rng = _rng("low_contrast_hst", cap)
    rows, cols = 28, 24
    canvas, y0, x0, qh, qw = _render_margin_scene(cap, float(rows), float(cols))
    content = _hst_field(qh, qw, _star_type_map(7, 6), LOWC_A, LOWC_B, rng, tint_amp=3)
    image = _paste(canvas, content, y0, x0)
    side = _base_sidecar("low_contrast_hst", cap, image, _rect_quad(y0, x0, qh, qw), "render")
    side.update(
        {
            "grid": {"rows": rows, "cols": cols, "border_pitches": 0.0},
            "palette_hex": [_rgb_to_hex(LOWC_A), _rgb_to_hex(LOWC_B)],
            "repeat_cells": [4, 4],
            "character": "non_square",
        }
    )
    return image, side


def fx_drunkards_path(cap: int):
    rng = _rng("drunkards_path", cap)
    rows, cols = 14, 12
    canvas, y0, x0, qh, qw = _render_margin_scene(cap, float(rows), float(cols))
    content = _drunkards_field(qh, qw, rows, cols, rng)
    image = _paste(canvas, content, y0, x0)
    side = _base_sidecar("drunkards_path", cap, image, _rect_quad(y0, x0, qh, qw), "render")
    side.update(
        {
            "grid": {"rows": rows, "cols": cols, "border_pitches": 0.0},
            "palette_hex": [_rgb_to_hex(DP_TEAL), _rgb_to_hex(DP_IVORY)],
            "repeat_cells": [2, 2],
            "character": "non_square",
        }
    )
    return image, side


def fx_busy_print_squares(cap: int):
    rng = _rng("busy_print_squares", cap)
    rows, cols = 13, 11
    labels = _rng("busy_print_squares_labels", cap).integers(0, 2, size=(rows, cols))
    canvas, y0, x0, qh, qw = _render_margin_scene(cap, float(rows), float(cols))
    content = _busy_print_field(qh, qw, labels, rng)
    image = _paste(canvas, content, y0, x0)
    side = _base_sidecar("busy_print_squares", cap, image, _rect_quad(y0, x0, qh, qw), "render")
    side.update(
        {
            "grid": {"rows": rows, "cols": cols, "border_pitches": 0.0},
            "palette_hex": [_rgb_to_hex(BUSY_RED), _rgb_to_hex(BUSY_NAVY)],
            "repeat_cells": None,
            "character": "squares",
            "cells": labels.tolist(),
        }
    )
    return image, side


def fx_solid_fabric(cap: int):
    h, w = int(round(cap * 0.75)), cap
    canvas, y0, x0, qh, qw = _render_margin_scene(cap, float(h), float(w))
    # one fabric, no piecing: a flat panel with a gentle radial vignette
    yy = (np.arange(qh, dtype=np.float64)[:, None] - qh / 2) / qh
    xx = (np.arange(qw, dtype=np.float64)[None, :] - qw / 2) / qw
    vignette = 1.0 - 0.05 * np.sqrt(xx**2 + yy**2)
    content = _apply_factor(_flat(qh, qw, SOLID_GREEN), vignette)
    image = _paste(canvas, content, y0, x0)
    side = _base_sidecar("solid_fabric", cap, image, _rect_quad(y0, x0, qh, qw), "render")
    side.update(
        {
            "grid": None,
            "palette_hex": [_rgb_to_hex(SOLID_GREEN)],
            "repeat_cells": None,
            "character": "no_pattern",
        }
    )
    return image, side


FIXTURES = {
    "render_on_white": fx_render_on_white,
    "render_on_wood": fx_render_on_wood,
    "render_perspective_jpeg": fx_render_perspective_jpeg,
    "screenshot_composite": fx_screenshot_composite,
    "tall_chrome": fx_tall_chrome,
    "edge_to_edge": fx_edge_to_edge,
    "white_border_on_white": fx_white_border_on_white,
    "lighting_gradient": fx_lighting_gradient,
    "fabric_print": fx_fabric_print,
    "seam_shadows": fx_seam_shadows,
    "hst_star": fx_hst_star,
    "drunkards_path": fx_drunkards_path,
    "busy_print_squares": fx_busy_print_squares,
    "low_contrast_hst": fx_low_contrast_hst,
    "solid_fabric": fx_solid_fabric,
}

# fixtures whose committed pixels are NOT byte-reproducible (JPEG stage)
JPEG_FIXTURES = {"render_perspective_jpeg"}


def generate(name: str, cap: int) -> tuple[np.ndarray, dict]:
    return FIXTURES[name](cap)


def fixture_path(name: str, cap: int) -> Path:
    return ROOT / f"{name}_{cap}.png"


def sidecar_path(name: str, cap: int) -> Path:
    return ROOT / f"{name}_{cap}.json"


def write_all() -> None:
    for name in FIXTURES:
        for cap in CAPS:
            image, side = generate(name, cap)
            Image.fromarray(image).save(fixture_path(name, cap), format="PNG", optimize=True)
            sidecar_path(name, cap).write_text(
                json.dumps(side, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
            )
            kb = fixture_path(name, cap).stat().st_size / 1024
            print(f"wrote {name}_{cap}.png ({kb:.0f} KB)")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "write":
        write_all()
    else:
        print("usage: python generator.py write   (regenerates committed fixtures)")
