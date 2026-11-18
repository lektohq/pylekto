"""Fixtures: a LektoClient whose requests the test answers, and values made up for it."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx2
import pytest
from pydantic import BaseModel, TypeAdapter

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
    data: dict[str, str]
    status: int
    body: Any

    def segment(self, index: int) -> str:
        """Return a segment of the path: 1 is the first after ``/``."""
        return self.path.split("/")[index]


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
        data=recorded.get("data", {}),
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
    when: dict[str, str] = field(default_factory=dict)


class Api:
    """Answers each request by method and path below ``/api/v1``; remembers every request."""

    def __init__(self) -> None:
        """Start without answers."""
        self.answers: dict[tuple[str, str], list[Answer]] = {}
        self.requests: list[httpx2.Request] = []

    def answer(self, method: str, path: str, status: int = 200, **answer: Any) -> None:
        """Answer ``method`` on ``path`` (below ``/api/v1``) with ``status`` and ``answer``.

        ``when`` restricts the answer to requests with these query values; the answer added
        last that fits is given.
        """
        self.answers.setdefault((method, "/api/v1" + path), []).append(Answer(status, **answer))

    def replay(self, name: str) -> Snapshot:
        """Answer the request of the recording ``name`` as Lekto did; return the recording."""
        recorded = snapshot(name)
        self.answer(recorded.method, recorded.path, recorded.status, json=recorded.body)
        return recorded

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        """Answer a request as told; an unexpected one fails the test."""
        self.requests.append(request)
        fitting = [
            answer
            for answer in self.answers.get((request.method, request.url.path), [])
            if all(request.url.params.get(key) == value for key, value in answer.when.items())
        ]
        if not fitting:
            pytest.fail(f"unexpected request: {request.method} {request.url}")
        answer = fitting[-1]
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


def assert_sent(api: Api, recorded: Snapshot) -> None:
    """Assert that the last request is the one of the recording: method, path, query, body."""
    request = api.requests[-1]
    assert request.method == recorded.method
    assert request.url.path == "/api/v1" + recorded.path
    sent = {key: request.url.params.get_list(key) for key in request.url.params}
    expected = {
        key: [str(item) for item in value] if isinstance(value, list) else [str(value)]
        for key, value in recorded.params.items()
    }
    assert sent == expected
    if recorded.json is not None:
        assert json.loads(request.content) == recorded.json


def plain(answer: object) -> object:
    """Return an answer as JSON values, to compare it with the recorded body."""
    if isinstance(answer, BaseModel):
        return answer.model_dump(mode="json", by_alias=True)
    return TypeAdapter(type(answer)).dump_python(answer, mode="json")


def expected(answer: object, body: object) -> object:
    """Return the recorded body read the way the answer was, as JSON values."""
    if isinstance(answer, BaseModel):
        return plain(type(answer).model_validate(body))
    if isinstance(answer, list) and answer and isinstance(answer[0], BaseModel):
        model = type(answer[0])
        assert isinstance(body, list)
        return [plain(model.model_validate(item)) for item in body]
    return body
