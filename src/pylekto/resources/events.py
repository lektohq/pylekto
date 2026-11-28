"""``/events``: what happens to documents, as it happens (server-sent events)."""

from contextlib import aclosing
from typing import TYPE_CHECKING

from pydantic import ValidationError

from pylekto._http import query
from pylekto._sse import server_sent_events
from pylekto.exceptions import LektoResponseError
from pylekto.models import EventMessage
from pylekto.resources._base import Resource

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator, Callable

    from pylekto.types import Id


class EventsResource(Resource):
    """The events of the documents the token's user may read, as Lekto sends them."""

    async def listen(
        self, *, document_id: Id | None = None, on_connected: Callable[[], None] | None = None
    ) -> AsyncGenerator[EventMessage]:
        """Yield the events as they happen, until Lekto ends the stream.

        The events are thin: fetch the document for its state. There is no replay: after
        listening again, fetch the current state. Lekto ends the stream when the token is no
        longer valid; a connection silent for 30 s (Lekto keeps a living one busy) raises
        :class:`~pylekto.LektoTimeoutError`, an answer that is no event stream (the page of a
        proxy) :class:`~pylekto.LektoResponseError`. Whether and when to listen again is up to
        the caller. To stop before the stream ends, close it (``aclose()``, or
        ``contextlib.aclosing``): leaving the loop alone keeps the connection open until the
        garbage collector finds it.

        Args:
            document_id: Only the events of this document.
            on_connected: A plain function, no coroutine, called once when the first line of
                the stream arrives, before any event. Lekto sends a line right away, so the call
                shows that the stream flows. It is never called for a stream a proxy holds back;
                that stream raises :class:`~pylekto.LektoTimeoutError`. What it raises ends the
                stream and reaches the caller.

        Example::

            async for event in lekto.events.listen(on_connected=lambda: print("listening")):
                if event.type == "document.filed":
                    document = await lekto.documents.get(event.document_id)

        """
        # Closed here, not when the garbage collector finds it: a raise would leave it open.
        async with aclosing(
            self._http.lines("/events", params=query(document_id=document_id))
        ) as lines:
            flowing = lines if on_connected is None else _announced(lines, on_connected)
            async for event in server_sent_events(flowing):
                try:
                    message = EventMessage.model_validate_json(event.data)
                except ValidationError as error:
                    text = f"Lekto's event {event.event} on GET /events is no EventMessage"
                    raise LektoResponseError(text) from error
                yield message


async def _announced(lines: AsyncIterator[str], announce: Callable[[], None]) -> AsyncIterator[str]:
    """Only a line shows that a stream flows: a proxy may answer 200 and hold the stream back."""
    first = True
    async for line in lines:
        if first:
            announce()
            first = False
        yield line
