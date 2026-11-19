"""Generate the models from Lekto's OpenAPI description, with every choice open to new values.

    uv run python script/generate_models.py [--check]

datamodel-codegen writes ``src/pylekto/models.py`` from ``openapi.json`` with the settings in
``pyproject.toml``. Before, every enum of strings in a copy of the description also admits
:class:`pylekto.Unknown` (``Literal[...] | Unknown``): a newer Lekto may send a value this
pylekto does not know (.knowledge/open/pylekto-tolerant-enums-fas.md). ``--check`` changes
nothing and fails if ``models.py`` differs.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

from datamodel_code_generator.__main__ import Exit, main

ROOT = Path(__file__).resolve().parent.parent
# models.py imports it from where it does not import models.py back.
UNKNOWN = {"type": "string", "x-python-type": "pylekto._unknown.Unknown"}
# Values, not schemas: an example may hold a JSON Schema of its own (a task's answer_schema).
EXAMPLES = {"example", "examples"}


def opened(node: object) -> object:
    """Return a part of the description with every enum of strings in it open to new values."""
    if isinstance(node, list):
        return [opened(item) for item in node]
    if not isinstance(node, dict):
        return node
    if node.get("type") == "string" and "enum" in node:
        rest = {key: value for key, value in node.items() if key not in {"type", "enum"}}
        return {**rest, "anyOf": [{"type": "string", "enum": node["enum"]}, UNKNOWN]}
    return {key: _keyword(key, value) for key, value in node.items()}


def _keyword(key: str, value: object) -> object:
    """Open the schemas below a keyword; property names (``examples`` is one) are no keywords."""
    if key == "properties" and isinstance(value, dict):
        return {name: opened(schema) for name, schema in value.items()}
    return value if key in EXAMPLES else opened(value)


def generate(*, check: bool = False) -> bool:
    """Write ``models.py`` (or with ``check`` compare it); return whether that succeeded."""
    description = json.loads((ROOT / "openapi.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "openapi.json"
        source.write_text(json.dumps(opened(description)), encoding="utf-8")
        # datamodel-codegen reads its settings from the pyproject.toml of the working directory.
        os.chdir(ROOT)
        return main(["--input", str(source), *(["--check"] if check else [])]) == Exit.OK


if __name__ == "__main__":
    sys.exit(0 if generate(check="--check" in sys.argv[1:]) else 1)
