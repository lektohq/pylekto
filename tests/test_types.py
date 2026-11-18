"""Tests that the types written by hand match the OpenAPI description."""

import json
from pathlib import Path
from typing import get_args, get_type_hints

from pylekto.types import (
    DocumentFilter,
    EditPart,
    IdentifierKind,
    OpenSource,
    PagePick,
    TagScope,
)

ROOT = Path(__file__).resolve().parent.parent
DESCRIPTION = json.loads((ROOT / "openapi.json").read_text(encoding="utf-8"))
PATHS = DESCRIPTION["paths"]


def query_names(path: str, method: str = "get") -> set[str]:
    """Return the names of the query parameters of an operation."""
    parameters = PATHS["/api/v1" + path][method]["parameters"]
    return {parameter["name"] for parameter in parameters if parameter["in"] == "query"}


def test_document_filter_is_the_filter_of_each_list() -> None:
    """``DocumentFilter`` holds the filters that count, facets, stream and bulk take."""
    keys = set(get_type_hints(DocumentFilter))
    assert keys == query_names("/documents/count")
    assert keys == query_names("/documents/facets")
    assert keys == query_names("/documents/bulk", "post")
    assert keys - {"ids"} == query_names("/documents/stream")
    assert keys - {"ids"} <= query_names("/documents/search", "post")
    assert keys <= query_names("/documents")


def test_edit_parts_are_the_ones_of_the_form() -> None:
    """``EditPart`` and ``PagePick`` hold the keys of the parts of a page edit."""
    form = PATHS["/api/v1/documents/{id}/edit"]["post"]["requestBody"]["content"]
    part = form["multipart/form-data"]["schema"]["properties"]["parts"]["contentSchema"]["items"]
    assert set(get_type_hints(EditPart)) == set(part["properties"])
    assert set(get_type_hints(PagePick)) == set(part["properties"]["pages"]["items"]["properties"])


def test_literals_are_the_descriptions_choices() -> None:
    """``IdentifierKind``, ``TagScope`` and ``OpenSource`` hold the choices of the description."""
    schemas = DESCRIPTION["components"]["schemas"]
    for alias, schema in [
        (IdentifierKind, "IdentifierKind"),
        (TagScope, "TagScope"),
        (OpenSource, "OpenSource"),
    ]:
        assert list(get_args(alias.__value__)) == schemas[schema]["enum"]
