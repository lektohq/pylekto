"""Fetch the OpenAPI description of a Lekto release and generate the models from it.

    uv run python script/update_openapi.py v0.16.0
    uv run python script/update_openapi.py main 0.17.4

pylekto is released before the Lekto release whose API it speaks, so the description usually
comes from Lekto's ``main`` (or one of its commits), with the version of the release it will be:
the one its release draft names. A tag of a published release names its version itself.

Writes ``openapi.json`` (with the release's version as ``info.x-lekto-version``; ``info.version``
is the version of the API), ``src/pylekto/_lekto.py`` and, through ``generate_models.py``,
``src/pylekto/models.py``.
"""

import json
import re
import sys
from pathlib import Path

import httpx2

from generate_models import generate

ROOT = Path(__file__).resolve().parent.parent
SOURCE = "https://raw.githubusercontent.com/lektohq/lekto/{ref}/web/openapi.json"
_TAG = re.compile(r"v(?P<version>\d+\.\d+\.\d+)")
LEKTO_MODULE = (
    '"""The Lekto release whose API pylekto speaks, and the version of that API.\n'
    "\n"
    "script/update_openapi.py writes this file.\n"
    '"""\n'
    "\n"
    'LEKTO_VERSION = "{version}"\n'
    'API_VERSION = "{api_version}"\n'
)


def update(ref: str, version: str) -> None:
    """Fetch the description at ``ref`` of Lekto and write the files from it.

    ``ref`` is a tag, a branch or a commit; ``version`` the Lekto release it is or will be.
    """
    response = httpx2.get(SOURCE.format(ref=ref), follow_redirects=True, timeout=30.0)
    response.raise_for_status()
    description = response.json()
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


def version_of(ref: str, version: str | None) -> str:
    """Name the Lekto release of the description at ``ref``.

    ``version`` if given, else the one the tag ``ref`` names.
    """
    if version is not None:
        return version
    tag = _TAG.fullmatch(ref)
    if tag is None:
        message = f"{ref} is no release tag: name the version of the release it will be"
        raise SystemExit(message)
    return tag["version"]


if __name__ == "__main__":
    if len(sys.argv) not in {2, 3}:
        raise SystemExit(__doc__)
    ref = sys.argv[1]
    update(ref, version_of(ref, sys.argv[2] if len(sys.argv) == 3 else None))
