"""Golden-file protocol: `pytest --bless` writes tests/golden/, plain runs
byte-compare against it. A missing golden without --bless fails the test."""

from pathlib import Path

import pytest

GOLDEN_DIR = Path(__file__).parent / "golden"


def pytest_addoption(parser):
    parser.addoption(
        "--bless",
        action="store_true",
        default=False,
        help="write current output to tests/golden/ instead of comparing",
    )


@pytest.fixture
def bless_mode(request) -> bool:
    return request.config.getoption("--bless")


@pytest.fixture
def golden(request):
    def check(name: str, content: str) -> None:
        path = GOLDEN_DIR / name
        if request.config.getoption("--bless"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode("utf-8"))
            return
        if not path.exists():
            pytest.fail(f"golden file {name} is missing: run --bless to create it")
        assert content.encode("utf-8") == path.read_bytes(), (
            f"{name} differs from the blessed golden; a diff here is a bug in "
            "the exporter until proven otherwise"
        )

    return check
