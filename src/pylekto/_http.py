"""Requests to Lekto's REST API: the token, problem details as exceptions, pages of items."""

import json
from collections.abc import (
    AsyncGenerator,
    AsyncIterator,
    Awaitable,
    Callable,
    Collection,
    Mapping,
    Sequence,
)
from contextlib import asynccontextmanager
from datetime import date
from http import HTTPStatus
from string.templatelib import Template
from typing import IO, Any, Protocol, TypedDict, Unpack
from urllib.parse import quote
from uuid import UUID

import httpx2
from pydantic import BaseModel, SecretBytes, SecretStr, TypeAdapter, ValidationError

from pylekto.exceptions import (
    LektoApiError,
    LektoAuthenticationError,
    LektoConflictError,
    LektoConnectionError,
    LektoForbiddenError,
    LektoNotFoundError,
    LektoRateLimitError,
    LektoResponseError,
    LektoServerError,
    LektoTimeoutError,
    LektoValidationError,
)
from pylekto.models import Problem

API_PATH = "/api/v1"
# Only for the clients pylekto makes itself; a client passed in keeps its own settings.
TIMEOUT = httpx2.Timeout(30.0, connect=10.0)
# Also on a client passed in: twice the 15 s after which Lekto sends a comment (": ping").
STREAM = httpx2.Timeout(None, connect=10.0, read=30.0)
# Writes ids, dates and the like as JSON (for request bodies).
_JSON: TypeAdapter[Any] = TypeAdapter(Any)
# Lekto recognises a file by its content, not by the type a client names.
FILE_TYPE = "application/octet-stream"

# A path below ``/api/v1``: a template (``t"/documents/{document_id}"``) wherever it holds values.
type Path = str | Template
type Params = Mapping[str, str | Sequence[str]]
type Upload = bytes | IO[bytes]
# A multipart part: a file (name, content, type) or a form field (None, its text).
type Part = tuple[str, Upload, str] | tuple[None, str]
type Files = Sequence[tuple[str, Part]]


def file_part(file: Upload, filename: str, field: str = "file") -> tuple[str, Part]:
    """Return a file as a part of a multipart body, under the name of its form field."""
    return field, (filename, file, FILE_TYPE)


_ERRORS: dict[int, type[LektoApiError]] = {
    HTTPStatus.UNAUTHORIZED: LektoAuthenticationError,
    HTTPStatus.FORBIDDEN: LektoForbiddenError,
    HTTPStatus.NOT_FOUND: LektoNotFoundError,
    HTTPStatus.CONFLICT: LektoConflictError,
    HTTPStatus.UNPROCESSABLE_ENTITY: LektoValidationError,
}


class Send(TypedDict, total=False):
    """What a request carries besides method and path.

    ``files`` makes a ``multipart/form-data`` body; form fields go in it as ``(None, text)``,
    because Lekto reads them only there.
    """

    params: Params
    json: Any
    files: Files
    accept: Collection[int]


class Http:
    """Sends requests to one Lekto instance with its API token.

    The httpx2 client may be shared with the rest of an application: the base URL and the token go
    with each request, the client's own settings stay as they are.
    """

    def __init__(self, url: str, token: str, client: httpx2.AsyncClient) -> None:
        """Remember where the API lies, the token and the client that sends the requests."""
        self._api = url.rstrip("/") + API_PATH
        self._headers = {"Authorization": f"Bearer {token}"}
        self._client = client

    async def request(self, method: str, path: Path, **send: Unpack[Send]) -> httpx2.Response:
        """Send a request below ``/api/v1``; an error status raises, unless it is in ``accept``."""
        url = self._api + address(path)
        return await exchange(self._client, method, url, self._headers, **send)

    async def get[M: BaseModel](self, path: Path, model: type[M], **send: Unpack[Send]) -> M:
        """GET a JSON answer as a model."""
        return await self.call("GET", path, model, **send)

    async def call[M: BaseModel](
        self, method: str, path: Path, model: type[M], **send: Unpack[Send]
    ) -> M:
        """Send a request and read its JSON answer as a model."""
        return parse(await self.request(method, path, **send), model)

    async def call_as[T](
        self, method: str, path: Path, answer: TypeAdapter[T], **send: Unpack[Send]
    ) -> T:
        """Send a request and read its JSON answer as a type that is no model: a list, a union."""
        return parse_as(await self.request(method, path, **send), answer)

    async def call_empty(self, method: str, path: Path, **send: Unpack[Send]) -> None:
        """Send a request whose answer has no body (204, or 202 without one)."""
        await self.request(method, path, **send)

    async def download(self, path: Path) -> bytes:
        """GET the bytes of a file."""
        return (await self.request("GET", path)).content

    async def lines(self, path: Path, *, params: Params | None = None) -> AsyncGenerator[str]:
        """GET a stream and yield its lines as they come, until Lekto ends it.

        Lekto may send no event for long but keeps the stream alive with comments: after 30 s
        without a byte it raises :class:`LektoTimeoutError`.
        """
        target = address(path)
        try:
            async with self._client.stream(
                "GET", self._api + target, params=params, headers=self._headers, timeout=STREAM
            ) as response:
                if response.is_error:
                    await response.aread()
                    raise api_error(response)
                async for line in response.aiter_lines():
                    yield line
        except httpx2.RequestError as error:
            raise _request_error(error, "GET", target) from error


async def exchange(
    client: httpx2.AsyncClient,
    method: str,
    url: str,
    headers: Mapping[str, str],
    **send: Unpack[Send],
) -> httpx2.Response:
    """Send a request to Lekto; a failed connection or an error status raises a LektoError."""
    try:
        response = await client.request(
            method,
            url,
            params=send.get("params"),
            json=send.get("json"),
            files=send.get("files"),
            headers=headers,
        )
    except httpx2.RequestError as error:
        raise _request_error(error, method, httpx2.URL(url).path) from error
    if response.is_error and response.status_code not in send.get("accept", ()):
        raise api_error(response)
    return response


def _request_error(error: httpx2.RequestError, method: str, path: str) -> LektoConnectionError:
    """Return the exception for a request that failed in httpx2.

    A body it cannot decode, or a loop of redirects, is no ``TransportError`` but fails it too.
    """
    if isinstance(error, httpx2.TimeoutException):
        return LektoTimeoutError(f"Lekto did not answer {method} {path} in time")
    if isinstance(error, httpx2.TransportError):
        return LektoConnectionError(f"Lekto is not reachable: {type(error).__name__}")
    return LektoConnectionError(
        f"Lekto's answer to {method} {path} could not be read: {type(error).__name__}"
    )


def new_client() -> httpx2.AsyncClient:
    """Make the httpx2 client pylekto sends with where none is passed in."""
    return httpx2.AsyncClient(timeout=TIMEOUT)


@asynccontextmanager
async def http_client(client: httpx2.AsyncClient | None) -> AsyncIterator[httpx2.AsyncClient]:
    """Yield the client given, or one made for the moment and closed afterwards."""
    if client is not None:
        yield client
        return
    own = new_client()
    try:
        yield own
    finally:
        await own.aclose()


def address(path: Path) -> str:
    """Write a path with each value of its template as one segment, percent-encoded.

    A value never leaves its segment: an id with ``?`` in it would add a query, one with ``/``
    reach another operation.
    """
    if isinstance(path, str):
        return path
    return "".join(part if isinstance(part, str) else _segment(part.value) for part in path)


def _segment(value: object) -> str:
    """Encode one path value, or refuse one that no encoding keeps in its segment.

    An empty one names another operation; httpx2 resolves ``.`` and ``..``; Lekto's server
    decodes ``%2F`` before it finds the operation, and a proxy may read a backslash as ``/``.
    """
    text = str(value)
    if text in {"", ".", ".."} or "/" in text or "\\" in text:
        message = f"no path value: {text!r}"
        raise ValueError(message)
    return quote(text, safe="")


def query(**values: object) -> dict[str, str | list[str]]:
    """Turn query values into what Lekto reads: ids, dates and flags as text; None is left out."""
    params: dict[str, str | list[str]] = {}
    for name, value in values.items():
        if value is None:
            continue
        if isinstance(value, Sequence) and not isinstance(value, str):
            params[name] = [_text(item) for item in value]
        else:
            params[name] = _text(value)
    return params


def _text(value: object) -> str:
    """Write one query value as Lekto reads it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID | str | int | float):
        return str(value)
    message = f"no query value: {value!r}"
    raise TypeError(message)


def body(model: BaseModel) -> Any:
    """Return the JSON of a request body: only the values set, so a change sends no others.

    Secrets (a mailbox's password) go as they are: pydantic would write them as ``**********``.
    """
    values = model.model_dump(mode="python", by_alias=True, exclude_unset=True)
    return _JSON.dump_python(_reveal(values), mode="json")


def _reveal(value: object) -> object:
    """Put the values of the secrets in a dumped model in place of the secrets."""
    if isinstance(value, SecretStr | SecretBytes):
        return value.get_secret_value()
    if isinstance(value, dict):
        return {key: _reveal(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_reveal(item) for item in value]
    return value


def parse[M: BaseModel](response: httpx2.Response, model: type[M]) -> M:
    """Read a JSON answer as a model; one that does not fit raises :class:`LektoResponseError`."""
    try:
        return model.model_validate_json(response.content)
    except ValidationError as error:
        raise _unfit(response, f"is no {model.__name__}") from error


def parse_as[T](response: httpx2.Response, answer: TypeAdapter[T]) -> T:
    """Read a JSON answer as a type; one that does not fit raises :class:`LektoResponseError`."""
    try:
        return answer.validate_json(response.content)
    except ValidationError as error:
        raise _unfit(response, "does not fit") from error


def _unfit(response: httpx2.Response, how: str) -> LektoResponseError:
    """Return the exception for an answer the models do not describe."""
    request = response.request
    return LektoResponseError(f"Lekto's answer to {request.method} {request.url.path} {how}")


def api_error(response: httpx2.Response) -> LektoApiError:
    """Build the exception for an error status, with the problem details of the answer."""
    problem = _problem(response)
    status = response.status_code
    if status == HTTPStatus.TOO_MANY_REQUESTS:
        return LektoRateLimitError(problem, _retry_after(response.headers.get("Retry-After")))
    if status >= HTTPStatus.INTERNAL_SERVER_ERROR:
        return LektoServerError(problem)
    return _ERRORS.get(status, LektoApiError)(problem)


def _problem(response: httpx2.Response) -> Problem:
    """Read the problem details; a body that holds none (a proxy's page) gives the status alone."""
    try:
        return Problem.model_validate_json(response.content)
    except ValidationError:
        pass
    title = response.reason_phrase or "Error"
    detail = None
    try:
        body = json.loads(response.content)
    except ValueError:
        body = None
    if isinstance(body, dict):
        title = body["title"] if isinstance(body.get("title"), str) else title
        detail = body["detail"] if isinstance(body.get("detail"), str) else None
    return Problem(title=title, status=response.status_code, detail=detail)


def _retry_after(header: str | None) -> float | None:
    """Seconds from a ``Retry-After`` header that holds a number."""
    try:
        return max(float(header), 0.0) if header is not None else None
    except ValueError:
        return None


class CursorPage[T](Protocol):
    """A page of a list that continues with a cursor (documents, the inbox)."""

    @property
    def items(self) -> Sequence[T]:
        """The items of this page."""
        ...

    @property
    def next_cursor(self) -> str | None:
        """Where the next page starts; None on the last."""
        ...


class OffsetPage[T](Protocol):
    """A page of a list that continues at an offset (jobs, deliveries, mails)."""

    @property
    def items(self) -> Sequence[T]:
        """The items of this page."""
        ...

    @property
    def next_offset(self) -> int | None:
        """Where the next page starts; None on the last."""
        ...


class TotalPage[T](Protocol):
    """A page of a list that says how many items it holds in all (open identifiers)."""

    @property
    def items(self) -> Sequence[T]:
        """The items of this page."""
        ...

    @property
    def total(self) -> int:
        """How many items the list holds in all."""
        ...


async def cursor_items[T](
    fetch: Callable[[str | None], Awaitable[CursorPage[T]]],
) -> AsyncIterator[T]:
    """Every item of a list, page after page; ``fetch`` gets the cursor (None for the first)."""
    async for page in _pages(None, fetch, lambda _, page: page.next_cursor):
        for item in page.items:
            yield item


async def offset_items[T](fetch: Callable[[int], Awaitable[OffsetPage[T]]]) -> AsyncIterator[T]:
    """Every item of a list, page after page; ``fetch`` gets the offset (0 for the first)."""
    async for page in _pages(0, fetch, lambda _, page: page.next_offset):
        for item in page.items:
            yield item


async def total_items[T](fetch: Callable[[int], Awaitable[TotalPage[T]]]) -> AsyncIterator[T]:
    """Every item of a list that gives its total instead of the next offset (open identifiers).

    An empty page ends it too: the total may shrink while the pages are read.
    """
    async for page in _pages(0, fetch, _offset_below_total):
        for item in page.items:
            yield item


def _offset_below_total(offset: int, page: TotalPage[Any]) -> int | None:
    """Return the offset after a page, or None once it was empty or reached the total."""
    after = offset + len(page.items)
    return after if page.items and after < page.total else None


async def _pages[P, G](
    start: P, fetch: Callable[[P], Awaitable[G]], following: Callable[[P, G], P | None]
) -> AsyncIterator[G]:
    """Yield page after page from ``start``; ``following`` names the next position, or None."""
    position = start
    while True:
        page = await fetch(position)
        yield page
        after = following(position, page)
        if after is None:
            return
        position = after
