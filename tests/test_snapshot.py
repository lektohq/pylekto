"""Tests that every recording fits the model the OpenAPI description names for its answer."""

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from pylekto import LEKTO_VERSION, models

from .conftest import SNAPSHOT, snapshot

ROOT = Path(__file__).resolve().parent.parent
DESCRIPTION = json.loads((ROOT / "openapi.json").read_text(encoding="utf-8"))
NAMES = sorted(path.stem for path in SNAPSHOT.glob("*.json"))


def answer_model(method: str, operation: str, status: int) -> tuple[type[BaseModel], bool]:
    """Return the model the description names for an answer, and whether it is a list of them."""
    answer = DESCRIPTION["paths"]["/api/v1" + operation][method.lower()]["responses"][str(status)]
    schema = answer["content"]["application/json"]["schema"]
    many = schema.get("type") == "array"
    reference = schema["items"]["$ref"] if many else schema["$ref"]
    return getattr(models, reference.rsplit("/", 1)[-1]), many


def test_there_are_recordings() -> None:
    """The snapshot holds recordings."""
    assert len(NAMES) > 1


@pytest.mark.parametrize("name", NAMES)
def test_recording_fits_its_model(name: str) -> None:
    """A recording of this Lekto release whose answer validates as its model."""
    recorded = snapshot(name)
    raw = json.loads((SNAPSHOT / f"{name}.json").read_text(encoding="utf-8"))
    assert raw["lekto_version"] == LEKTO_VERSION
    if recorded.body is not None:
        model, many = answer_model(recorded.method, recorded.operation, recorded.status)
        for item in recorded.body if many else [recorded.body]:
            model.model_validate(item)
