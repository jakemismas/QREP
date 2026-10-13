"""Confidence and provenance of the confirmed read (B2b, criterion S7-6).

Every value the read derives from the photo carries a confidence in [0, 1],
every input you confirmed is recorded at 1.0, and every knob the read turns
is provisional, with its source, until D5 measures it (plan section 5.B).
"""

from qrep.vision.read import knobs


def test_every_knob_is_provisional_with_a_source():
    # Plan B2b: the L weight, P, the inset, the k range and the vote threshold
    # sit in knobs.py with their sources, and this ticket freezes none.
    named = {"L_WEIGHT", "P", "INSET", "K_MIN", "K_MAX", "VOTE_THRESHOLD"}
    assert named <= set(knobs.KNOBS)
    for name, knob in knobs.KNOBS.items():
        assert knob.status == "provisional", name
        assert knob.source.strip(), name
        assert knob.value == getattr(knobs, name, knob.value), name


def test_knob_values_match_their_sources():
    # Source: plan sections 2.1 (L*0.5, Jake's default) and 5.B; B2a's P = 32
    # and inset 0.2 (plan B2a); the 2 to 12 fabric range (SPEC.md section
    # 12.1); REBASELINE.md literal B5 keeps 3 copies; the 3/4 in and 4 in
    # square bounds are literals B8 and B9 (6 and 32 eighths).
    expected = {
        "L_WEIGHT": 0.5,
        "P": 32,
        "INSET": 0.2,
        "K_MIN": 2,
        "K_MAX": 12,
        "VOTE_MIN_COPIES": 3,
        "SQUARE_MIN": 6,
        "SQUARE_MAX": 32,
        "SIZE_STEP": 2,
    }
    assert {name: knobs.KNOBS[name].value for name in expected} == expected
