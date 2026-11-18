"""``/inbox`` and ``/expected``: what waits for the caller, and what should come next."""

from typing import TYPE_CHECKING

from pydantic import TypeAdapter

from pylekto._http import cursor_items, query
from pylekto.models import ExpectedOut, InboxItemOut, InboxPage, InboxSeenOut, InboxSummaryOut
from pylekto.resources._base import Resource

if TYPE_CHECKING:
    import builtins
    from collections.abc import AsyncIterator

    from pylekto.types import InboxTab

_EXPECTED = TypeAdapter(list[ExpectedOut])


class InboxResource(Resource):
    """The caller's inbox: new documents, those to review, to intervene, in processing, done."""

    def list(
        self,
        *,
        tab: InboxTab | None = None,
        all_users: bool | None = None,
        page_size: int | None = None,
    ) -> AsyncIterator[InboxItemOut]:
        """Iterate over every document of an inbox tab, page after page.

        Args:
            tab: The tab; default: everything open.
            all_users: Every user's inbox (admins).
            page_size: How many documents each request fetches.

        Example::

            async for item in lekto.inbox.list(tab="review"):
                print(item.document.title)

        """

        async def fetch(cursor: str | None) -> InboxPage:
            return await self.page(tab=tab, all_users=all_users, cursor=cursor, limit=page_size)

        return cursor_items(fetch)

    async def page(
        self,
        *,
        tab: InboxTab | None = None,
        all_users: bool | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> InboxPage:
        """Return one page of an inbox tab; ``next_cursor`` leads to the next.

        Args:
            tab: The tab; default: everything open.
            all_users: Every user's inbox (admins).
            cursor: Where the page starts: the ``next_cursor`` of the page before.
            limit: How many documents the page holds at most.

        Example::

            page = await lekto.inbox.page(tab="new", limit=10)

        """
        params = query(tab=tab, all_users=all_users, cursor=cursor, limit=limit)
        return await self._http.get("/inbox", InboxPage, params=params)

    async def summary(self, *, all_users: bool | None = None) -> InboxSummaryOut:
        """Count the documents under each tab, and name the worst lane among the open ones.

        Args:
            all_users: Every user's inbox (admins).

        Example::

            summary = await lekto.inbox.summary()
            print(summary.open, summary.worst_lane)

        """
        return await self._http.get(
            "/inbox/summary", InboxSummaryOut, params=query(all_users=all_users)
        )

    async def mark_seen(self, *, all_users: bool | None = None) -> InboxSeenOut:
        """Mark everything new in the inbox as seen.

        Args:
            all_users: Every user's inbox (admins).

        Example::

            seen = await lekto.inbox.mark_seen()

        """
        return await self._http.call(
            "POST", "/inbox/seen", InboxSeenOut, params=query(all_users=all_users)
        )


class ExpectedResource(Resource):
    """The documents expected next, from the series Lekto found."""

    async def list(
        self, *, all_users: bool | None = None, tz: str | None = None
    ) -> builtins.list[ExpectedOut]:
        """Return the documents expected next, each with its series and when it is due.

        Args:
            all_users: Every user's documents (admins).
            tz: The IANA time zone the months begin in, such as ``Europe/Berlin``.

        Example::

            for expected in await lekto.expected.list(tz="Europe/Berlin"):
                print(expected.title, expected.due)

        """
        return await self._http.call_as(
            "GET", "/expected", _EXPECTED, params=query(all_users=all_users, tz=tz)
        )
