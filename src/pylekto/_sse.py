"""Server-sent events: the lines of a ``text/event-stream`` as events."""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator

_LINE_END = re.compile(r"\r\n|\n|\r")


@dataclass(frozen=True)
class ServerSentEvent:
    """One event of a stream: its type, its data and the id the server gave it."""

    event: str
    data: str
    id: str | None


async def text_lines(chunks: AsyncIterable[str]) -> AsyncIterator[str]:
    """Yield the lines of a stream's text, ended by CR, LF or CRLF alone, as the standard says.

    httpx2 ends a line wherever ``str.splitlines`` does, so also at U+2028, U+2029 and U+0085,
    which may stand in the data of an event and would tear it apart.
    """
    rest = ""
    after_cr = False
    async for chunk in chunks:
        if not chunk:
            continue
        # A CR ends its line at once; an LF that opens the next chunk is the rest of a CRLF.
        text = chunk.removeprefix("\n") if after_cr else chunk
        after_cr = chunk.endswith("\r")
        *whole, rest = _LINE_END.split(rest + text)
        for line in whole:
            yield line
    if rest:
        yield rest


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
