"""Tests of the event stream and the reading of server-sent events."""

from typing import TYPE_CHECKING

import httpx2
import pytest

from pylekto import LektoAuthenticationError, LektoClient, LektoConnectionError, LektoTimeoutError
from pylekto._sse import ServerSentEvent, server_sent_events

from .conftest import Api, assert_sent

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable


async def lines(texts: Iterable[str]) -> AsyncIterator[str]:
    """Yield lines as a stream would."""
    for text in texts:
        yield text


async def read(texts: Iterable[str]) -> list[ServerSentEvent]:
    """Return the events the lines make."""
    return [event async for event in server_sent_events(lines(texts))]


async def test_listen(api: Api, lekto: LektoClient) -> None:
    """``events.listen`` yields each event of the stream as an ``EventMessage``."""
    recorded = api.replay("events_listen")
    events = [event async for event in lekto.events.listen()]
    assert_sent(api, recorded)
    assert [event.type for event in events] == ["document.updated"]
    assert events[0].model_extra == {"fields": ["title"]}
    assert recorded.text is not None
    assert str(events[0].id) in recorded.text


async def test_listen_to_one_document(api: Api, lekto: LektoClient) -> None:
    """``events.listen`` with a document asks for the events of that document only."""
    recorded = api.replay("events_listen_document")
    document = recorded.params["document_id"]
    events = [event async for event in lekto.events.listen(document_id=document)]
    assert_sent(api, recorded)
    assert all(str(event.document_id) == document for event in events)


async def test_listen_refused(api: Api, lekto: LektoClient) -> None:
    """A stream that Lekto refuses raises with the problem details."""
    api.answer("GET", "/events", 401, json={"title": "Unauthorized", "status": 401})
    with pytest.raises(LektoAuthenticationError):
        [event async for event in lekto.events.listen()]


@pytest.mark.parametrize(
    ("failure", "error"),
    [
        (httpx2.ReadError("broken off"), LektoConnectionError),
        (httpx2.ConnectTimeout("slow"), LektoTimeoutError),
    ],
)
async def test_listen_fails(
    api: Api, lekto: LektoClient, failure: Exception, error: type[LektoConnectionError]
) -> None:
    """A stream that cannot start or breaks off raises a connection error."""
    api.answer("GET", "/events", error=failure)
    with pytest.raises(LektoConnectionError) as raised:
        [event async for event in lekto.events.listen()]
    assert type(raised.value) is error


async def test_listen_to_a_stream_that_cannot_be_decoded(api: Api, lekto: LektoClient) -> None:
    """A stream whose bytes do not match its ``Content-Encoding`` raises a connection error."""
    headers = {"Content-Type": "text/event-stream", "Content-Encoding": "gzip"}
    api.answer("GET", "/events", content=b": ready\n\n", headers=headers)
    with pytest.raises(LektoConnectionError, match=r"GET /events could not be read") as raised:
        [event async for event in lekto.events.listen()]
    assert type(raised.value) is LektoConnectionError
    assert isinstance(raised.value.__cause__, httpx2.DecodingError)


async def test_events_are_read_as_the_standard_says() -> None:
    """Comments are skipped, data lines joined, the id kept, an event without data dropped."""
    events = await read(
        [
            ": ready",
            "",
            "event: one",
            "data: first",
            "data:second",
            "id: 1",
            "",
            "event: empty",
            "",
            "data: third\r",
            "",
            "id: bad\0id",
            "retry: 1000",
            "data: fourth",
            "",
            "data: never ended",
        ]
    )
    assert events == [
        ServerSentEvent("one", "first\nsecond", "1"),
        ServerSentEvent("message", "third", "1"),
        ServerSentEvent("message", "fourth", "1"),
    ]
