"""Fetch the OpenAPI description of a Lekto release and generate the models from it.

    uv run python script/update_openapi.py v0.15.6

Writes ``openapi.json`` (with the release's version), ``src/pylekto/_lekto.py`` and, through
datamodel-codegen with the settings in ``pyproject.toml``, ``src/pylekto/models.py``.
"""

import json
import os
import sys
from pathlib import Path

import httpx2
from datamodel_code_generator.__main__ import Exit, main

ROOT = Path(__file__).resolve().parent.parent
SOURCE = "https://raw.githubusercontent.com/lektohq/lekto/{tag}/web/openapi.json"
LEKTO_MODULE = (
    '"""The Lekto release whose API pylekto speaks; script/update_openapi.py writes this file."""\n'
    "\n"
    'LEKTO_VERSION = "{version}"\n'
)


def update(tag: str) -> None:
    """Fetch the description of the release ``tag`` and write the files from it."""
    response = httpx2.get(SOURCE.format(tag=tag), follow_redirects=True, timeout=30.0)
    response.raise_for_status()
    description = response.json()
    version = tag.removeprefix("v")
    # The file of a release carries the version of the repository (0.0.0.dev0), not its own.
    description["info"]["version"] = version
    (ROOT / "openapi.json").write_text(
        json.dumps(description, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (ROOT / "src/pylekto/_lekto.py").write_text(
        LEKTO_MODULE.format(version=version), encoding="utf-8"
    )
    # datamodel-codegen reads its settings from the pyproject.toml of the working directory.
    os.chdir(ROOT)
    if main([]) != Exit.OK:
        message = "datamodel-codegen failed"
        raise SystemExit(message)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    update(sys.argv[1])
