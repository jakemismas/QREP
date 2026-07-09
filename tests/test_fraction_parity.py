"""Fraction display parity (S2, issue #42).

The web UI reimplements the mixed-fraction formatter in TypeScript
(web/src/model/units.ts). Both sides assert the SAME hand-authored fixture,
tests/fixtures/fraction_display.json, so they cannot drift: this module pins
the Python side, web/src/model/units.test.ts pins the TS side.
"""

import json
from pathlib import Path

import pytest

from qrep.model.units import format_inches

FIXTURE = Path(__file__).parent / "fixtures" / "fraction_display.json"
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: str(c["eighths"]))
def test_format_inches_matches_shared_fixture(case):
    assert format_inches(case["eighths"]) == case["display"]
