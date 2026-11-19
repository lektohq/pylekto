"""``/identifiers/open``: identifiers that belong to no contact yet, to confirm or reject."""

from typing import TYPE_CHECKING

from pydantic import TypeAdapter

from pylekto._http import body, query, total_items
from pylekto.models import (
    OpenCountsOut,
    OpenDecisionsIn,
    OpenDetailOut,
    OpenIdentifierOut,
    OpenPageOut,
    OutcomeOut,
)
from pylekto.resources._base import Resource

if TYPE_CHECKING:
    import builtins
    from collections.abc import AsyncIterator

    from pylekto.types import IdentifierKind, OpenSource

_OUTCOMES = TypeAdapter(list[OutcomeOut])


class OpenIdentifiersResource(Resource):
    """Open identifiers: IBANs, customer numbers … that no person has confirmed at a contact yet.

    A value from a document never goes in an address: a reference (``ref``) stands for it.
    """

    def list(
        self,
        *,
        source: OpenSource | None = None,
        kind: IdentifierKind | None = None,
        recommended: bool | None = None,
        page_size: int | None = None,
    ) -> AsyncIterator[OpenIdentifierOut]:
        """Iterate over every open identifier, page after page.

        Args:
            source: Only those learned from confirmed documents, or only suggested ones.
            kind: Only identifiers of this kind.
            recommended: Only those their documents recommend for a contact.
            page_size: How many identifiers each request fetches.

        Example::

            async for item in lekto.open_identifiers.list(kind="iban"):
                print(item.value, item.documents)

        """

        async def fetch(offset: int) -> OpenPageOut:
            return await self.page(
                source=source, kind=kind, recommended=recommended, offset=offset, limit=page_size
            )

        return total_items(fetch)

    async def page(
        self,
        *,
        source: OpenSource | None = None,
        kind: IdentifierKind | None = None,
        recommended: bool | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> OpenPageOut:
        """Return a page of the open identifiers, with their counts.

        Args:
            source: Only those learned from confirmed documents, or only suggested ones.
            kind: Only identifiers of this kind.
            recommended: Only those their documents recommend for a contact.
            offset: Skip so many.
            limit: How many the page holds at most.

        Example::

            page = await lekto.open_identifiers.page(kind="iban", limit=20)
            print(page.total, [item.value for item in page.items])

        """
        params = query(
            source=source, kind=kind, recommended=recommended, offset=offset, limit=limit
        )
        return await self._http.get("/identifiers/open", OpenPageOut, params=params)

    async def search(
        self,
        words: str,
        *,
        source: OpenSource | None = None,
        kind: IdentifierKind | None = None,
        recommended: bool | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> OpenPageOut:
        """Find open identifiers by words (in the body, never in the address).

        Args:
            words: What to look for in the value, the holder or the documents.
            source: Only those learned from confirmed documents, or only suggested ones.
            kind: Only identifiers of this kind.
            recommended: Only those their documents recommend for a contact.
            offset: Skip so many.
            limit: How many the page holds at most.

        Example::

            page = await lekto.open_identifiers.search("Muster")

        """
        params = query(
            source=source, kind=kind, recommended=recommended, offset=offset, limit=limit
        )
        return await self._http.call(
            "POST", "/identifiers/open/search", OpenPageOut, params=params, json={"q": words}
        )

    async def summary(self) -> OpenCountsOut:
        """Count the open identifiers.

        Example::

            counts = await lekto.open_identifiers.summary()

        """
        return await self._http.get("/identifiers/open/summary", OpenCountsOut)

    async def get(self, kind: IdentifierKind, ref: str) -> OpenDetailOut:
        """Return an open identifier and where it stands.

        Args:
            kind: Its kind.
            ref: The reference to its value.

        Example::

            detail = await lekto.open_identifiers.get("iban", ref)

        """
        return await self._http.get(f"/identifiers/open/{kind}/{ref}", OpenDetailOut)

    async def decide(self, decisions: OpenDecisionsIn) -> builtins.list[OutcomeOut]:
        """Confirm open identifiers at a contact, or reject them.

        Args:
            decisions: What to do with which identifier.

        Example::

            outcomes = await lekto.open_identifiers.decide(decisions)

        """
        return await self._http.call_as(
            "POST", "/identifiers/open/decisions", _OUTCOMES, json=body(decisions)
        )

    async def confirm_recommended(self) -> builtins.list[OutcomeOut]:
        """Confirm every open identifier its documents recommend for a contact.

        Example::

            outcomes = await lekto.open_identifiers.confirm_recommended()

        """
        return await self._http.call_as("POST", "/identifiers/open/recommended", _OUTCOMES)
