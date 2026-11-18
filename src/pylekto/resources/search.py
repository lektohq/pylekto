"""Search: documents by words and meaning, and the search index."""

from typing import TYPE_CHECKING, Unpack

from pylekto._http import offset_items, query
from pylekto.models import (
    DocumentSort,
    IndexCheckOut,
    SearchPlacesOut,
    SearchResultItem,
    SearchResultPage,
    SearchStatusOut,
)
from pylekto.resources._base import Resource

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pylekto.types import DocumentFilter, Id


class SearchResource(Resource):
    """Search the documents, and look after the search index."""

    def list(
        self,
        words: str,
        *,
        sort: DocumentSort | None = None,
        semantic_ratio: float | None = None,
        page_size: int | None = None,
        **filters: Unpack[DocumentFilter],
    ) -> AsyncIterator[SearchResultItem]:
        """Iterate over every document a search finds, page after page.

        Args:
            words: What to search for; it goes in the body, never in the address.
            sort: The order; default: by relevance.
            semantic_ratio: How much the meaning counts against the words, from 0 to 1.
            page_size: How many hits each request fetches.
            **filters: Which documents (:class:`pylekto.types.DocumentFilter`).

        Example::

            async for hit in lekto.search.list("electricity bill 2025"):
                print(hit.document.title)

        """

        async def fetch(offset: int) -> SearchResultPage:
            return await self.page(
                words,
                offset=offset,
                limit=page_size,
                sort=sort,
                semantic_ratio=semantic_ratio,
                **filters,
            )

        return offset_items(fetch)

    async def page(
        self,
        words: str,
        *,
        offset: int | None = None,
        limit: int | None = None,
        sort: DocumentSort | None = None,
        semantic_ratio: float | None = None,
        **filters: Unpack[DocumentFilter],
    ) -> SearchResultPage:
        """Return one page of a search, with how it searched and how many it found.

        Args:
            words: What to search for; it goes in the body, never in the address.
            offset: Skip so many hits.
            limit: How many hits the page holds at most.
            sort: The order; default: by relevance.
            semantic_ratio: How much the meaning counts against the words, from 0 to 1.
            **filters: Which documents (:class:`pylekto.types.DocumentFilter`).

        Example::

            result = await lekto.search.page("insurance", limit=10)
            print(result.estimated_total, result.mode)

        """
        params = query(
            offset=offset, limit=limit, sort=sort, semantic_ratio=semantic_ratio, **filters
        )
        return await self._http.call(
            "POST", "/documents/search", SearchResultPage, params=params, json={"q": words}
        )

    async def places(self, document_id: Id, words: str) -> SearchPlacesOut:
        """Return where the words of a search stand in a document.

        Args:
            document_id: The document.
            words: The search.

        Example::

            places = await lekto.search.places(document_id, "meter number")

        """
        return await self._http.call(
            "POST", f"/documents/{document_id}/search-places", SearchPlacesOut, json={"q": words}
        )

    async def warm(self) -> None:
        """Get the search ready, so that the first search answers fast.

        Example::

            await lekto.search.warm()

        """
        await self._http.call_empty("POST", "/documents/search/warm")

    async def reindex(self) -> None:
        """Rebuild the search index in the background (admins).

        Example::

            await lekto.search.reindex()

        """
        await self._http.call_empty("POST", "/search/reindex")

    async def status(self) -> SearchStatusOut:
        """Return the state of the search index.

        Example::

            status = await lekto.search.status()

        """
        return await self._http.get("/search/status", SearchStatusOut)

    async def check(self) -> IndexCheckOut:
        """Compare the search index with the documents (admins).

        Example::

            check = await lekto.search.check()

        """
        return await self._http.call("POST", "/search/check", IndexCheckOut)
