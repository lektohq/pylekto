"""Tests that every recording fits the model the OpenAPI description names for its answer."""

import json
from http import HTTPStatus
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from pylekto import LEKTO_VERSION, models

from .conftest import SNAPSHOT, snapshot

ROOT = Path(__file__).resolve().parent.parent
DESCRIPTION = json.loads((ROOT / "openapi.json").read_text(encoding="utf-8"))
NAMES = sorted(path.stem for path in SNAPSHOT.glob("*.json"))


def answer_schema(method: str, operation: str, status: int) -> dict[str, Any]:
    """Return the schema the description names for an answer."""
    answer = DESCRIPTION["paths"]["/api/v1" + operation][method.lower()]["responses"][str(status)]
    schema: dict[str, Any] = answer["content"]["application/json"]["schema"]
    return schema


def validate(schema: dict[str, Any], value: object) -> None:
    """Validate a value against a schema of the description, by the models it names.

    Strictly: a recording holds only values the description lists, so none may become
    ``Unknown`` (which takes a value only in lax mode).
    """
    if "$ref" in schema:
        model = getattr(models, schema["$ref"].rsplit("/", 1)[-1])
        model.model_validate_json(json.dumps(value), strict=True)
    elif "anyOf" in schema:
        failures = []
        for option in schema["anyOf"]:
            try:
                validate(option, value)
            except ValidationError as failure:
                failures.append(failure)
        assert len(failures) < len(schema["anyOf"]), failures
    elif schema.get("type") == "array":
        assert isinstance(value, list)
        for item in value:
            validate(schema["items"], item)
    else:
        assert schema.get("type") == "object"
        assert isinstance(value, dict)


def test_there_are_recordings() -> None:
    """The snapshot holds recordings."""
    assert len(NAMES) > 1


@pytest.mark.parametrize("name", NAMES)
def test_recording_fits_its_model(name: str) -> None:
    """A recording of this Lekto release whose answer validates as its model."""
    recorded = snapshot(name)
    raw = json.loads((SNAPSHOT / f"{name}.json").read_text(encoding="utf-8"))
    assert raw["lekto_version"] == LEKTO_VERSION
    if recorded.text is not None:
        events = [
            line[len("data: ") :]
            for line in recorded.text.splitlines()
            if line.startswith("data: ")
        ]
        assert events
        for data in events:
            models.EventMessage.model_validate_json(data, strict=True)
        return
    if recorded.body is None:
        return
    if recorded.status >= HTTPStatus.BAD_REQUEST:
        models.Problem.model_validate_json(json.dumps(recorded.body), strict=True)
        return
    validate(answer_schema(recorded.method, recorded.operation, recorded.status), recorded.body)
