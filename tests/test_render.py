"""Synthetic renderer tests: geometry, color fidelity, determinism, homography.

Fixture at scale 10: quilt 750x900 px, margin = round(0.08 * 900) = 72,
canvas 894x1044. Palette RGB: blue #9db8d9 = (157,184,217), cream #f2e8d5 =
(242,232,213), background #404040 = (64,64,64)."""

import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from typer.testing import CliRunner

from qrep.cli import app
from qrep.model import load
from qrep.render import render, save_render

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "double_irish_chain.json"
GENERATED_DIR = Path(__file__).parent / "fixtures" / "_generated"

BLUE = (157, 184, 217)
CREAM = (242, 232, 213)

runner = CliRunner()


@pytest.fixture
def quilt():
    return load(FIXTURE_PATH)


def test_l0_geometry_and_margin(quilt):
    result = render(quilt, level=0)
    # canvas = quilt + 2 x margin on each axis
    assert result.margin == 72
    assert result.image.size == (750 + 144, 900 + 144)
    # quilt rectangle (canvas minus known margin) matches model aspect within 1 px
    quilt_w = result.image.size[0] - 2 * result.margin
    quilt_h = result.image.size[1] - 2 * result.margin
    assert abs(quilt_w - 750) <= 1 and abs(quilt_h - 900) <= 1
    # corners of the sidecar are the exact unwarped quilt rect at L0
    assert result.corners == [(72.0, 72.0), (822.0, 72.0), (822.0, 972.0), (72.0, 972.0)]
    # background margin is #404040
    assert result.image.getpixel((5, 5)) == (64, 64, 64)


def test_l0_every_cell_center_matches_palette_exactly(quilt):
    result = render(quilt, level=0)
    expected = {"b": BLUE, "c": CREAM}
    for r, row in enumerate(quilt.center.cells):
        for c, fabric_id in enumerate(row):
            x, y = result.base_cell_center(r, c)
            assert result.image.getpixel((round(x), round(y))) == expected[fabric_id], (r, c)


def test_l0_border_band_pixels_match_border_fabric(quilt):
    result = render(quilt, level=0)
    # border ring is 30 eighths = 37.5 px wide; sample well inside it on all
    # four sides (18 px in from the quilt edge)
    m = result.margin
    for point in [
        (m + 18, m + 18),
        (m + 750 - 19, m + 18),
        (m + 375, m + 900 - 19),
        (m + 18, m + 450),
    ]:
        assert result.image.getpixel(point) == CREAM, point


@pytest.mark.parametrize("level", [1, 3])
def test_seed_determinism(quilt, tmp_path, level):
    a1, _ = save_render(quilt, tmp_path / "a1.png", level=level, seed=42)
    a2, _ = save_render(quilt, tmp_path / "a2.png", level=level, seed=42)
    b, _ = save_render(quilt, tmp_path / "b.png", level=level, seed=43)
    assert a1.read_bytes() == a2.read_bytes()
    assert a1.read_bytes() != b.read_bytes()


def test_l2_sidecar_corners_consistent_with_homography(quilt):
    result = render(quilt, level=2, seed=42)
    base = [(72, 72), (822, 72), (822, 972), (72, 972)]
    # every corner moved inward by 3-6 percent of the 750 px width on each axis
    for (bx, by), (wx, wy) in zip(base, result.corners):
        assert 0.03 * 750 <= abs(wx - bx) <= 0.06 * 750
        assert 0.03 * 750 <= abs(wy - by) <= 0.06 * 750
    # rebuild the base->output homography from the sidecar corners alone,
    # forward-map interior cell centers, and re-check the sampled color by
    # nearest palette entry (lighting is bounded, so nearest stays correct)
    matrix = cv2.getPerspectiveTransform(np.float32(base), np.float32(result.corners))
    samples = {(2, 2): BLUE, (12, 12): BLUE, (32, 32): BLUE, (2, 7): CREAM, (22, 27): CREAM}
    for (r, c), expected in samples.items():
        x, y = result.base_cell_center(r, c)
        vec = matrix @ np.array([x, y, 1.0])
        px, py = vec[0] / vec[2], vec[1] / vec[2]
        got = result.image.getpixel((round(px), round(py)))
        dist_blue = sum((a - b) ** 2 for a, b in zip(got, BLUE))
        dist_cream = sum((a - b) ** 2 for a, b in zip(got, CREAM))
        nearest = BLUE if dist_blue < dist_cream else CREAM
        assert nearest == expected, (r, c, got)


def test_cli_renders_all_four_levels(quilt):
    GENERATED_DIR.mkdir(exist_ok=True)
    for level in range(4):
        out = GENERATED_DIR / f"cli_l{level}.png"
        result = runner.invoke(
            app,
            [
                "render",
                str(FIXTURE_PATH),
                "--level",
                str(level),
                "--seed",
                "42",
                "-o",
                str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        assert out.exists() and out.stat().st_size > 0
        sidecar = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
        assert sidecar["level"] == level
        assert sidecar["seed"] == 42
        assert len(sidecar["corners"]) == 4


def test_render_rejects_bad_level(quilt):
    with pytest.raises(ValueError, match="level must be"):
        render(quilt, level=4)
