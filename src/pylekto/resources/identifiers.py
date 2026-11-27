"""``/identifiers``: references to values, and where an identifier stands."""

from typing import TYPE_CHECKING

from pylekto._http import body
from pylekto.models import PlacesOut, RefIn, RefOut
from pylekto.resources._base import Resource

if TYPE_CHECKING:
    from pylekto.models import IdentifierKind


class IdentifiersResource(Resource):
    """References to values (IBANs, customer numbers …), and where an identifier stands.

    A value from a document never goes in an address: a reference (``ref``) stands for it. The
    identifiers no person has confirmed yet are in :class:`OpenIdentifiersResource`.
    """

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
        return await self._http.get(t"/identifiers/refs/{kind}/{ref}", RefOut)

    async def places(self, kind: IdentifierKind, ref: str) -> PlacesOut:
        """Return where an identifier stands: contacts, documents, profiles.

        Args:
            kind: Its kind.
            ref: The reference to its value.

        Example::

            places = await lekto.identifiers.places("iban", ref)

        """
        return await self._http.get(t"/identifiers/places/{kind}/{ref}", PlacesOut)
