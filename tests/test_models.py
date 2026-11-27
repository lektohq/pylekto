"""Tests that the models are the ones generated from the OpenAPI description in the repository."""

import json
import runpy
from pathlib import Path

import pytest
from pydantic import BaseModel

from pylekto import API_VERSION, LEKTO_VERSION, models

ROOT = Path(__file__).resolve().parent.parent


GENERATOR = runpy.run_path(str(ROOT / "script" / "generate_models.py"))


def test_models_match_the_description(monkeypatch: pytest.MonkeyPatch) -> None:
    """``src/pylekto/models.py`` is what ``script/generate_models.py`` writes from ``openapi.json``.

    If this fails, run ``uv run python script/generate_models.py`` and commit the result.
    """
    monkeypatch.chdir(ROOT)
    assert GENERATOR["generate"](check=True)


def test_choices_are_opened_but_not_examples() -> None:
    """Every enum of strings admits ``Unknown``; examples stay, though one may hold a schema."""
    choice = {"type": "string", "enum": ["a", "b"]}
    schema = {"type": "object", "properties": {"examples": choice}, "examples": [choice]}
    opened = GENERATOR["opened"](schema)
    assert opened["properties"]["examples"] == {"anyOf": [choice, GENERATOR["UNKNOWN"]]}
    assert opened["examples"] == [choice]


def test_versions_are_the_descriptions() -> None:
    """``LEKTO_VERSION`` names the Lekto release of ``openapi.json``, ``API_VERSION`` its API."""
    description = json.loads((ROOT / "openapi.json").read_text(encoding="utf-8"))
    assert description["info"]["x-lekto-version"] == LEKTO_VERSION
    assert description["info"]["version"] == API_VERSION


def test_every_model_builds() -> None:
    """Every generated model is complete: each name in its annotations resolves at run time.

    A model defined before an alias it reaches (the items of a group of conditions) completes
    on its first use, which is what ``model_rebuild`` does here.
    """
    built = [
        value
        for value in vars(models).values()
        if isinstance(value, type)
        and issubclass(value, BaseModel)
        and value.__module__ == models.__name__
    ]
    assert len(built) > 100
    for model in built:
        model.model_rebuild()
    assert [model.__name__ for model in built if not model.__pydantic_complete__] == []
