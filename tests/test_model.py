"""Schema, serialization, and validation tests for the quilt model."""

import json
import typing

import pytest
from pydantic import BaseModel, ValidationError

from qrep.model import (
    STAGES,
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
from qrep.model.fixtures import make_double_irish_chain
from qrep.model.schema import ConfirmedBlocks, FinishedSizeBasis


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


def dic_blocks(**overrides) -> ConfirmedBlocks:
    # Source: qrep/model/fixtures.py, docstring and defaults: 9 x 11 blocks of
    # 5 x 5 squares. They tile the fixture's grid: 9 x 5 = 45 columns and
    # 11 x 5 = 55 rows.
    counts = {"blocks_across": 9, "blocks_down": 11, "squares_across": 5, "squares_down": 5}
    return ConfirmedBlocks(**{**counts, **overrides})


def dic_typed_basis(**overrides) -> FinishedSizeBasis:
    # Source: plan ticket A10, the DIC typed at 75 x 90 in with 1 1/2 in squares.
    # Requested: 75 x 8 = 600 and 90 x 8 = 720 eighths.
    # Achieved: 45 x 12 + 2 x 30 = 540 + 60 = 600 and 55 x 12 + 2 x 30 = 660 + 60 = 720.
    # Rounding step: 1/4 in = 2 eighths.
    values = {
        "source": "typed",
        "requested_width": 600,
        "requested_height": 720,
        "achieved_width": 600,
        "achieved_height": 720,
        "rounding_step": 2,
    }
    return FinishedSizeBasis(**{**values, **overrides})


def default_basis(**overrides) -> FinishedSizeBasis:
    # A default size sets nothing, so it records no requested size; the achieved
    # size is the DIC's 600 x 720 eighths (see dic_typed_basis).
    values = {
        "source": "default",
        "achieved_width": 600,
        "achieved_height": 720,
        "rounding_step": 2,
    }
    return FinishedSizeBasis(**{**values, **overrides})


def test_confirmed_blocks_and_size_basis_round_trip():
    quilt = make_double_irish_chain().model_copy(
        update={"confirmed_blocks": dic_blocks(), "size_basis": dic_typed_basis()}
    )
    text = dumps(quilt)
    again = loads(text)
    assert again == quilt
    assert again.confirmed_blocks == dic_blocks()
    assert again.size_basis == dic_typed_basis()
    data = json.loads(text)
    # Both user facts are written at confidence 1.0 (docs/SPEC.md section 8).
    assert data["confirmed_blocks"]["confidence"] == 1.0
    assert data["size_basis"]["confidence"] == 1.0
    assert data["size_basis"]["requested_width"] == 600
    assert data["size_basis"]["rounding_step"] == 2


def test_new_fields_default_to_none_and_serialize_last():
    data = json.loads(dumps(small_quilt()))
    # Appending the two keys keeps every older key in its place, so a
    # regenerated fixture gains two lines of null and changes nothing else.
    assert list(data)[-2:] == ["confirmed_blocks", "size_basis"]
    assert data["confirmed_blocks"] is None
    assert data["size_basis"] is None


def test_model_written_before_the_optional_fields_loads_unchanged():
    # Criterion S1-2: schema_version stays major 1, and a model that predates
    # the two optional fields loads as it was.
    data = json.loads(dumps(small_quilt()))
    del data["confirmed_blocks"]
    del data["size_basis"]
    assert data["schema_version"] == "1"
    loaded = loads(json.dumps(data))
    assert loaded == small_quilt()
    assert loaded.schema_version == "1"
    assert loaded.confirmed_blocks is None
    assert loaded.size_basis is None
    rewritten = json.loads(dumps(loaded))
    new_keys = ("confirmed_blocks", "size_basis")
    assert {k: v for k, v in rewritten.items() if k not in new_keys} == data


@pytest.mark.parametrize(
    "field", ["blocks_across", "blocks_down", "squares_across", "squares_down"]
)
def test_confirmed_blocks_refuse_a_count_below_one(field):
    with pytest.raises(ValidationError, match=field):
        dic_blocks(**{field: 0})


def test_size_basis_accepts_each_source_with_its_requested_sizes():
    # A typed size may give one axis and let the other follow.
    assert dic_typed_basis(requested_height=None).requested_width == 600
    # A preset has both dimensions (qrep/viewer/sizing.py PRESETS).
    assert dic_typed_basis(source="preset").requested_height == 720
    basis = default_basis()
    assert basis.requested_width is None and basis.requested_height is None


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"requested_width": None, "requested_height": None}, "typed size needs"),
        ({"source": "preset", "requested_height": None}, "preset size records both"),
        ({"source": "default"}, "default size records no requested"),
        ({"source": "default", "requested_width": None}, "default size records no requested"),
        ({"source": "guessed"}, "source"),
        ({"rounding_step": 0}, "rounding_step"),
        ({"achieved_width": 0}, "achieved_width"),
        ({"requested_height": 0}, "requested_height"),
    ],
)
def test_size_basis_refuses_a_source_its_sizes_contradict(overrides, message):
    with pytest.raises(ValidationError, match=message):
        dic_typed_basis(**overrides)


# Where each stored value comes from (docs/SPEC.md section 8). A CV value names
# the carrier of its confidence; a user value lives in a model that records it
# at 1.0. The other kinds carry no confidence of their own: settings and
# authored values are set by hand, derived values follow deterministically from
# the read or other fields, format values describe the file, and confidence
# fields are the carriers. B8 and B2a add their fields here.
FIELD_SOURCES = {
    "Quilt.schema_version": "format",
    "QuiltMetadata.name": "derived",
    "QuiltMetadata.notes": "derived",
    "Fabric.id": "derived",
    "Fabric.name": "derived",
    "Fabric.color": "cv:stage:palette",
    "GridRegion.kind": "format",
    "GridRegion.rows": "cv:stage:grid",
    "GridRegion.cols": "cv:stage:grid",
    # A read scales squares and borders to inches by an assumed photo
    # resolution (qrep/vision/pipeline.py ASSUMED_PPI), so their physical size
    # is the photo's size estimate until the user sets a size (engine-09); the
    # size basis carries that estimate.
    "GridRegion.cell_size": "cv:size_estimate",
    "GridRegion.cells": "cv:cell",
    "GridRegion.cell_confidence": "confidence",
    "BorderBand.fabric_id": "cv:stage:border",
    "BorderBand.width": "cv:size_estimate",
    # The read binds in the border fabric it found (qrep/vision/pipeline.py).
    "Binding.fabric_id": "cv:stage:border",
    "Binding.strip_width": "setting",
    "QuiltingMotif.name": "authored",
    "QuiltingMotif.x": "authored",
    "QuiltingMotif.y": "authored",
    "QuiltingMotif.width": "authored",
    "QuiltingMotif.height": "authored",
    "QuiltingLayer.density": "authored",
    "Settings.seam_allowance": "setting",
    "Settings.wof": "setting",
    "Settings.binding_strip_width": "setting",
    "Settings.binding_extra": "setting",
    "Settings.backing_margin": "setting",
    "Settings.backing_width": "setting",
    "Settings.wide_back_width": "setting",
    "Settings.backing_pieced_allowance": "setting",
    "Settings.backing_one_piece_allowance": "setting",
    "Settings.purchase_increment": "setting",
    "Settings.top_margin": "setting",
    "Provenance.source": "format",
    "Provenance.stage_confidence": "confidence",
    "ConfirmedBlocks.blocks_across": "user",
    "ConfirmedBlocks.blocks_down": "user",
    "ConfirmedBlocks.squares_across": "user",
    "ConfirmedBlocks.squares_down": "user",
    "ConfirmedBlocks.confidence": "confidence",
    "FinishedSizeBasis.source": "user",
    "FinishedSizeBasis.requested_width": "user",
    "FinishedSizeBasis.requested_height": "user",
    # Its confidence is 1.0 once the user sets a size (typed or preset).
    "FinishedSizeBasis.achieved_width": "cv:size_estimate",
    "FinishedSizeBasis.achieved_height": "cv:size_estimate",
    "FinishedSizeBasis.rounding_step": "setting",
    "FinishedSizeBasis.confidence": "confidence",
}

KINDS = {"user", "derived", "authored", "setting", "format", "confidence"}

# Each CV carrier, built with one confidence value; a refused value raises.
CV_CARRIERS = {
    **{
        f"stage:{stage}": (lambda v, stage=stage: Provenance(stage_confidence={stage: v}))
        for stage in STAGES
    },
    "cell": lambda v: GridRegion(rows=1, cols=1, cell_size=8, cells=[["r"]], cell_confidence=[[v]]),
    # A default size estimated from a photo carries the estimate's confidence.
    "size_estimate": lambda v: default_basis(confidence=v),
}

# Each model that holds user facts, built from user values with one confidence.
USER_FACT_MODELS = {
    "ConfirmedBlocks": [lambda v: dic_blocks(confidence=v)],
    "FinishedSizeBasis": [
        lambda v: dic_typed_basis(confidence=v),
        lambda v: dic_typed_basis(source="preset", confidence=v),
    ],
}

CARRIER_FIELDS = {"GridRegion.cell_confidence", "Provenance.stage_confidence"}


def _models_in(annotation) -> list[type[BaseModel]]:
    """Every pydantic model inside an annotation such as list[X] or X | None."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    return [model for arg in typing.get_args(annotation) for model in _models_in(arg)]


def _leaf_fields(model: type[BaseModel]) -> set[str]:
    """Model.field for every stored value reachable from model, nested models walked."""
    leaves: set[str] = set()
    for name, field in model.model_fields.items():
        nested = _models_in(field.annotation)
        if nested:
            for sub in nested:
                leaves |= _leaf_fields(sub)
        else:
            leaves.add(f"{model.__name__}.{name}")
    return leaves


def test_schema_walk_classifies_every_stored_value():
    # Criterion S7-6: a new field fails here until its source is recorded.
    leaves = _leaf_fields(Quilt)
    assert sorted(leaves - set(FIELD_SOURCES)) == [], "fields with no recorded source"
    assert sorted(set(FIELD_SOURCES) - leaves) == [], "recorded sources with no field"
    for path, source in FIELD_SOURCES.items():
        if source.startswith("cv:"):
            assert source[3:] in CV_CARRIERS, f"{path}: unknown confidence carrier {source}"
        else:
            assert source in KINDS, f"{path}: unknown source {source}"
    # Only the carriers are labeled confidence, so a CV value cannot hide there.
    labeled = {path for path, source in FIELD_SOURCES.items() if source == "confidence"}
    user_models = {path.split(".")[0] for path, source in FIELD_SOURCES.items() if source == "user"}
    assert labeled == CARRIER_FIELDS | {f"{model}.confidence" for model in user_models}


@pytest.mark.parametrize(
    "carrier",
    sorted({source[3:] for source in FIELD_SOURCES.values() if source.startswith("cv:")}),
)
def test_every_cv_value_has_a_confidence_in_the_unit_interval(carrier):
    build = CV_CARRIERS[carrier]
    for inside in (0.0, 0.5, 1.0):
        build(inside)
    for outside in (-0.125, 1.125):
        with pytest.raises(ValidationError):
            build(outside)


@pytest.mark.parametrize(
    "model", sorted({path.split(".")[0] for path, s in FIELD_SOURCES.items() if s == "user"})
)
def test_every_user_fact_is_recorded_at_confidence_one(model):
    builds = USER_FACT_MODELS[model]
    assert builds, model
    for build in builds:
        assert build(1.0).confidence == 1.0
        # In range but below 1.0, only the user-fact rule can refuse it.
        for other in (0.0, 0.875):
            with pytest.raises(ValidationError, match="user fact at confidence 1.0"):
                build(other)
        with pytest.raises(ValidationError, match="confidence"):
            build(1.125)
    # Left out, the confidence defaults to 1.0.
    defaults = {"ConfirmedBlocks": dic_blocks, "FinishedSizeBasis": dic_typed_basis}
    assert defaults[model]().confidence == 1.0


def test_default_size_estimate_keeps_its_confidence():
    # docs/SPEC.md section 8: a size estimated from the photo is a low-confidence
    # guess, so a default basis keeps the confidence it was given.
    assert default_basis(confidence=0.25).confidence == 0.25
    assert default_basis().confidence == 1.0
