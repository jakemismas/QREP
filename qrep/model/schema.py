"""Pydantic schema for the QREP quilt model.

All lengths are integer eighths of an inch (see qrep.model.units). Confidence
lives in exactly two places: provenance.stage_confidence (per CV stage) and
GridRegion.cell_confidence (per cell). Hand-authored models omit both; the
effective_* helpers fill in the 1.0 defaults.
"""

import re

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
    wof: int = Field(default=336, gt=0, description="usable width of fabric, 42in")
    binding_strip_width: int = Field(default=20, gt=0)
    binding_extra: int = Field(default=80, ge=0, description="binding length beyond perimeter")
    backing_margin: int = Field(default=64, ge=0, description="extra per axis for backing, 8in")

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
