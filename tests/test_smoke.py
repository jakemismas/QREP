"""Import smoke test: every qrep subpackage and each binary-wheel dependency imports."""

import importlib

import pytest

MODULES = [
    "qrep",
    "qrep.model",
    "qrep.construct",
    "qrep.export",
    "qrep.render",
    "qrep.vision",
    "qrep.viewer",
    "qrep.cli",
    "cv2",
    "reportlab",
    "svgwrite",
]


@pytest.mark.parametrize("module", MODULES)
def test_imports(module):
    importlib.import_module(module)
