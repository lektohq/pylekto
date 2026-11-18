"""Tests of the documents, the search and the relations against the snapshot."""

import json
from collections.abc import Awaitable, Callable
from datetime import date
from uuid import UUID

import pytest

from pylekto import LektoClient, LektoConflictError, LektoResponseError, LektoValidationError
from pylekto._http import query
from pylekto.models import (
    BulkRequest,
    ConfirmRequest,
    DocumentPatch,
    FactDecisionIn,
    ReprocessRequest,
)

from .conftest import DOCUMENT_ID, Api, Snapshot, assert_sent, expected, plain

type Call = Callable[[LektoClient, Snapshot], Awaitable[object]]


def document(recorded: Snapshot) -> str:
    """Return the id of the document in the path of a recording."""
    return recorded.segment(2)


ANSWERS: dict[str, Call] = {
    "documents_page": lambda lekto, _: lekto.documents.page(limit=5),
    "documents_count": lambda lekto, _: lekto.documents.count(),
    "documents_facets": lambda lekto, _: lekto.documents.facets(),
    "documents_stream": lambda lekto, _: lekto.documents.stream(),
    "documents_get": lambda lekto, r: lekto.documents.get(document(r)),
    "documents_text": lambda lekto, r: lekto.documents.text(document(r), limit=400),
    "documents_structure": lambda lekto, r: lekto.documents.structure(document(r)),
    "documents_log": lambda lekto, r: lekto.documents.log(document(r)),
    "documents_facts": lambda lekto, r: lekto.documents.facts(document(r)),
    "documents_place": lambda lekto, r: lekto.documents.place(
        document(r), r.segment(4), r.segment(5)
    ),
    "documents_files": lambda lekto, r: lekto.documents.files(document(r)),
    "documents_reading": lambda lekto, r: lekto.documents.reading(document(r)),
    "documents_review": lambda lekto, r: lekto.documents.review(document(r)),
    "documents_origin": lambda lekto, r: lekto.documents.origin(document(r)),
    "documents_exchanges": lambda lekto, r: lekto.documents.exchanges(document(r), "fields"),
    "documents_dry_run": lambda lekto, r: lekto.documents.dry_run(
        document(r), DocumentPatch.model_validate(r.json)
    ),
    "documents_update": lambda lekto, r: lekto.documents.update(
        document(r), DocumentPatch.model_validate(r.json)
    ),
    "documents_decide_fact": lambda lekto, r: lekto.documents.decide_fact(
        document(r), FactDecisionIn.model_validate(r.json)
    ),
    "documents_withdraw_fact": lambda lekto, r: lekto.documents.decide_fact(
        document(r), FactDecisionIn.model_validate(r.json)
    ),
    "documents_reprocess": lambda lekto, r: lekto.documents.reprocess(
        document(r), ReprocessRequest.model_validate(r.json)
    ),
    "documents_confirm": lambda lekto, r: lekto.documents.confirm(
        document(r), ConfirmRequest.model_validate(r.json)
    ),
    "documents_bulk": lambda lekto, r: lekto.documents.bulk(BulkRequest.model_validate(r.json)),
    "documents_bulk_progress": lambda lekto, r: lekto.documents.bulk_progress(r.segment(3)),
    "search_page": lambda lekto, r: lekto.search.page(r.json["q"], limit=5),
    "search_places": lambda lekto, r: lekto.search.places(document(r), r.json["q"]),
    "search_status": lambda lekto, _: lekto.search.status(),
    "search_check": lambda lekto, _: lekto.search.check(),
    "relations_get": lambda lekto, r: lekto.relations.get(document(r)),
    "relations_add": lambda lekto, r: lekto.relations.add(document(r), r.json["document_id"]),
    "relations_remove": lambda lekto, r: lekto.relations.remove(document(r), r.segment(4)),
}

EMPTY: dict[str, Call] = {
    "documents_mark_seen": lambda lekto, r: lekto.documents.mark_seen(document(r)),
    "documents_mark_new": lambda lekto, r: lekto.documents.mark_new(document(r)),
    "documents_move": lambda lekto, r: lekto.documents.move(document(r), r.json["space_id"]),
    "documents_delete": lambda lekto, r: lekto.documents.delete(document(r)),
    "search_warm": lambda lekto, _: lekto.search.warm(),
    "search_reindex": lambda lekto, _: lekto.search.reindex(),
}


@pytest.mark.parametrize("name", sorted(ANSWERS))
async def test_answer(api: Api, lekto: LektoClient, name: str) -> None:
    """The method sends the recorded request and reads Lekto's answer."""
    recorded = api.replay(name)
    answer = await ANSWERS[name](lekto, recorded)
    assert_sent(api, recorded)
    assert plain(answer) == expected(answer, recorded.body)


@pytest.mark.parametrize("name", sorted(EMPTY))
async def test_empty_answer(api: Api, lekto: LektoClient, name: str) -> None:
    """The method sends the recorded request; Lekto answers without a body."""
    recorded = api.replay(name)
    assert await EMPTY[name](lekto, recorded) is None
    assert_sent(api, recorded)


@pytest.mark.parametrize(
    "name", ["documents_confirm_refused", "documents_retry", "documents_vision"]
)
async def test_refused(api: Api, lekto: LektoClient, name: str) -> None:
    """A document that is not waiting for it refuses with 409 and a reason."""
    recorded = api.replay(name)
    actions: dict[str, Callable[[str], Awaitable[object]]] = {
        "documents_confirm_refused": lekto.documents.confirm,
        "documents_retry": lekto.documents.retry,
        "documents_vision": lekto.documents.vision,
    }
    with pytest.raises(LektoConflictError) as raised:
        await actions[name](document(recorded))
    assert raised.value.reason is not None
    assert raised.value.reason.code == recorded.body["reason"]["code"]


async def test_confirm_with_open_fields(api: Api, lekto: LektoClient) -> None:
    """Confirming without the open fields refuses with 422 and names them."""
    recorded = api.replay("documents_confirm_open_fields")
    with pytest.raises(LektoValidationError) as raised:
        await lekto.documents.confirm(
            document(recorded), ConfirmRequest.model_validate(recorded.json)
        )
    assert raised.value.problem.open_fields == recorded.body["open_fields"]
    assert_sent(api, recorded)


async def test_confirm_without_changes(api: Api, lekto: LektoClient) -> None:
    """Confirming without a request sends an empty one."""
    api.answer("POST", f"/documents/{DOCUMENT_ID}/confirm", 202, json={"id": DOCUMENT_ID})
    answer = await lekto.documents.confirm(DOCUMENT_ID)
    assert str(answer.id) == DOCUMENT_ID
    assert json.loads(api.requests[-1].content) == {}


def form(api: Api) -> bytes:
    """Return the multipart body of the last request."""
    request = api.requests[-1]
    assert request.headers["Content-Type"].startswith("multipart/form-data; boundary=")
    return request.content


async def test_upload(api: Api, lekto: LektoClient) -> None:
    """An upload sends the file and the form fields as parts of a multipart body."""
    recorded = api.replay("documents_upload")
    space = "0199a3c4-0000-7000-8000-0000000000aa"
    answer = await lekto.documents.upload(
        b"%PDF-1.4 made up",
        "documents_upload.pdf",
        space_id=space,
        channel="migration",
        metadata={"title": "Muster Versicherung"},
    )
    assert str(answer.id) == recorded.body["id"]
    sent = form(api)
    assert b'name="file"; filename="documents_upload.pdf"' in sent
    assert b"%PDF-1.4 made up" in sent
    assert b'name="space_id"\r\n\r\n' + space.encode() in sent
    assert b'name="channel"\r\n\r\nmigration' in sent
    assert b'name="metadata"\r\n\r\n{"title": "Muster Versicherung"}' in sent
    assert b'name="uploaded_by"' not in sent


async def test_add_version(api: Api, lekto: LektoClient) -> None:
    """A new version sends its file."""
    recorded = api.replay("documents_add_version")
    answer = await lekto.documents.add_version(document(recorded), b"%PDF-1.4", "scan.pdf")
    assert str(answer.id) == recorded.body["id"]
    assert b'name="file"; filename="scan.pdf"' in form(api)


async def test_edit_pages(api: Api, lekto: LektoClient) -> None:
    """The pages of a file to add are shown."""
    recorded = api.replay("documents_edit_pages")
    answer = await lekto.documents.edit_pages(document(recorded), b"%PDF-1.4", "more.pdf")
    assert plain(answer) == expected(answer, recorded.body)
    assert b'name="file"; filename="more.pdf"' in form(api)


async def test_edit(api: Api, lekto: LektoClient) -> None:
    """An edit sends its parts, other documents, the target and files as multipart parts."""
    recorded = api.replay("documents_edit")
    other = "0199a3c4-0000-7000-8000-0000000000bb"
    answer = await lekto.documents.edit(
        document(recorded),
        [{"pages": [{"page": 1, "rotate": 90}], "replaces": True}],
        files=[("more.pdf", b"%PDF-1.4")],
        documents=[UUID(other)],
        target=document(recorded),
    )
    assert plain(answer) == expected(answer, recorded.body)
    sent = form(api)
    assert b'name="parts"\r\n\r\n' + recorded.data["parts"].encode() in sent
    assert b'name="documents"\r\n\r\n["' + other.encode() + b'"]' in sent
    assert b'name="target"\r\n\r\n' + document(recorded).encode() in sent
    assert b'name="files"; filename="more.pdf"' in sent


async def test_edit_without_files_is_multipart(api: Api, lekto: LektoClient) -> None:
    """An edit without files is still a multipart body: Lekto reads its fields only there."""
    recorded = api.replay("documents_edit")
    await lekto.documents.edit(document(recorded), [{"pages": [{"page": 1}]}])
    sent = form(api)
    assert b'name="parts"\r\n\r\n[{"pages": [{"page": 1}]}]' in sent


@pytest.mark.parametrize(
    ("call", "path"),
    [
        (lambda lekto: lekto.documents.original(DOCUMENT_ID), "/original"),
        (lambda lekto: lekto.documents.version_original(DOCUMENT_ID, 2), "/versions/2/original"),
        (lambda lekto: lekto.documents.archive(DOCUMENT_ID), "/archive"),
        (lambda lekto: lekto.documents.preview(DOCUMENT_ID), "/preview"),
        (lambda lekto: lekto.documents.page_image(DOCUMENT_ID, 3), "/pages/3"),
    ],
)
async def test_download(
    api: Api,
    lekto: LektoClient,
    call: Callable[[LektoClient], Awaitable[bytes]],
    path: str,
) -> None:
    """A download returns the bytes of the file."""
    api.answer("GET", f"/documents/{DOCUMENT_ID}{path}", content=b"\x00made up\xff")
    assert await call(lekto) == b"\x00made up\xff"


async def test_list_follows_the_cursor(api: Api, lekto: LektoClient) -> None:
    """``list`` yields the documents of every page, each request with the cursor before."""
    recorded = api.replay("documents_page")
    cursor = recorded.body["next_cursor"]
    assert cursor is not None
    api.answer(
        "GET", "/documents", json={"items": [], "next_cursor": None}, when={"cursor": cursor}
    )
    found = [item async for item in lekto.documents.list(page_size=5, sort="-created_at")]
    assert [str(item.id) for item in found] == [item["id"] for item in recorded.body["items"]]
    assert api.requests[0].url.params.get("cursor") is None
    assert api.requests[1].url.params.get("cursor") == cursor
    assert api.requests[1].url.params.get("sort") == "-created_at"


async def test_search_list_follows_the_offset(api: Api, lekto: LektoClient) -> None:
    """``search.list`` yields the hits of every page, each request at the next offset."""
    recorded = api.replay("search_page")
    last = {**recorded.body, "items": [], "next_offset": None}
    api.answer("POST", "/documents/search", json={**recorded.body, "next_offset": 5}, when={})
    api.answer("POST", "/documents/search", json=last, when={"offset": "5"})
    found = [hit async for hit in lekto.search.list("Strom", page_size=5)]
    assert len(found) == len(recorded.body["items"])
    assert [request.url.params.get("offset") for request in api.requests] == ["0", "5"]
    assert all(json.loads(request.content) == {"q": "Strom"} for request in api.requests)


async def test_filters_go_in_the_query(api: Api, lekto: LektoClient) -> None:
    """Filters become query values: lists repeated, ids, dates and flags as text."""
    api.answer("GET", "/documents/count", json={"total": 3})
    contact = UUID("0199a3c4-0000-7000-8000-0000000000cc")
    answer = await lekto.documents.count(
        all_users=True,
        lane=["red", "yellow"],
        contact_id=[contact],
        document_date_from=date(2026, 1, 1),
    )
    assert answer.total == 3
    params = api.requests[-1].url.params
    assert params.get_list("lane") == ["red", "yellow"]
    assert params.get("contact_id") == str(contact)
    assert params.get("document_date_from") == "2026-01-01"
    assert params.get("all_users") == "true"


def test_query_leaves_none_out_and_refuses_the_unknown() -> None:
    """``query`` drops None and refuses a value it cannot write."""
    assert query(a=None, b=False, c=1.5, d=[]) == {"b": "false", "c": "1.5", "d": []}
    with pytest.raises(TypeError, match="no query value"):
        query(e=object())


async def test_union_answer_that_does_not_fit(api: Api, lekto: LektoClient) -> None:
    """An answer that fits none of the types of a union raises a response error."""
    api.answer("PATCH", f"/documents/{DOCUMENT_ID}", json={"id": "no uuid"})
    with pytest.raises(LektoResponseError, match=r"PATCH .* does not fit"):
        await lekto.documents.update(DOCUMENT_ID, DocumentPatch(title="Muster"))
