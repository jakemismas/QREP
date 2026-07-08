"""Formatter tests. Expected strings are hand-computed from the eighths value."""

import pytest

from qrep.model.units import format_inches


@pytest.mark.parametrize(
    ("eighths", "expected"),
    [
        # 12 eighths = 1 whole (8) + 4/8 = 1 1/2"
        (12, '1 1/2"'),
        # 30 eighths = 3 wholes (24) + 6/8 = 3 3/4"
        (30, '3 3/4"'),
        # 2 eighths = 2/8 = 1/4"
        (2, '1/4"'),
        # 20 eighths = 2 wholes + 4/8 = 2 1/2"
        (20, '2 1/2"'),
        # 600 eighths = exactly 75 inches
        (600, '75"'),
        # 720 eighths = exactly 90 inches
        (720, '90"'),
        # 1 eighth stays 1/8
        (1, '1/8"'),
        # 0 renders as 0"
        (0, '0"'),
        # negative carries the sign through: -30 = -(3 3/4)
        (-30, '-3 3/4"'),
    ],
)
def test_format_inches(eighths, expected):
    assert format_inches(eighths) == expected
