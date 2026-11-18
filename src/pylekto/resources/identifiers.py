"""``/identifiers``: identifiers that belong to no contact yet, and references to values."""

from typing import TYPE_CHECKING

from pydantic import TypeAdapter

from pylekto._http import body, query
from pylekto.models import (
    OpenCountsOut,
    OpenDecisionsIn,
    OpenDetailOut,
    OpenPageOut,
    OutcomeOut,
    PlacesOut,
    RefIn,
    RefOut,
)
from pylekto.resources._base import Resource

if TYPE_CHECKING:
    import builtins

    from pylekto.types import IdentifierKind, OpenSource

_OUTCOMES = TypeAdapter(list[OutcomeOut])


class IdentifiersResource(Resource):
    """Open identifiers (IBANs, customer numbers … not yet at a contact) and value references.

    A value from a document never goes in an address: a reference (``ref``) stands for it.
    """

    async def open(
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

            page = await lekto.identifiers.open(kind="iban", limit=20)
            print(page.total, [item.value for item in page.items])

        """
        params = query(
            source=source, kind=kind, recommended=recommended, offset=offset, limit=limit
        )
        return await self._http.get("/identifiers/open", OpenPageOut, params=params)

    async def search_open(
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

            page = await lekto.identifiers.search_open("Muster")

        """
        params = query(
            source=source, kind=kind, recommended=recommended, offset=offset, limit=limit
        )
        return await self._http.call(
            "POST", "/identifiers/open/search", OpenPageOut, params=params, json={"q": words}
        )

    async def open_summary(self) -> OpenCountsOut:
        """Count the open identifiers.

        Example::

            counts = await lekto.identifiers.open_summary()

        """
        return await self._http.get("/identifiers/open/summary", OpenCountsOut)

    async def open_identifier(self, kind: IdentifierKind, ref: str) -> OpenDetailOut:
        """Return an open identifier and where it stands.

        Args:
            kind: Its kind.
            ref: The reference to its value.

        Example::

            detail = await lekto.identifiers.open_identifier("iban", ref)

        """
        return await self._http.get(f"/identifiers/open/{kind}/{ref}", OpenDetailOut)

    async def decide(self, decisions: OpenDecisionsIn) -> builtins.list[OutcomeOut]:
        """Confirm open identifiers at a contact, or reject them.

        Args:
            decisions: What to do with which identifier.

        Example::

            outcomes = await lekto.identifiers.decide(decisions)

        """
        return await self._http.call_as(
            "POST", "/identifiers/open/decisions", _OUTCOMES, json=body(decisions)
        )

    async def confirm_recommended(self) -> builtins.list[OutcomeOut]:
        """Confirm every open identifier its documents recommend for a contact.

        Example::

            outcomes = await lekto.identifiers.confirm_recommended()

        """
        return await self._http.call_as("POST", "/identifiers/open/recommended", _OUTCOMES)

    async def ref(self, value: RefIn) -> RefOut:
        """Return the reference that stands for a value in addresses and filters.

        Args:
            value: The kind and the value, as typed or as a document shows it.

        Example::

            ref = await lekto.identifiers.ref(RefIn(kind="iban", value=iban))
            documents = lekto.documents.list(fact=[f"iban:{ref.ref}:contact"])

        """
        return await self._http.call("POST", "/identifiers/refs", RefOut, json=body(value))

    async def value(self, kind: IdentifierKind, ref: str) -> RefOut:
        """Return the value a reference stands for.

        Args:
            kind: Its kind.
            ref: The reference.

        Example::

            value = await lekto.identifiers.value("iban", ref)

        """
        return await self._http.get(f"/identifiers/refs/{kind}/{ref}", RefOut)

    async def places(self, kind: IdentifierKind, ref: str) -> PlacesOut:
        """Return where an identifier stands: contacts, documents, profiles.

        Args:
            kind: Its kind.
            ref: The reference to its value.

        Example::

            places = await lekto.identifiers.places("iban", ref)

        """
        return await self._http.get(f"/identifiers/places/{kind}/{ref}", PlacesOut)
