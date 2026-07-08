"""Schema, serialization, and validation tests for the quilt model."""

import json

import pytest
from pydantic import ValidationError

from qrep.model import (
    Binding,
    BorderBand,
    Fabric,
    GridRegion,
    Palette,
    Provenance,
    QrepSchemaError,
    Quilt,
    QuiltMetadata,
    dumps,
    loads,
)


def small_quilt() -> Quilt:
    """2x3 grid of 1-inch cells (8 eighths), one 1/2-inch border (4), red binding."""
    return Quilt(
        metadata=QuiltMetadata(name="tiny"),
        palette=Palette(
            fabrics=[
                Fabric(id="r", name="Red", color="#cc3333"),
                Fabric(id="w", name="White", color="#ffffff"),
            ]
        ),
        center=GridRegion(rows=2, cols=3, cell_size=8, cells=[["r", "w", "r"], ["w", "r", "w"]]),
        borders=[BorderBand(fabric_id="w", width=4)],
        binding=Binding(fabric_id="r"),
    )


def test_round_trip_exact_equality():
    quilt = small_quilt()
    assert loads(dumps(quilt)) == quilt


def test_round_trip_preserves_confidence_and_quilting():
    quilt = small_quilt()
    quilt = quilt.model_copy(
        update={
            "provenance": Provenance(
                source="cv", stage_confidence={"rectify": 0.9, "palette": 0.75}
            ),
            "center": GridRegion(
                rows=2,
                cols=3,
                cell_size=8,
                cells=[["r", "w", "r"], ["w", "r", "w"]],
                cell_confidence=[[1.0, 0.5, 0.25], [0.0, 1.0, 0.875]],
            ),
        }
    )
    again = loads(dumps(quilt))
    assert again == quilt
    assert again.center.cell_confidence == [[1.0, 0.5, 0.25], [0.0, 1.0, 0.875]]


def test_missing_schema_version_raises():
    data = json.loads(dumps(small_quilt()))
    del data["schema_version"]
    with pytest.raises(QrepSchemaError, match="schema_version"):
        loads(json.dumps(data))


def test_unknown_major_version_raises():
    data = json.loads(dumps(small_quilt()))
    data["schema_version"] = "2"
    with pytest.raises(QrepSchemaError, match="unsupported schema_version"):
        loads(json.dumps(data))


def test_invalid_json_raises():
    with pytest.raises(QrepSchemaError, match="not valid JSON"):
        loads("this is not json")


def test_non_object_json_raises():
    with pytest.raises(QrepSchemaError, match="object at the top level"):
        loads("[1, 2, 3]")


def test_unknown_fabric_id_rejected():
    with pytest.raises(ValidationError, match="not in palette"):
        Quilt(
            metadata=QuiltMetadata(name="bad"),
            palette=Palette(fabrics=[Fabric(id="r", name="Red", color="#cc3333")]),
            center=GridRegion(rows=1, cols=1, cell_size=8, cells=[["ghost"]]),
            binding=Binding(fabric_id="r"),
        )


def test_grid_dimension_mismatch_rejected():
    with pytest.raises(ValidationError, match="rows"):
        GridRegion(rows=2, cols=2, cell_size=8, cells=[["r", "r"]])
    with pytest.raises(ValidationError, match="cols"):
        GridRegion(rows=1, cols=2, cell_size=8, cells=[["r"]])


def test_bad_hex_color_rejected():
    with pytest.raises(ValidationError, match="hex"):
        Fabric(id="x", name="Bad", color="red")


def test_unknown_stage_rejected():
    with pytest.raises(ValidationError, match="unknown confidence stage"):
        Provenance(stage_confidence={"vibes": 1.0})


def test_confidence_out_of_range_rejected():
    with pytest.raises(ValidationError, match="outside"):
        Provenance(stage_confidence={"rectify": 1.5})
    with pytest.raises(ValidationError, match="outside"):
        GridRegion(rows=1, cols=1, cell_size=8, cells=[["r"]], cell_confidence=[[2.0]])


def test_computed_dimensions():
    quilt = small_quilt()
    # width: 3 cells x 8 + border 4 on both sides = 24 + 8 = 32 eighths (4")
    assert quilt.finished_width == 32
    # height: 2 cells x 8 + 8 = 16 + 8 = 24 eighths (3")
    assert quilt.finished_height == 24
    # perimeter: 2 x (32 + 24) = 112; binding adds the 80-eighth (10") extra
    assert quilt.perimeter == 112
    assert quilt.binding_length == 192
