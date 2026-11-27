"""Tests that the types written by hand match the OpenAPI description."""

import json
from pathlib import Path
from typing import get_type_hints

from pylekto.types import DocumentFilter, EditPart, ListedFilter, PagePick

ROOT = Path(__file__).resolve().parent.parent
DESCRIPTION = json.loads((ROOT / "openapi.json").read_text(encoding="utf-8"))
PATHS = DESCRIPTION["paths"]


def query_names(path: str, method: str = "get") -> set[str]:
    """Return the names of the query parameters of an operation."""
    parameters = PATHS["/api/v1" + path][method]["parameters"]
    return {parameter["name"] for parameter in parameters if parameter["in"] == "query"}


def test_document_filter_is_the_filter_of_each_list() -> None:
    """``DocumentFilter`` holds what stream and bulk take, ``ListedFilter`` what a list takes."""
    keys = set(get_type_hints(DocumentFilter))
    assert keys == query_names("/documents/bulk", "post")
    assert keys - {"ids"} == query_names("/documents/stream")
    assert keys - {"ids"} <= query_names("/documents/search", "post")
    listed = set(get_type_hints(ListedFilter))
    assert listed - keys == {"in_inbox"}
    assert listed == query_names("/documents/count")
    assert listed == query_names("/documents/facets")
    assert query_names("/documents") - listed == {
        "cursor",
        "offset",
        "limit",
        "sort",
        "sort_field_id",
    }


def test_edit_parts_are_the_ones_of_the_form() -> None:
    """``EditPart`` and ``PagePick`` hold the keys of the parts of a page edit."""
    form = PATHS["/api/v1/documents/{id}/edit"]["post"]["requestBody"]["content"]
    part = form["multipart/form-data"]["schema"]["properties"]["parts"]["contentSchema"]["items"]
    assert set(get_type_hints(EditPart)) == set(part["properties"])
    assert set(get_type_hints(PagePick)) == set(part["properties"]["pages"]["items"]["properties"])
