"""Pydantic schema for the QREP quilt model.

All lengths are integer eighths of an inch (see qrep.model.units). CV
confidence lives in three places: provenance.stage_confidence (per CV stage),
GridRegion.cell_confidence (per cell) and FinishedSizeBasis.confidence (a size
estimated from the photo). Hand-authored models omit the first two; the
effective_* helpers fill in the 1.0 defaults. User facts (the confirmed block
structure, a typed or preset size) record confidence 1.0 (docs/SPEC.md
section 8).
"""

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# The CV pipeline stages that report confidence. Hand-authored models omit
# stage_confidence entirely and every stage defaults to 1.0.
STAGES = ("rectify", "palette", "grid", "cells", "repeat", "border")

_HEX_RE = re.compile(r"^#[0-9a-f]{6}$")


class QrepSchemaError(ValueError):
    """Raised when quilt JSON has a missing or unsupported schema_version."""


class Fabric(BaseModel):
    id: str
    name: str
    color: str

    @field_validator("color")
    @classmethod
    def _hex_color(cls, v: str) -> str:
        v = v.lower()
        if not _HEX_RE.match(v):
            raise ValueError(f"fabric color must be #rrggbb hex, got {v!r}")
        return v


class Palette(BaseModel):
    fabrics: list[Fabric]

    @model_validator(mode="after")
    def _unique_ids(self) -> "Palette":
        ids = [f.id for f in self.fabrics]
        if len(ids) != len(set(ids)):
            raise ValueError(f"palette fabric ids must be unique, got {ids}")
        return self

    def fabric_ids(self) -> set[str]:
        return {f.id for f in self.fabrics}

    def by_id(self, fabric_id: str) -> Fabric:
        for f in self.fabrics:
            if f.id == fabric_id:
                return f
        raise KeyError(f"no fabric with id {fabric_id!r} in palette")


class GridRegion(BaseModel):
    """Rectilinear grid of cells; the one region type v1 implements.

    The `kind` discriminator is the extension point for non-grid region types.
    """

    kind: str = "grid"
    rows: int = Field(gt=0)
    cols: int = Field(gt=0)
    cell_size: int = Field(gt=0, description="finished cell size in eighths")
    cells: list[list[str]]
    cell_confidence: list[list[float]] | None = None

    @model_validator(mode="after")
    def _dims_match(self) -> "GridRegion":
        if len(self.cells) != self.rows:
            raise ValueError(f"cells has {len(self.cells)} rows, expected {self.rows}")
        for i, row in enumerate(self.cells):
            if len(row) != self.cols:
                raise ValueError(f"cells row {i} has {len(row)} cols, expected {self.cols}")
        if self.cell_confidence is not None:
            if len(self.cell_confidence) != self.rows:
                raise ValueError("cell_confidence row count does not match rows")
            for i, row in enumerate(self.cell_confidence):
                if len(row) != self.cols:
                    raise ValueError(f"cell_confidence row {i} does not match cols")
                for v in row:
                    if not 0.0 <= v <= 1.0:
                        raise ValueError(f"cell confidence {v} outside [0, 1]")
        return self

    def effective_cell_confidence(self) -> list[list[float]]:
        """Per-cell confidence; hand-authored grids (no array) default to 1.0."""
        if self.cell_confidence is not None:
            return self.cell_confidence
        return [[1.0] * self.cols for _ in range(self.rows)]

    @property
    def width(self) -> int:
        return self.cols * self.cell_size

    @property
    def height(self) -> int:
        return self.rows * self.cell_size


class BorderBand(BaseModel):
    fabric_id: str
    width: int = Field(gt=0, description="finished band width in eighths, all four sides")


class Binding(BaseModel):
    fabric_id: str
    strip_width: int = Field(default=20, gt=0, description="cut strip width in eighths (2.5in)")


class QuiltingMotif(BaseModel):
    """Authored quilting motif over a rectangular region of the finished top."""

    name: str
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class QuiltingLayer(BaseModel):
    """Authored-only in v1; renders on diagrams, never detected."""

    motifs: list[QuiltingMotif] = Field(default_factory=list)
    density: float | None = Field(default=None, description="stitches per inch, authored")


class Settings(BaseModel):
    """Math defaults, all in eighths unless noted. Overridable per quilt."""

    seam_allowance: int = Field(default=2, gt=0)
    # Strip cutting assumes 40in usable (MATH.md D-05); backing has its own width.
    wof: int = Field(default=320, gt=0, description="usable width of fabric for strips, 40in")
    binding_strip_width: int = Field(default=20, gt=0)
    binding_extra: int = Field(default=80, ge=0, description="binding length beyond perimeter")
    backing_margin: int = Field(default=64, ge=0, description="extra per axis for backing, 8in")
    # Each backing seam loses 1in (8), so a narrower width could never grow
    # a pieced backing (qrep/construct/finishing.py, BACKING_SEAM_LOSS).
    backing_width: int = Field(
        default=336, gt=8, description="backing fabric width, selvages trimmed, 42in"
    )
    wide_back_width: int = Field(default=864, gt=0, description="wide-back fabric width, 108in")
    backing_pieced_allowance: int = Field(
        default=72, ge=0, description="squaring allowance, backing of 2+ panels, 9in"
    )
    backing_one_piece_allowance: int = Field(
        default=36, ge=0, description="squaring allowance, one-piece or wide backing, 4.5in"
    )
    purchase_increment: int = Field(default=72, gt=0, description="purchase rounding step, 1/4yd")
    top_margin: int = Field(
        default=10, ge=0, description="percent added to each quilt-top fabric's strip plan"
    )

    @model_validator(mode="after")
    def _wide_back_is_wider(self) -> "Settings":
        if self.wide_back_width <= self.backing_width:
            raise ValueError(
                f"wide_back_width {self.wide_back_width} must exceed backing_width "
                f"{self.backing_width}"
            )
        return self

    @property
    def cut_add(self) -> int:
        """Cut size = finished size + 2 * seam allowance (1/2in at defaults)."""
        return 2 * self.seam_allowance


class Provenance(BaseModel):
    source: str = "authored"
    stage_confidence: dict[str, float] = Field(default_factory=dict)

    @field_validator("stage_confidence")
    @classmethod
    def _known_stages(cls, v: dict[str, float]) -> dict[str, float]:
        for stage, conf in v.items():
            if stage not in STAGES:
                raise ValueError(f"unknown confidence stage {stage!r}, expected one of {STAGES}")
            if not 0.0 <= conf <= 1.0:
                raise ValueError(f"stage {stage!r} confidence {conf} outside [0, 1]")
        return v

    def effective_stage_confidence(self) -> dict[str, float]:
        """All six stages; stages a hand-authored model omits default to 1.0."""
        return {stage: self.stage_confidence.get(stage, 1.0) for stage in STAGES}


class QuiltMetadata(BaseModel):
    name: str
    notes: str = ""


class ConfirmedBlocks(BaseModel):
    """The block structure the user confirmed: blocks across and down, times
    squares per block on each axis. Construction uses it instead of
    re-inferring the period, so a few misread squares cannot flip the method."""

    blocks_across: int = Field(gt=0)
    blocks_down: int = Field(gt=0)
    squares_across: int = Field(gt=0, description="squares per block across")
    squares_down: int = Field(gt=0, description="squares per block down")
    confidence: float = 1.0

    @field_validator("confidence")
    @classmethod
    def _user_fact(cls, v: float) -> float:
        if v != 1.0:
            raise ValueError(
                f"a confirmed block structure is a user fact at confidence 1.0, got {v}"
            )
        return v


class FinishedSizeBasis(BaseModel):
    """How the finished size was set, so the pattern can say so.

    A typed size gives a width, a height or both; a preset gives both; a
    default sets nothing, and its size is estimated from the photo. A typed
    or preset size is a user fact at confidence 1.0, which it may leave out;
    a default size must state the estimate's confidence (1.0 only when
    hand-authored), so a guess is never stored as certain by omission.
    """

    source: Literal["typed", "preset", "default"]
    requested_width: int | None = Field(default=None, gt=0)
    requested_height: int | None = Field(default=None, gt=0)
    achieved_width: int = Field(gt=0)
    achieved_height: int = Field(gt=0)
    rounding_step: int = Field(
        gt=0, description="rounding applied: the finished square size snaps to this step, eighths"
    )
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="before")
    @classmethod
    def _user_set_size_is_certain(cls, data):
        if isinstance(data, dict) and data.get("source") in ("typed", "preset"):
            return {"confidence": 1.0, **data}
        return data

    @model_validator(mode="after")
    def _source_matches_request(self) -> "FinishedSizeBasis":
        given = (self.requested_width is not None, self.requested_height is not None)
        if self.source == "typed" and not any(given):
            raise ValueError("a typed size needs a requested width or height")
        if self.source == "preset" and not all(given):
            raise ValueError("a preset size records both requested width and height")
        if self.source == "default" and any(given):
            raise ValueError("a default size records no requested width or height")
        if self.source != "default" and self.confidence != 1.0:
            raise ValueError(
                f"a {self.source} size is a user fact at confidence 1.0, got {self.confidence}"
            )
        return self


class Quilt(BaseModel):
    schema_version: str = "1"
    metadata: QuiltMetadata
    palette: Palette
    center: GridRegion
    borders: list[BorderBand] = Field(default_factory=list)
    binding: Binding
    quilting: QuiltingLayer = Field(default_factory=QuiltingLayer)
    settings: Settings = Field(default_factory=Settings)
    provenance: Provenance = Field(default_factory=Provenance)
    # Optional under schema_version 1, and last, so a model written without
    # them loads unchanged and older keys keep their serialized order.
    confirmed_blocks: ConfirmedBlocks | None = None
    size_basis: FinishedSizeBasis | None = None

    @field_validator("schema_version")
    @classmethod
    def _major_one(cls, v: str) -> str:
        if str(v).split(".")[0] != "1":
            raise ValueError(f'unsupported schema_version {v!r}; this build reads major version "1"')
        return v

    @model_validator(mode="after")
    def _fabric_refs_exist(self) -> "Quilt":
        known = self.palette.fabric_ids()
        used: set[str] = set()
        for row in self.center.cells:
            used.update(row)
        used.update(b.fabric_id for b in self.borders)
        used.add(self.binding.fabric_id)
        missing = sorted(used - known)
        if missing:
            raise ValueError(f"fabric ids {missing} referenced but not in palette {sorted(known)}")
        return self

    @model_validator(mode="after")
    def _binding_strip_fits_the_fabric(self) -> "Quilt":
        # Each diagonal join uses one strip width (MATH.md F7), so a strip at
        # least as wide as the usable width yields no binding length.
        if self.binding.strip_width >= self.settings.wof:
            raise ValueError(
                f"binding strip width {self.binding.strip_width} must be narrower than the "
                f"usable width of fabric {self.settings.wof}"
            )
        return self

    @property
    def finished_width(self) -> int:
        return self.center.width + 2 * sum(b.width for b in self.borders)

    @property
    def finished_height(self) -> int:
        return self.center.height + 2 * sum(b.width for b in self.borders)

    @property
    def perimeter(self) -> int:
        return 2 * (self.finished_width + self.finished_height)

    @property
    def binding_length(self) -> int:
        return self.perimeter + self.settings.binding_extra
