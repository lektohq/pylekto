"""Fetch the OpenAPI description of a Lekto release and generate the models from it.

    uv run python script/update_openapi.py v0.16.0

Writes ``openapi.json`` (with the release's version as ``info.x-lekto-version``; ``info.version``
is the version of the API), ``src/pylekto/_lekto.py`` and, through ``generate_models.py``,
``src/pylekto/models.py``.
"""

import json
import sys
from pathlib import Path

import httpx2

from generate_models import generate

ROOT = Path(__file__).resolve().parent.parent
SOURCE = "https://raw.githubusercontent.com/lektohq/lekto/{tag}/web/openapi.json"
LEKTO_MODULE = (
    '"""The Lekto release whose API pylekto speaks, and the version of that API.\n'
    "\n"
    "script/update_openapi.py writes this file.\n"
    '"""\n'
    "\n"
    'LEKTO_VERSION = "{version}"\n'
    'API_VERSION = "{api_version}"\n'
)


def update(tag: str) -> None:
    """Fetch the description of the release ``tag`` and write the files from it."""
    response = httpx2.get(SOURCE.format(tag=tag), follow_redirects=True, timeout=30.0)
    response.raise_for_status()
    description = response.json()
    version = tag.removeprefix("v")
    # The file of a release carries the version of the repository (0.0.0.dev0), not its own.
    description["info"]["x-lekto-version"] = version
    (ROOT / "openapi.json").write_text(
        json.dumps(description, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (ROOT / "src/pylekto/_lekto.py").write_text(
        LEKTO_MODULE.format(version=version, api_version=description["info"]["version"]),
        encoding="utf-8",
    )
    if not generate():
        message = "datamodel-codegen failed"
        raise SystemExit(message)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    update(sys.argv[1])
