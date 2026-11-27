"""Tests of the HTTP layer: errors as exceptions, answers as models, pages of items."""

from dataclasses import dataclass
from datetime import date

import httpx2
import pytest
from pydantic import SecretBytes, SecretStr

from pylekto import (
    LektoApiError,
    LektoAuthenticationError,
    LektoClient,
    LektoConflictError,
    LektoConnectionError,
    LektoForbiddenError,
    LektoNotFoundError,
    LektoRateLimitError,
    LektoResponseError,
    LektoServerError,
    LektoTimeoutError,
    LektoValidationError,
    Unknown,
)
from pylekto._http import _reveal, body, cursor_items, offset_items
from pylekto.models import DocumentPatch, MailboxPatch

from .conftest import DOCUMENT_ID, TOKEN, URL, Api


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (400, LektoApiError),
        (401, LektoAuthenticationError),
        (403, LektoForbiddenError),
        (404, LektoNotFoundError),
        (409, LektoConflictError),
        (413, LektoApiError),
        (422, LektoValidationError),
        (429, LektoRateLimitError),
        (500, LektoServerError),
        (502, LektoServerError),
    ],
)
async def test_status_gives_its_error(
    api: Api, lekto: LektoClient, status: int, error: type[LektoApiError]
) -> None:
    """Each error status raises its own exception, with the status and the title."""
    api.answer("GET", "/auth/me", status, json={"title": "Refused", "status": status})
    with pytest.raises(LektoApiError) as raised:
        await lekto.auth.me()
    assert type(raised.value) is error
    assert raised.value.status == status
    assert str(raised.value) == f"{status} Refused"


async def test_problem_details(api: Api, lekto: LektoClient) -> None:
    """The problem details come with the exception: detail, reason and the errors per field."""
    reason = {"code": "input_too_short", "params": {"min": 1}}
    problem = {
        "title": "Unprocessable Content",
        "status": 422,
        "detail": "name: too short",
        "reason": reason,
        "errors": [{"field": "name", "message": "too short", "reason": reason}],
    }
    api.answer("GET", "/auth/me", 422, json=problem)
    with pytest.raises(LektoValidationError) as raised:
        await lekto.auth.me()
    error = raised.value
    assert str(error) == "422 Unprocessable Content: name: too short"
    assert error.reason is not None
    assert error.reason.code == "input_too_short"
    assert [(e.field, e.reason.code) for e in error.errors] == [("name", "input_too_short")]


async def test_conflict_names_the_existing_document(api: Api, lekto: LektoClient) -> None:
    """A duplicate upload names the document it collided with."""
    problem = {"title": "Conflict", "status": 409, "existing_document_id": DOCUMENT_ID}
    api.answer("GET", "/auth/me", 409, json=problem)
    with pytest.raises(LektoConflictError) as raised:
        await lekto.auth.me()
    assert str(raised.value.existing_document_id) == DOCUMENT_ID
    assert raised.value.errors == []


async def test_error_without_problem_details(api: Api, lekto: LektoClient) -> None:
    """An error page of a proxy gives the status and its phrase."""
    api.answer("GET", "/auth/me", 502, content=b"<html>Bad Gateway</html>")
    with pytest.raises(LektoServerError) as raised:
        await lekto.auth.me()
    assert raised.value.problem.title == "Bad Gateway"
    assert raised.value.problem.detail is None
    assert raised.value.reason is None


async def test_error_with_unknown_reason_keeps_it(api: Api, lekto: LektoClient) -> None:
    """Problem details with a reason the models do not know keep it as an ``Unknown``."""
    problem = {
        "title": "Bad Request",
        "status": 400,
        "detail": "something new",
        "reason": {"code": "made_up_code", "params": {}},
    }
    api.answer("GET", "/auth/me", 400, json=problem)
    with pytest.raises(LektoApiError) as raised:
        await lekto.auth.me()
    assert str(raised.value) == "400 Bad Request: something new"
    assert raised.value.reason is not None
    assert raised.value.reason.code == "made_up_code"
    assert isinstance(raised.value.reason.code, Unknown)


async def test_error_with_other_json_keeps_its_text(api: Api, lekto: LektoClient) -> None:
    """JSON that holds no problem details (a proxy's) keeps its title and detail."""
    api.answer("GET", "/auth/me", 502, json={"title": "Muster Gateway", "detail": "no answer"})
    with pytest.raises(LektoServerError) as raised:
        await lekto.auth.me()
    assert str(raised.value) == "502 Muster Gateway: no answer"
    assert raised.value.reason is None


@pytest.mark.parametrize(
    ("header", "seconds"),
    [("7", 7.0), ("0.5", 0.5), ("-3", 0.0), ("Wed, 21 Oct 2026 07:28:00 GMT", None), (None, None)],
)
async def test_rate_limit_says_how_long_to_wait(
    api: Api, lekto: LektoClient, header: str | None, seconds: float | None
) -> None:
    """``Retry-After`` in seconds becomes ``retry_after``; any other form is None."""
    headers = {} if header is None else {"Retry-After": header}
    api.answer("GET", "/auth/me", 429, json={"title": "Too Many", "status": 429}, headers=headers)
    with pytest.raises(LektoRateLimitError) as raised:
        await lekto.auth.me()
    assert raised.value.retry_after == seconds


@pytest.mark.parametrize(
    ("failure", "error"),
    [
        (httpx2.ConnectError("refused"), LektoConnectionError),
        (httpx2.ReadTimeout("slow"), LektoTimeoutError),
    ],
)
async def test_transport_failure(
    api: Api, lekto: LektoClient, failure: Exception, error: type[LektoConnectionError]
) -> None:
    """A connection that fails or times out raises a connection error, with the cause."""
    api.answer("GET", "/auth/me", error=failure)
    with pytest.raises(LektoConnectionError) as raised:
        await lekto.auth.me()
    assert type(raised.value) is error
    assert raised.value.__cause__ is failure


async def test_answer_that_cannot_be_decoded(api: Api, lekto: LektoClient) -> None:
    """A body that does not match its ``Content-Encoding`` raises a connection error."""
    api.answer("GET", "/auth/me", content=b"no gzip", headers={"Content-Encoding": "gzip"})
    with pytest.raises(
        LektoConnectionError, match=r"GET /api/v1/auth/me could not be read"
    ) as raised:
        await lekto.auth.me()
    assert type(raised.value) is LektoConnectionError
    assert isinstance(raised.value.__cause__, httpx2.DecodingError)


async def test_redirects_in_a_circle(api: Api) -> None:
    """A client passed in that follows redirects raises a connection error on a loop of them."""
    api.answer("GET", "/auth/me", 302, headers={"Location": f"{URL}/api/v1/auth/me"})
    async with httpx2.AsyncClient(
        transport=httpx2.MockTransport(api), follow_redirects=True
    ) as http:
        lekto = LektoClient(URL, TOKEN, client=http)
        with pytest.raises(LektoConnectionError, match=r"could not be read") as raised:
            await lekto.auth.me()
    assert type(raised.value) is LektoConnectionError
    assert isinstance(raised.value.__cause__, httpx2.TooManyRedirects)


@pytest.mark.parametrize(
    ("value", "sent"),
    [
        ("a/b", "a%2Fb"),
        ("a?b=c#d", "a%3Fb%3Dc%23d"),
        ("../users", "..%2Fusers"),
        ("ä b", "%C3%A4%20b"),
        (DOCUMENT_ID, DOCUMENT_ID),
    ],
)
async def test_a_path_value_stays_in_its_segment(
    api: Api, lekto: LektoClient, value: str, sent: str
) -> None:
    """A value put in a path is percent-encoded, so it reaches no other operation."""
    api.answer("DELETE", f"/documents/{value}", 204)
    await lekto.documents.delete(value)
    assert api.requests[-1].url.raw_path == f"/api/v1/documents/{sent}".encode()


@pytest.mark.parametrize("value", ["", ".", ".."])
async def test_a_path_value_that_is_none(api: Api, lekto: LektoClient, value: str) -> None:
    """An empty value and one that leads up are refused before a request is sent."""
    with pytest.raises(ValueError, match="no path value"):
        await lekto.documents.get(value)
    assert api.requests == []


async def test_answer_the_models_do_not_describe(api: Api, lekto: LektoClient) -> None:
    """An answer that does not fit the model raises a response error."""
    api.answer("GET", "/auth/me", json={"user": None})
    with pytest.raises(LektoResponseError, match=r"GET /api/v1/auth/me is no Me"):
        await lekto.auth.me()


@dataclass
class CursorPage:
    """A page of a list with a cursor."""

    items: list[int]
    next_cursor: str | None


@dataclass
class OffsetPage:
    """A page of a list with an offset."""

    items: list[int]
    next_offset: int | None


async def test_cursor_items() -> None:
    """Every item of every page, the cursor of each page handed to the next request."""
    pages = {None: CursorPage([1, 2], "b"), "b": CursorPage([3], "c"), "c": CursorPage([], None)}
    asked: list[str | None] = []

    async def fetch(cursor: str | None) -> CursorPage:
        asked.append(cursor)
        return pages[cursor]

    assert [item async for item in cursor_items(fetch)] == [1, 2, 3]
    assert asked == [None, "b", "c"]


async def test_offset_items() -> None:
    """Every item of every page, from offset 0 to where the last page ends."""
    pages = {0: OffsetPage([1, 2], 2), 2: OffsetPage([3], None)}
    asked: list[int] = []

    async def fetch(offset: int) -> OffsetPage:
        asked.append(offset)
        return pages[offset]

    assert [item async for item in offset_items(fetch)] == [1, 2, 3]
    assert asked == [0, 2]


def test_body_sends_secrets_and_only_what_was_set() -> None:
    """A body holds the values set, secrets as they are, ids and dates as JSON."""
    mailbox = MailboxPatch(password=SecretStr("made-up-password"), interval_minutes=60)
    assert body(mailbox) == {"password": "made-up-password", "interval_minutes": 60}
    patch = DocumentPatch(contact_id=None, document_date=date(2026, 10, 1))
    assert body(patch) == {"contact_id": None, "document_date": "2026-10-01"}
    assert _reveal([SecretBytes(b"made up")]) == [b"made up"]
