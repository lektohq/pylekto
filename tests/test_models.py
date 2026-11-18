"""Tests that the models are the ones generated from the OpenAPI description in the repository."""

import json
from pathlib import Path

import pytest
from datamodel_code_generator.__main__ import Exit, main
from pydantic import BaseModel

from pylekto import LEKTO_VERSION, models

ROOT = Path(__file__).resolve().parent.parent


def test_models_match_the_description(monkeypatch: pytest.MonkeyPatch) -> None:
    """``src/pylekto/models.py`` is what datamodel-codegen writes from ``openapi.json``.

    If this fails, run ``uv run datamodel-codegen`` and commit the result.
    """
    monkeypatch.chdir(ROOT)
    assert main(["--check"]) == Exit.OK


def test_version_is_the_descriptions() -> None:
    """``LEKTO_VERSION`` names the Lekto release of ``openapi.json``."""
    description = json.loads((ROOT / "openapi.json").read_text(encoding="utf-8"))
    assert description["info"]["version"] == LEKTO_VERSION


def test_every_model_builds() -> None:
    """Every generated model is complete: each name in its annotations resolves at run time."""
    built = [
        value
        for value in vars(models).values()
        if isinstance(value, type)
        and issubclass(value, BaseModel)
        and value.__module__ == models.__name__
    ]
    assert len(built) > 100
    assert [model.__name__ for model in built if not model.__pydantic_complete__] == []
