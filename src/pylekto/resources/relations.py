"""``/documents/{id}/relations``: which documents belong together."""

from typing import TYPE_CHECKING

from pylekto.models import RelationsOut
from pylekto.resources._base import Resource

if TYPE_CHECKING:
    from pylekto.types import Id


class RelationsResource(Resource):
    """The relations of documents: what a document refers to, what refers to it, suggestions."""

    async def get(self, document_id: Id) -> RelationsOut:
        """Return the relations of a document.

        Args:
            document_id: The document.

        Example::

            relations = await lekto.relations.get(document_id)
            print([related.title for related in relations.refers_to])

        """
        return await self._http.get(t"/documents/{document_id}/relations", RelationsOut)

    async def add(self, document_id: Id, other_id: Id) -> RelationsOut:
        """Relate a document with another.

        Args:
            document_id: The document.
            other_id: The document it relates to.

        Example::

            relations = await lekto.relations.add(invoice_id, order_id)

        """
        return await self._http.call(
            "POST",
            t"/documents/{document_id}/relations",
            RelationsOut,
            json={"document_id": str(other_id)},
        )

    async def remove(self, document_id: Id, other_id: Id) -> RelationsOut:
        """Remove the relation between two documents.

        Args:
            document_id: The document.
            other_id: The document it related to.

        Example::

            relations = await lekto.relations.remove(invoice_id, order_id)

        """
        return await self._http.call(
            "DELETE", t"/documents/{document_id}/relations/{other_id}", RelationsOut
        )
