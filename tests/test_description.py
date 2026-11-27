"""Tests that pylekto reaches every operation of the OpenAPI description a token may use."""

import ast
import json
import re
from pathlib import Path

from .conftest import API, DESCRIPTION, ROOT, SNAPSHOT

PATHS = DESCRIPTION["paths"]
METHODS = {"get", "post", "put", "patch", "delete"}
CREDENTIALS = {"token", "taskToken", "fileSignature"}

type Operation = tuple[str, str]

# pylekto signs in with nothing but an API token.
SIGN_IN: set[Operation] = {
    ("POST", "/auth/login"),
    ("GET", "/auth/oidc"),
    ("GET", "/auth/oidc/login"),
    ("GET", "/auth/oidc/callback"),
}

# Lekto names the address of these in a webhook's request; pylekto.webhooks sends them there.
BY_URL: set[Operation] = {
    ("POST", "/external/tasks/{}/result"),
    ("GET", "/external/tasks/{}/files/{}"),
}

# No recording holds these; their tests answer with made-up values.
UNRECORDED: dict[Operation, str] = {
    ("GET", "/contacts/{}/logo"): "the instance fetches no logos",
    ("GET", "/documents/{}/archive"): "a file",
    ("GET", "/documents/{}/original"): "a file",
    ("GET", "/documents/{}/pages/{}"): "a file",
    ("GET", "/documents/{}/preview"): "a file",
    ("GET", "/documents/{}/versions/{}/original"): "a file",
    ("POST", "/push/devices/{}/test"): "the notification would go to the push service",
    ("POST", "/external/tasks/{}/result"): "the recording answers tasks without pylekto",
    ("GET", "/external/tasks/{}/files/{}"): "a file",
}

# What the client's HTTP layer offers; these send GET, the others take the method first.
_GETS = {"get", "download", "lines"}
_SENDS = {"call", "call_as", "call_empty", "request"}


def template(path: str) -> str:
    """Return a path below ``/api/v1`` with every parameter written as ``{}``."""
    return re.sub(r"\{[^}]*\}", "{}", path.removeprefix(API))


def description() -> set[Operation]:
    """Return the operations a token, a task's token or a file's signature reaches."""
    found: set[Operation] = set()
    for path, item in PATHS.items():
        for method, operation in item.items():
            if method not in METHODS:
                continue
            schemes = {name for need in operation.get("security", []) for name in need}
            key = (method.upper(), template(path))
            if schemes & CREDENTIALS or (not schemes and key not in SIGN_IN):
                found.add(key)
    return found


def _path(node: ast.expr) -> str:
    """Return a path as the code writes it, with ``{}`` for each value put in.

    A path with values is a template string, whose values the HTTP layer encodes; an f-string
    would put them in as they are.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    assert isinstance(node, ast.TemplateStr), ast.unparse(node)
    return "".join(
        part.value if isinstance(part, ast.Constant) and isinstance(part.value, str) else "{}"
        for part in node.values
    )


def resources() -> set[Operation]:
    """Return the operations the methods of ``pylekto.resources`` send, read from their code."""
    found: set[Operation] = set()
    for module in (ROOT / "src" / "pylekto" / "resources").glob("*.py"):
        for node in ast.walk(ast.parse(module.read_text(encoding="utf-8"))):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "_http"
            ):
                continue
            if node.func.attr in _GETS:
                found.add(("GET", _path(node.args[0])))
            elif node.func.attr in _SENDS:
                method = node.args[0]
                assert isinstance(method, ast.Constant), ast.unparse(method)
                assert isinstance(method.value, str), ast.unparse(method)
                found.add((method.value, _path(node.args[1])))
    return found


def recorded() -> set[Operation]:
    """Return the operations the snapshot holds a recording of."""
    found: set[Operation] = set()
    for path in SNAPSHOT.glob("*.json"):
        recording = json.loads(path.read_text(encoding="utf-8"))
        found.add((recording["method"], template(recording["operation"])))
    return found


def test_sign_in_is_what_needs_no_credential() -> None:
    """Only the sign-in and the health check need no credential; the sign-in stays out."""
    open_ = {
        (method.upper(), template(path))
        for path, item in PATHS.items()
        for method, operation in item.items()
        if method in METHODS and operation.get("security") == []
    }
    assert open_ == SIGN_IN | {("GET", "/health")}


def test_every_operation_has_a_method() -> None:
    """A method of a resource sends each operation, but those at an address from a webhook."""
    assert description() >= BY_URL
    assert resources() == description() - BY_URL


def test_every_operation_is_recorded_or_listed() -> None:
    """The snapshot holds each operation, or the list of unrecorded ones says why not."""
    assert not recorded() & UNRECORDED.keys()
    assert recorded() | UNRECORDED.keys() == description()


def test_every_recording_is_replayed() -> None:
    """Each recording is named in a test, so a method is checked against it."""
    names = {
        node.value
        for module in Path(__file__).parent.glob("test_*.py")
        for node in ast.walk(ast.parse(module.read_text(encoding="utf-8")))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    files = [*SNAPSHOT.glob("*.json"), *(SNAPSHOT / "webhooks").glob("*.json")]
    assert {path.stem for path in files} <= names
