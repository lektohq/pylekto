"""Requests to Lekto's REST API: the token, problem details as exceptions, pages of items."""

import json
from collections.abc import AsyncIterator, Awaitable, Callable, Collection, Mapping, Sequence
from http import HTTPStatus
from typing import Any, Protocol

import httpx2
from pydantic import BaseModel, ValidationError

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

type Params = Mapping[str, str | int | float | bool | Sequence[str] | None]

_ERRORS: dict[int, type[LektoApiError]] = {
    HTTPStatus.UNAUTHORIZED: LektoAuthenticationError,
    HTTPStatus.FORBIDDEN: LektoForbiddenError,
    HTTPStatus.NOT_FOUND: LektoNotFoundError,
    HTTPStatus.CONFLICT: LektoConflictError,
    HTTPStatus.UNPROCESSABLE_ENTITY: LektoValidationError,
}


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

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Params | None = None,
        json: Any = None,
        accept: Collection[int] = (),
    ) -> httpx2.Response:
        """Send a request below ``/api/v1``; an error status raises, unless it is in ``accept``."""
        try:
            response = await self._client.request(
                method, self._api + path, params=params, json=json, headers=self._headers
            )
        except httpx2.TimeoutException as error:
            message = f"Lekto did not answer {method} {path} in time"
            raise LektoTimeoutError(message) from error
        except httpx2.TransportError as error:
            message = f"Lekto is not reachable: {type(error).__name__}"
            raise LektoConnectionError(message) from error
        if response.is_error and response.status_code not in accept:
            raise api_error(response)
        return response

    async def get[M: BaseModel](
        self,
        path: str,
        model: type[M],
        *,
        params: Params | None = None,
        accept: Collection[int] = (),
    ) -> M:
        """GET a JSON answer as a model."""
        return parse(await self.request("GET", path, params=params, accept=accept), model)


def parse[M: BaseModel](response: httpx2.Response, model: type[M]) -> M:
    """Read a JSON answer as a model; one that does not fit raises :class:`LektoResponseError`."""
    try:
        return model.model_validate_json(response.content)
    except ValidationError as error:
        request = response.request
        message = f"Lekto's answer to {request.method} {request.url.path} is no {model.__name__}"
        raise LektoResponseError(message) from error


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
    # A newer Lekto may send a reason code the models do not know: keep what reads plainly.
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


async def cursor_items[T](
    fetch: Callable[[str | None], Awaitable[CursorPage[T]]],
) -> AsyncIterator[T]:
    """Every item of a list, page after page; ``fetch`` gets the cursor (None for the first)."""
    cursor: str | None = None
    while True:
        page = await fetch(cursor)
        for item in page.items:
            yield item
        if page.next_cursor is None:
            return
        cursor = page.next_cursor


async def offset_items[T](fetch: Callable[[int], Awaitable[OffsetPage[T]]]) -> AsyncIterator[T]:
    """Every item of a list, page after page; ``fetch`` gets the offset (0 for the first)."""
    offset = 0
    while True:
        page = await fetch(offset)
        for item in page.items:
            yield item
        if page.next_offset is None:
            return
        offset = page.next_offset
