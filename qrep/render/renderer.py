"""Synthetic renderer: quilt model to PNG at difficulty levels L0-L3.

The test oracle for the CV pipeline. Every stochastic effect draws from one
numpy.random.default_rng(seed) in a fixed order, so the same seed always
produces byte-identical PNGs. The sidecar ground truth (true corners, seed,
level) exists for the round-trip harness only; the pipeline under test never
reads it.
"""

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from qrep.model.schema import Quilt

BACKGROUND = (0x40, 0x40, 0x40)  # guaranteed absent from any palette
MARGIN_FRACTION = 0.08
OCCLUSION_COLOR = (0x6B, 0x5D, 0x4F)


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    return tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))


class RenderResult:
    """A rendered quilt plus the ground truth the harness compares against."""

    def __init__(
        self,
        image: Image.Image,
        corners: list[tuple[float, float]],
        level: int,
        seed: int,
        scale: int,
        margin: int,
        quilt: Quilt,
    ):
        self.image = image
        self.corners = corners  # TL, TR, BR, BL in pixel coordinates
        self.level = level
        self.seed = seed
        self.scale = scale
        self.margin = margin
        self._quilt = quilt

    def base_cell_center(self, row: int, col: int) -> tuple[float, float]:
        """Center of a center-field cell in BASE (unwarped) pixel coordinates."""
        border = sum(b.width for b in self._quilt.borders)
        cell = self._quilt.center.cell_size
        x = self.margin + (border + (col + 0.5) * cell) * self.scale / 8
        y = self.margin + (border + (row + 0.5) * cell) * self.scale / 8
        return (x, y)

    def sidecar(self) -> dict:
        return {
            "level": self.level,
            "seed": self.seed,
            "scale": self.scale,
            "margin": self.margin,
            "corners": [[round(x, 3), round(y, 3)] for x, y in self.corners],
            "quilt_px": [
                round(self._quilt.finished_width * self.scale / 8, 3),
                round(self._quilt.finished_height * self.scale / 8, 3),
            ],
        }


def _base_image(quilt: Quilt, scale: int) -> tuple[Image.Image, int, int, int]:
    """L0 base: flat colors, integer rectangle fills, no antialiasing."""
    width = round(quilt.finished_width * scale / 8)
    height = round(quilt.finished_height * scale / 8)
    margin = round(MARGIN_FRACTION * max(width, height))
    image = Image.new("RGB", (width + 2 * margin, height + 2 * margin), BACKGROUND)
    draw = ImageDraw.Draw(image)
    colors = {f.id: _hex_to_rgb(f.color) for f in quilt.palette.fabrics}

    def px(eighths: int) -> int:
        # half-up, not round(): banker's rounding puts x.5 boundaries
        # alternately up and down, making cells alternate 14/16 px wide and
        # giving the edge pattern a spurious 2-cell period
        return int(eighths * scale / 8 + 0.5)

    # border bands, outermost first, then the center cells on top
    inset = 0
    for band in reversed(quilt.borders):
        draw.rectangle(
            [
                margin + px(inset),
                margin + px(inset),
                margin + px(quilt.finished_width - inset) - 1,
                margin + px(quilt.finished_height - inset) - 1,
            ],
            fill=colors[band.fabric_id],
        )
        inset += band.width
    border_total = sum(b.width for b in quilt.borders)
    cell = quilt.center.cell_size
    for r, row in enumerate(quilt.center.cells):
        for c, fabric_id in enumerate(row):
            draw.rectangle(
                [
                    margin + px(border_total + c * cell),
                    margin + px(border_total + r * cell),
                    margin + px(border_total + (c + 1) * cell) - 1,
                    margin + px(border_total + (r + 1) * cell) - 1,
                ],
                fill=colors[fabric_id],
            )
    return image, width, height, margin


def _quilt_slice(margin: int, width: int, height: int) -> tuple[slice, slice]:
    return slice(margin, margin + height), slice(margin, margin + width)


def _apply_texture(image: Image.Image, quilt: Quilt, rng, margin: int, width: int, height: int):
    """L1: per-cell color variance plus pixel noise over the quilt region."""
    draw = ImageDraw.Draw(image)
    colors = {f.id: _hex_to_rgb(f.color) for f in quilt.palette.fabrics}
    scale_px = width / (quilt.finished_width / 8)

    def px(eighths: int) -> int:
        # half-up for the same reason as the base image (see _base_image)
        return int(eighths * scale_px / 8 + 0.5)

    border_total = sum(b.width for b in quilt.borders)
    cell = quilt.center.cell_size
    # per-patch variance: one bounded shift per cell, fixed draw order
    for r, row in enumerate(quilt.center.cells):
        for c, fabric_id in enumerate(row):
            shift = rng.integers(-6, 7, size=3)
            base = colors[fabric_id]
            tinted = tuple(int(np.clip(base[i] + shift[i], 0, 255)) for i in range(3))
            draw.rectangle(
                [
                    margin + px(border_total + c * cell),
                    margin + px(border_total + r * cell),
                    margin + px(border_total + (c + 1) * cell) - 1,
                    margin + px(border_total + (r + 1) * cell) - 1,
                ],
                fill=tinted,
            )
    array = np.asarray(image).astype(np.int16)
    ys, xs = _quilt_slice(margin, width, height)
    noise = rng.normal(0, 2.5, size=array[ys, xs].shape)
    array[ys, xs] = np.clip(array[ys, xs] + noise, 0, 255)
    return Image.fromarray(array.astype(np.uint8))


def _apply_perspective(
    image: Image.Image, rng, margin: int, width: int, height: int
) -> tuple[Image.Image, list[tuple[float, float]]]:
    """L2 geometry: corners pulled inward 3-6 percent of quilt width, seeded."""
    src = [
        (margin, margin),
        (margin + width, margin),
        (margin + width, margin + height),
        (margin, margin + height),
    ]
    # inward unit direction per corner: TL (+,+), TR (-,+), BR (-,-), BL (+,-)
    directions = [(1, 1), (-1, 1), (-1, -1), (1, -1)]
    # A real camera tilt forshortens one edge: the top corners pull inward
    # noticeably more than the bottom ones (all inside the 3-6 percent bound).
    # A symmetric pinch would look like a plain scale-down and let the
    # rectifier's identity path fire, defeating the L2 non-identity contract.
    bottom_dx = rng.uniform(0.03, 0.042) * width
    top_dx = min(0.06, bottom_dx / width + rng.uniform(0.015, 0.018)) * width
    inward_dx = [top_dx, top_dx, bottom_dx, bottom_dx]
    dst = []
    for (x, y), (sx, sy), dx in zip(src, directions, inward_dx):
        dy = rng.uniform(0.03, 0.06) * width
        dst.append((x + sx * dx, y + sy * dy))
    # PIL PERSPECTIVE coefficients map OUTPUT pixels to INPUT sample points,
    # which is exactly the dst -> src homography.
    matrix = cv2.getPerspectiveTransform(np.float32(dst), np.float32(src))
    coeffs = matrix.flatten()[:8]
    warped = image.transform(
        image.size,
        Image.Transform.PERSPECTIVE,
        tuple(float(v) for v in coeffs),
        resample=Image.Resampling.BILINEAR,
        fillcolor=BACKGROUND,
    )
    return warped, dst


def _apply_lighting(image: Image.Image, rng) -> Image.Image:
    """L2 lighting: bounded linear gradient (0.88-1.0) at a seeded angle,
    mild enough that nearest-palette color assignment still resolves."""
    w, h = image.size
    angle = rng.uniform(0, 2 * np.pi)
    low = rng.uniform(0.88, 0.94)
    xs = np.linspace(0, 1, w)
    ys = np.linspace(0, 1, h)
    grid_x, grid_y = np.meshgrid(xs, ys)
    ramp = grid_x * np.cos(angle) + grid_y * np.sin(angle)
    ramp = (ramp - ramp.min()) / (ramp.max() - ramp.min())
    factor = low + (1.0 - low) * ramp
    array = np.asarray(image).astype(np.float64) * factor[:, :, None]
    return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8))


def _apply_l3_effects(
    image: Image.Image, rng, margin: int, width: int, height: int
) -> Image.Image:
    """L3: mild fold shading, background clutter, one partial occlusion."""
    array = np.asarray(image).astype(np.float64)
    ys, xs = _quilt_slice(margin, width, height)
    # folds: three soft vertical darkening bands across the quilt
    x_norm = np.linspace(0, 1, width)
    profile = np.ones(width)
    for _ in range(3):
        center = rng.uniform(0.15, 0.85)
        sigma = rng.uniform(0.02, 0.05)
        depth = rng.uniform(0.05, 0.10)
        profile -= depth * np.exp(-((x_norm - center) ** 2) / (2 * sigma**2))
    array[ys, xs] *= np.clip(profile, 0.8, 1.0)[None, :, None]
    image = Image.fromarray(np.clip(array, 0, 255).astype(np.uint8))

    draw = ImageDraw.Draw(image)
    canvas_w, canvas_h = image.size
    # clutter: six seeded rectangles in the margin ring, never over the quilt
    for _ in range(6):
        cw = int(rng.integers(margin // 3, margin))
        ch = int(rng.integers(margin // 3, margin))
        side = int(rng.integers(0, 4))
        if side == 0:  # top strip
            x0 = int(rng.integers(0, canvas_w - cw))
            y0 = int(rng.integers(0, max(1, margin - ch)))
        elif side == 1:  # bottom strip
            x0 = int(rng.integers(0, canvas_w - cw))
            y0 = int(rng.integers(canvas_h - margin, canvas_h - ch))
        elif side == 2:  # left strip
            x0 = int(rng.integers(0, max(1, margin - cw)))
            y0 = int(rng.integers(0, canvas_h - ch))
        else:  # right strip
            x0 = int(rng.integers(canvas_w - margin, canvas_w - cw))
            y0 = int(rng.integers(0, canvas_h - ch))
        color = tuple(int(v) for v in rng.integers(50, 200, size=3))
        draw.rectangle([x0, y0, x0 + cw, y0 + ch], fill=color)
    # occlusion: one rectangle over a seeded corner of the quilt
    corner = int(rng.integers(0, 4))
    ow = int(rng.uniform(0.08, 0.12) * width)
    oh = int(rng.uniform(0.08, 0.12) * height)
    corner_xy = [
        (margin, margin),
        (margin + width - ow, margin),
        (margin + width - ow, margin + height - oh),
        (margin, margin + height - oh),
    ][corner]
    draw.rectangle(
        [corner_xy[0], corner_xy[1], corner_xy[0] + ow, corner_xy[1] + oh],
        fill=OCCLUSION_COLOR,
    )
    return image


def render(quilt: Quilt, level: int = 0, seed: int = 42, scale: int = 10) -> RenderResult:
    if not 0 <= level <= 3:
        raise ValueError(f"level must be 0..3, got {level}")
    rng = np.random.default_rng(seed)
    image, width, height, margin = _base_image(quilt, scale)
    corners = [
        (float(margin), float(margin)),
        (float(margin + width), float(margin)),
        (float(margin + width), float(margin + height)),
        (float(margin), float(margin + height)),
    ]
    if level >= 1:
        image = _apply_texture(image, quilt, rng, margin, width, height)
    if level == 2:
        image, warped = _apply_perspective(image, rng, margin, width, height)
        corners = [(float(x), float(y)) for x, y in warped]
        image = _apply_lighting(image, rng)
    if level == 3:
        image = _apply_l3_effects(image, rng, margin, width, height)
    return RenderResult(image, corners, level, seed, scale, margin, quilt)


def save_render(
    quilt: Quilt, path: str | Path, level: int = 0, seed: int = 42, scale: int = 10
) -> tuple[Path, Path]:
    """Write the PNG and its sidecar JSON (same stem, .json suffix)."""
    path = Path(path)
    result = render(quilt, level=level, seed=seed, scale=scale)
    result.image.save(path, format="PNG")
    sidecar_path = path.with_suffix(".json")
    sidecar_path.write_text(
        json.dumps(result.sidecar(), indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return path, sidecar_path
