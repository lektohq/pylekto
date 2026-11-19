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
    from collections.abc import AsyncIterator

    from pylekto.types import Id


class EventsResource(Resource):
    """The events of the documents the token's user may read, as Lekto sends them."""

    async def listen(self, *, document_id: Id | None = None) -> AsyncIterator[EventMessage]:
        """Yield the events as they happen, until Lekto ends the stream.

        The events are thin: fetch the document for its state. There is no replay: after
        listening again, fetch the current state. Lekto ends the stream when the token is no
        longer valid; a connection silent for 30 s (Lekto keeps a living one busy) raises
        :class:`~pylekto.LektoTimeoutError`. Whether and when to listen again is up to the
        caller.

        Args:
            document_id: Only the events of this document.

        Example::

            async for event in lekto.events.listen():
                if event.type == "document.filed":
                    document = await lekto.documents.get(event.document_id)

        """
        # Closed here, not when the garbage collector finds it: a raise would leave it open.
        async with aclosing(
            self._http.lines("/events", params=query(document_id=document_id))
        ) as lines:
            async for event in server_sent_events(lines):
                try:
                    message = EventMessage.model_validate_json(event.data)
                except ValidationError as error:
                    text = f"Lekto's event {event.event} on GET /events is no EventMessage"
                    raise LektoResponseError(text) from error
                yield message
