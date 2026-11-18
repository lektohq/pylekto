"""What every area of the API shares."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pylekto._http import Http


class Resource:
    """One area of the API; it sends its requests through the client's :class:`Http`."""

    def __init__(self, http: Http) -> None:
        """Keep the connection to Lekto."""
        self._http = http
