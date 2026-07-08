"""Emit the self-contained sizing viewer HTML with the model embedded."""

import json
from pathlib import Path

from qrep.model.io import dumps
from qrep.model.schema import Quilt
from qrep.model.units import format_inches
from qrep.viewer.sizing import build_view_config

TEMPLATE_PATH = Path(__file__).parent / "template.html"


def _embed_json(data_json: str) -> str:
    # "</" inside a script block would end it early; JSON allows the escape.
    return data_json.replace("</", "<\\/")


def _border_inputs_html(quilt: Quilt) -> str:
    names = {f.id: f.name for f in quilt.palette.fabrics}
    parts = []
    for i, band in enumerate(quilt.borders):
        # values use the one shared Python formatter, minus the inch mark
        value = format_inches(band.width)[:-1]
        parts.append(
            f'<label class="control-label">Border {i + 1} ({names[band.fabric_id]})'
            f'<input type="text" id="border-width-{i}" class="border-width-input" '
            f'value="{value}"></label>'
        )
    return "\n".join(parts)


def emit_viewer(quilt: Quilt) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    model_json = _embed_json(dumps(quilt).strip())
    config_json = _embed_json(json.dumps(build_view_config(quilt), indent=2))
    html = template.replace("__QREP_TITLE__", quilt.metadata.name)
    html = html.replace("/*__QREP_MODEL__*/ null", model_json)
    html = html.replace("/*__QREP_CONFIG__*/ null", config_json)
    html = html.replace("__QREP_BORDER_INPUTS__", _border_inputs_html(quilt))
    return html


def write_viewer(quilt: Quilt, path: str | Path) -> Path:
    path = Path(path)
    path.write_text(emit_viewer(quilt), encoding="utf-8", newline="\n")
    return path
