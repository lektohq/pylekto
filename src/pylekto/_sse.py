"""Server-sent events: the lines of a ``text/event-stream`` as events."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator


@dataclass(frozen=True)
class ServerSentEvent:
    """One event of a stream: its type, its data and the id the server gave it."""

    event: str
    data: str
    id: str | None


async def server_sent_events(lines: AsyncIterable[str]) -> AsyncIterator[ServerSentEvent]:
    """Yield the events the lines of a stream make, as the HTML standard reads them.

    A blank line ends an event; lines that start with ``:`` are comments; several ``data`` lines
    join with line breaks; an event without data is no event.
    """
    event, last_id = "", None
    data: list[str] = []
    async for raw in lines:
        line = raw.rstrip("\r\n")
        if not line:
            if data:
                yield ServerSentEvent(event or "message", "\n".join(data), last_id)
            event, data = "", []
            continue
        if line.startswith(":"):
            continue
        name, _, value = line.partition(":")
        value = value.removeprefix(" ")
        if name == "event":
            event = value
        elif name == "data":
            data.append(value)
        elif name == "id" and "\0" not in value:
            last_id = value
