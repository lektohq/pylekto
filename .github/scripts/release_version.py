"""The version of pylekto's next release: the API it speaks and one more release for that API.

pylekto X.Y.Z speaks Lekto's API X.Y (`API_VERSION` of `src/pylekto/_lekto.py`); Z is one past
the highest tag vX.Y.*, so numbers PyPI already holds (0.3.0, 0.4.0) are skipped
(.knowledge/decisions/2026-11-21-pylekto-version.md).

    git tag --list 'v*' | python3 .github/scripts/release_version.py   # 0.3.1
    python3 .github/scripts/release_version.py --check v0.3.1          # fails for another API
"""

import re
import sys
from collections.abc import Iterable
from pathlib import Path

LEKTO = Path(__file__).resolve().parents[2] / "src" / "pylekto" / "_lekto.py"
API_VERSION = re.compile(r'^API_VERSION = "([0-9]+\.[0-9]+)"$', re.MULTILINE)
TAG = re.compile(r"v([0-9]+\.[0-9]+)\.([0-9]+)")


def api_version(source: str) -> str:
    """Read the version of the API from the text of `_lekto.py`."""
    match = API_VERSION.search(source)
    if match is None:
        msg = "_lekto.py names no API_VERSION"
        raise ValueError(msg)
    return match.group(1)


def next_version(api: str, tags: Iterable[str]) -> str:
    """Count one past the highest tag of `api`, or start at its first release."""
    releases = [
        int(match.group(2))
        for tag in tags
        if (match := TAG.fullmatch(tag)) is not None and match.group(1) == api
    ]
    return f"{api}.{max(releases) + 1 if releases else 0}"


def fits(api: str, tag: str) -> bool:
    """Tell whether a release tag names a version of pylekto for `api`."""
    match = TAG.fullmatch(tag)
    return match is not None and match.group(1) == api


def main(arguments: list[str]) -> int:
    """Print the next version from the tags on stdin, or check a tag; return the exit code."""
    api = api_version(LEKTO.read_text(encoding="utf-8"))
    match arguments:
        case []:
            print(next_version(api, sys.stdin.read().split()))
            return 0
        case ["--check", tag] if fits(api, tag):
            return 0
        case ["--check", tag]:
            print(
                f"The tag {tag} names no version for the API {api} of src/pylekto/_lekto.py; "
                f"tag the release v{api}.<release>.",
                file=sys.stderr,
            )
            return 1
        case _:
            print(__doc__, file=sys.stderr)
            return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
