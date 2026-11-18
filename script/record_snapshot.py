r"""Record the answers of a Lekto instance as the snapshot the tests replay.

    uv run python script/record_snapshot.py --url http://127.0.0.1:18000 [NAME ...]

The token comes from the environment variable ``PYLEKTO_SNAPSHOT_TOKEN``: an admin's API token
with the scope ``read_write``. Without names, every recording is made again.

Never point it at an instance with real documents: the snapshot is public. Use a throwaway Lekto
of the release ``LEKTO_VERSION`` names, filled with the synthetic documents of Lekto's
repository::

    docker run -d --name lekto-snapshot -p 127.0.0.1:18000:8000 \\
      -e LEKTO_SECRET_KEY=... -e LEKTO_ADMIN_USERNAME=admin -e LEKTO_ADMIN_PASSWORD=... \\
      -e LEKTO_COOKIE_SECURE=false ghcr.io/lektohq/lekto:0.15.5
    # an API token: sign in at http://127.0.0.1:18000/ui, Settings, API tokens (read_write)
    python <lekto>/examples/mcp-eval/seed.py --url http://127.0.0.1:18000 --token ... \\
      --documents 40
    # wait until the inbox shows nothing in processing

Each recording becomes ``tests/snapshot/<name>.json``: the request (method, path, query, body)
and the answer (status, body). The address of the instance is replaced by the one the tests use.
Some recordings change the instance (they create, change or delete): run them on a throwaway one.
"""

import argparse
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx2

from pylekto import LEKTO_VERSION

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "tests" / "snapshot"
TESTS_URL = "https://lekto.example.com"

type Lookup = Callable[["Recorder"], str]


@dataclass
class Recording:
    """One request to record; ``{name}`` in the path is filled by the lookup of that name.

    ``path`` is the path of the operation in the OpenAPI description below ``/api/v1``, with the
    placeholders of the lookups in place of its parameters.
    """

    name: str
    method: str
    path: str
    operation: str
    params: dict[str, Any] = field(default_factory=dict)
    json: Any = None


class Recorder:
    """Sends the recordings to an instance and writes their answers."""

    def __init__(self, url: str, token: str) -> None:
        """Connect to the instance with the token."""
        self.url = url.rstrip("/")
        self.client = httpx2.Client(
            base_url=self.url + "/api/v1",
            headers={"Authorization": f"Bearer {token}"},
            timeout=60.0,
        )
        self.found: dict[str, str] = {}

    def get(self, path: str, **params: Any) -> Any:
        """GET a JSON answer for a lookup; an error stops the recording."""
        response = self.client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    def value(self, name: str) -> str:
        """Return the value of a placeholder, looked up once."""
        if name not in self.found:
            self.found[name] = LOOKUPS[name](self)
        return self.found[name]

    def record(self, recording: Recording) -> int:
        """Send one recording and write its file; return the status."""
        path = recording.path.format_map(_Values(self))
        response = self.client.request(
            recording.method, path, params=recording.params, json=recording.json
        )
        body = response.json() if response.content else None
        snapshot = {
            "lekto_version": LEKTO_VERSION,
            "method": recording.method,
            "operation": recording.operation,
            "path": path,
            "params": recording.params,
            "json": recording.json,
            "status": response.status_code,
            "body": body,
        }
        text = json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n"
        (SNAPSHOT / f"{recording.name}.json").write_text(
            text.replace(self.url, TESTS_URL), encoding="utf-8"
        )
        return response.status_code


class _Values(dict[str, str]):
    """The placeholders of a path, each looked up when it is used."""

    def __init__(self, recorder: Recorder) -> None:
        super().__init__()
        self.recorder = recorder

    def __missing__(self, key: str) -> str:
        return self.recorder.value(key)


LOOKUPS: dict[str, Lookup] = {}

RECORDINGS: list[Recording] = [
    Recording("auth_me", "GET", "/auth/me", "/auth/me"),
    Recording("health", "GET", "/health", "/health"),
]


def main() -> None:
    """Record the named recordings, or all of them."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", required=True, help="the throwaway Lekto instance")
    parser.add_argument("names", nargs="*", help="the recordings to make (default: all)")
    arguments = parser.parse_args()
    token = os.environ.get("PYLEKTO_SNAPSHOT_TOKEN")
    if not token:
        message = "PYLEKTO_SNAPSHOT_TOKEN is not set"
        raise SystemExit(message)
    recorder = Recorder(arguments.url, token)
    version = recorder.get("/auth/me")["lekto_version"]
    if version != LEKTO_VERSION:
        message = f"the instance runs Lekto {version}, the snapshot is of {LEKTO_VERSION}"
        raise SystemExit(message)
    chosen = [r for r in RECORDINGS if not arguments.names or r.name in arguments.names]
    unknown = set(arguments.names) - {r.name for r in RECORDINGS}
    if unknown:
        message = f"no such recordings: {', '.join(sorted(unknown))}"
        raise SystemExit(message)
    SNAPSHOT.mkdir(parents=True, exist_ok=True)
    for recording in chosen:
        status = recorder.record(recording)
        sys.stdout.write(f"{status} {recording.name}\n")


if __name__ == "__main__":
    main()
