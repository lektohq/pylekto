"""Tests of the event stream and the reading of server-sent events."""

from contextlib import aclosing
from typing import TYPE_CHECKING, Any

import httpx2
import pytest
from pydantic import ValidationError

from pylekto import (
    LektoAuthenticationError,
    LektoClient,
    LektoConnectionError,
    LektoError,
    LektoResponseError,
    LektoTimeoutError,
)
from pylekto._sse import ServerSentEvent, server_sent_events

from .conftest import Api, assert_sent

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable


STREAM = {"Content-Type": "text/event-stream"}


class FallsSilent(httpx2.AsyncByteStream):
    """A stream that starts, then waits for its next byte longer than the read timeout."""

    def __init__(self, sent: bytes = b": ready\n\n") -> None:
        """Hold what comes before the silence: Lekto's first comment unless told otherwise."""
        self.sent = sent

    async def __aiter__(self) -> AsyncIterator[bytes]:
        """Yield what was sent, then time out as httpx2 does."""
        yield self.sent
        message = "no byte within the read timeout"
        raise httpx2.ReadTimeout(message)


class Closes(httpx2.AsyncByteStream):
    """A stream that holds a text and remembers whether it was closed."""

    def __init__(self, text: str) -> None:
        """Hold the text, not closed yet."""
        self.text = text
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        """Yield the text at once."""
        yield self.text.encode()

    async def aclose(self) -> None:
        """Remember that the response was closed."""
        self.closed = True


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


async def test_listen_calls_back_once_the_stream_flows(api: Api, lekto: LektoClient) -> None:
    """``on_connected`` is called once for all the lines of a stream, before its first event."""
    recorded = api.replay("events_listen")
    seen: list[str] = []
    events = lekto.events.listen(on_connected=lambda: seen.append("connected"))
    first = await anext(events)
    seen.append(first.type)
    assert [event async for event in events] == []
    assert seen == ["connected", "document.updated"]
    assert recorded.text is not None
    assert len(recorded.text.splitlines()) > 1


@pytest.mark.parametrize(
    "sent",
    [b": ready\n\n", b": ready\n", b"\n"],
    ids=["Lekto's comment", "one line", "an empty line"],
)
async def test_listen_calls_back_without_an_event(
    api: Api, lekto: LektoClient, sent: bytes
) -> None:
    """The first line is enough, whichever it is: a stream no event comes on is connected too."""
    api.answer("GET", "/events", stream=FallsSilent(sent), headers=STREAM)
    connected: list[bool] = []
    with pytest.raises(LektoTimeoutError):
        [event async for event in lekto.events.listen(on_connected=lambda: connected.append(True))]
    assert connected == [True]


@pytest.mark.parametrize(
    "answer",
    [
        {"status": 401, "json": {"title": "Unauthorized", "status": 401}},
        {"error": httpx2.ConnectTimeout("slow")},
        {"stream": FallsSilent(b""), "headers": STREAM},
        {"stream": FallsSilent(b": rea"), "headers": STREAM},
    ],
    ids=["refused", "not reachable", "held back", "half a line, then silence"],
)
async def test_listen_does_not_call_back_before_a_line(
    api: Api, lekto: LektoClient, answer: dict[str, Any]
) -> None:
    """A refusal, no byte, or half a line before the silence is no line: nothing flows yet."""
    api.answer("GET", "/events", **answer)
    connected: list[bool] = []
    with pytest.raises(LektoError):
        [event async for event in lekto.events.listen(on_connected=lambda: connected.append(True))]
    assert not connected


async def test_listen_ends_with_what_the_callback_raises(api: Api, lekto: LektoClient) -> None:
    """What ``on_connected`` raises reaches the caller as it is, and the stream is closed."""
    stream = Closes(": ready\n\n")
    api.answer("GET", "/events", stream=stream, headers=STREAM)
    failure = httpx2.ReadError("the caller's own")

    def fail() -> None:
        raise failure

    with pytest.raises(httpx2.ReadError) as raised:
        [event async for event in lekto.events.listen(on_connected=fail)]
    assert raised.value is failure
    assert stream.closed


@pytest.mark.parametrize(
    "answer",
    [
        {"content": b"<html>\nSign in\n</html>\n", "headers": {"Content-Type": "text/html"}},
        {"content": b": ready\n\n", "headers": {"Content-Type": "text/event-streams"}},
        {"content": b": ready\n\n"},
        {"status": 302, "content": b"Found\n", "headers": STREAM | {"Location": "/login"}},
        {"status": 204, "headers": STREAM},
    ],
    ids=["a page", "nearly the type", "no type", "a redirect", "no content"],
)
async def test_listen_to_what_is_no_event_stream(
    api: Api, lekto: LektoClient, answer: dict[str, Any]
) -> None:
    """Only a 200 of the type ``text/event-stream`` is a stream: a proxy's page never connects."""
    api.answer("GET", "/events", **answer)
    connected: list[bool] = []
    with pytest.raises(LektoResponseError, match=r"GET /events is no event stream"):
        [event async for event in lekto.events.listen(on_connected=lambda: connected.append(True))]
    assert not connected


@pytest.mark.parametrize(
    "media_type",
    ["text/event-stream; charset=utf-8", "text/event-stream ;charset=utf-8", "Text/Event-Stream"],
)
async def test_listen_to_an_event_stream_named_otherwise(
    api: Api, lekto: LektoClient, media_type: str
) -> None:
    """The type counts without its parameters and whatever its case."""
    recorded = api.replay("events_listen")
    assert recorded.text is not None
    headers = {"Content-Type": media_type}
    api.answer("GET", "/events", content=recorded.text.encode(), headers=headers)

    events = [event async for event in lekto.events.listen()]

    assert [event.type for event in events] == ["document.updated"]


async def test_listen_can_be_closed_early(api: Api, lekto: LektoClient) -> None:
    """The stream is a generator: closing it after an event closes Lekto's answer at once."""
    recorded = api.replay("events_listen")
    assert recorded.text is not None
    stream = Closes(recorded.text)
    api.answer("GET", "/events", stream=stream, headers=STREAM)

    async with aclosing(lekto.events.listen()) as events:
        first = await anext(events)
        assert not stream.closed

    assert first.type == "document.updated"
    assert stream.closed


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


async def test_listen_to_a_connection_that_falls_silent(api: Api, lekto: LektoClient) -> None:
    """A stream waits 30 s for a byte, twice the 15 s after which Lekto sends a comment."""
    api.answer("GET", "/events", stream=FallsSilent(), headers=STREAM)
    with pytest.raises(LektoTimeoutError, match=r"GET /events in time"):
        [event async for event in lekto.events.listen()]
    timeout = api.requests[-1].extensions["timeout"]
    assert timeout == {"connect": 10.0, "read": 30.0, "write": None, "pool": None}


async def test_listen_to_a_stream_that_cannot_be_decoded(api: Api, lekto: LektoClient) -> None:
    """A stream whose bytes do not match its ``Content-Encoding`` raises a connection error."""
    headers = {"Content-Type": "text/event-stream", "Content-Encoding": "gzip"}
    api.answer("GET", "/events", content=b": ready\n\n", headers=headers)
    with pytest.raises(LektoConnectionError, match=r"GET /events could not be read") as raised:
        [event async for event in lekto.events.listen()]
    assert type(raised.value) is LektoConnectionError
    assert isinstance(raised.value.__cause__, httpx2.DecodingError)


@pytest.mark.parametrize(
    "data",
    ["{broken", '{"type": "document.received", "occurred_at": "2026-11-19T08:00:00Z"}'],
)
async def test_listen_to_an_event_that_is_no_event_message(
    api: Api, lekto: LektoClient, data: str
) -> None:
    """An event whose data is no ``EventMessage`` (a proxy's damage) raises a response error."""
    stream = Closes(f": ready\n\nevent: document.received\ndata: {data}\n\n")
    api.answer("GET", "/events", stream=stream, headers=STREAM)
    with pytest.raises(
        LektoResponseError, match=r"event document.received on GET /events"
    ) as raised:
        [event async for event in lekto.events.listen()]
    assert isinstance(raised.value.__cause__, ValidationError)
    assert stream.closed


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
