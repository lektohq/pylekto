"""Fixtures: a LektoClient whose requests the test answers, and values made up for it."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx2
import pytest

from pylekto import LEKTO_VERSION, LektoClient

SNAPSHOT = Path(__file__).resolve().parent / "snapshot"
URL = "https://lekto.example.com"
TOKEN = "lekto_0123456789abcdef"
USER_ID = "0199a3c4-0000-7000-8000-000000000001"
DOCUMENT_ID = "0199a3c4-0000-7000-8000-000000000002"


def me(**changes: Any) -> dict[str, Any]:
    """Return the answer of ``GET /auth/me`` for Jane Doe with a read token, with ``changes``."""
    return {
        "user": {"id": USER_ID, "username": "jane", "display_name": "Jane Doe", "role": "user"},
        "authenticated_with": "token",
        "csrf_token": None,
        "session_expires_at": None,
        "token_scope": "read",
        "has_password": True,
        "totp_enabled": False,
        "linked_accounts": [],
        "lekto_version": LEKTO_VERSION,
        "shortcut_url": None,
    } | changes


@dataclass(frozen=True)
class Snapshot:
    """A request to Lekto and its answer, recorded by ``script/record_snapshot.py``."""

    name: str
    method: str
    operation: str
    path: str
    params: dict[str, Any]
    json: Any
    status: int
    body: Any


def snapshot(name: str) -> Snapshot:
    """Read the recording ``tests/snapshot/<name>.json``."""
    recorded = json.loads((SNAPSHOT / f"{name}.json").read_text(encoding="utf-8"))
    return Snapshot(
        name=name,
        method=recorded["method"],
        operation=recorded["operation"],
        path=recorded["path"],
        params=recorded["params"],
        json=recorded["json"],
        status=recorded["status"],
        body=recorded["body"],
    )


@dataclass
class Answer:
    """How the fake API answers one method and path."""

    status: int = 200
    json: Any = None
    content: bytes | None = None
    headers: dict[str, str] = field(default_factory=dict)
    error: Exception | None = None


class Api:
    """Answers each request by method and path below ``/api/v1``; remembers every request."""

    def __init__(self) -> None:
        """Start without answers."""
        self.answers: dict[tuple[str, str], Answer] = {}
        self.requests: list[httpx2.Request] = []

    def answer(self, method: str, path: str, status: int = 200, **answer: Any) -> None:
        """Answer ``method`` on ``path`` (below ``/api/v1``) with ``status`` and ``answer``."""
        self.answers[method, "/api/v1" + path] = Answer(status, **answer)

    def replay(self, name: str) -> Snapshot:
        """Answer the request of the recording ``name`` as Lekto did; return the recording."""
        recorded = snapshot(name)
        self.answer(recorded.method, recorded.path, recorded.status, json=recorded.body)
        return recorded

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        """Answer a request as told; an unexpected one fails the test."""
        self.requests.append(request)
        answer = self.answers.get((request.method, request.url.path))
        if answer is None:
            pytest.fail(f"unexpected request: {request.method} {request.url}")
        if answer.error is not None:
            raise answer.error
        return httpx2.Response(
            answer.status, json=answer.json, content=answer.content, headers=answer.headers
        )


@pytest.fixture
def api() -> Api:
    """Return the fake API of the test."""
    return Api()


@pytest.fixture
def http(api: Api) -> httpx2.AsyncClient:
    """Return an httpx2 client that sends every request to the fake API."""
    return httpx2.AsyncClient(transport=httpx2.MockTransport(api))


@pytest.fixture
def lekto(http: httpx2.AsyncClient) -> LektoClient:
    """Return a LektoClient on the fake API, not connected."""
    return LektoClient(URL, TOKEN, client=http)
