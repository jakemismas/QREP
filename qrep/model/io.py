"""Load and save quilt JSON.

schema_version is checked before pydantic validation so a wrong-version file
fails with a clear QrepSchemaError instead of a wall of field errors.
"""

import json
from pathlib import Path

from qrep.model.schema import Quilt, QrepSchemaError


def loads(text: str) -> Quilt:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise QrepSchemaError(f"not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise QrepSchemaError("quilt JSON must be an object at the top level")
    if "schema_version" not in data:
        raise QrepSchemaError('quilt JSON is missing "schema_version"; expected "1"')
    version = data["schema_version"]
    if str(version).split(".")[0] != "1":
        raise QrepSchemaError(
            f'unsupported schema_version {version!r}; this build of qrep reads major version "1"'
        )
    return Quilt.model_validate(data)


def dumps(quilt: Quilt) -> str:
    """Deterministic serialization: field order fixed by the schema, LF, indent 2."""
    return quilt.model_dump_json(indent=2) + "\n"


def load(path: str | Path) -> Quilt:
    return loads(Path(path).read_text(encoding="utf-8"))


def save(quilt: Quilt, path: str | Path) -> None:
    Path(path).write_text(dumps(quilt), encoding="utf-8", newline="\n")
