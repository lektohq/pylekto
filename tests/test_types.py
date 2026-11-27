"""Tests that the types written by hand match the OpenAPI description."""

from typing import get_type_hints

from pylekto.types import (
    AutomationFilter,
    DeliveryFilter,
    DocumentCounts,
    DocumentFilter,
    EditPart,
    InboxFilter,
    JobFilter,
    ListedFilter,
    MailFilter,
    OpenIdentifierFilter,
    PagePick,
)

from .conftest import API, DESCRIPTION

PATHS = DESCRIPTION["paths"]


def query_names(path: str, method: str = "get") -> set[str]:
    """Return the names of the query parameters of an operation."""
    parameters = PATHS[API + path][method]["parameters"]
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


def test_each_filter_is_the_one_of_its_lists() -> None:
    """A filter holds what the query of its operations takes besides the place in the list."""
    place = {"cursor", "offset", "limit"}
    for filters, path, method in [
        (InboxFilter, "/inbox", "get"),
        (OpenIdentifierFilter, "/identifiers/open", "get"),
        (OpenIdentifierFilter, "/identifiers/open/search", "post"),
        (JobFilter, "/jobs", "get"),
        (MailFilter, "/mailboxes/{id}/mails", "get"),
        (DeliveryFilter, "/webhooks/{id}/deliveries", "get"),
        (AutomationFilter, "/automation", "get"),
        (AutomationFilter, "/automation/signals", "get"),
        (DocumentCounts, "/contacts", "get"),
        (DocumentCounts, "/document-types", "get"),
        (DocumentCounts, "/fields", "get"),
    ]:
        assert set(get_type_hints(filters)) == query_names(path, method) - place, path
    assert set(get_type_hints(DocumentCounts)) == query_names("/tags") - {"scope"}


def test_edit_parts_are_the_ones_of_the_form() -> None:
    """``EditPart`` and ``PagePick`` hold the keys of the parts of a page edit."""
    form = PATHS[API + "/documents/{id}/edit"]["post"]["requestBody"]["content"]
    part = form["multipart/form-data"]["schema"]["properties"]["parts"]["contentSchema"]["items"]
    assert set(get_type_hints(EditPart)) == set(part["properties"])
    assert set(get_type_hints(PagePick)) == set(part["properties"]["pages"]["items"]["properties"])
