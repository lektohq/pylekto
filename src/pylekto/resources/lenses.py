"""``/lenses``: the caller's saved views of documents."""

from typing import TYPE_CHECKING

from pydantic import TypeAdapter

from pylekto._http import body
from pylekto.models import LensCreate, LensOrder, LensOut, LensPatch
from pylekto.resources._base import Resource

if TYPE_CHECKING:
    import builtins

    from pylekto.types import Id

_LENSES = TypeAdapter(list[LensOut])


class LensesResource(Resource):
    """The lenses: saved filters, searches and layouts of documents, each user their own."""

    async def list(self) -> builtins.list[LensOut]:
        """Return the caller's lenses, in their order.

        Example::

            names = [lens.name for lens in await lekto.lenses.list()]

        """
        return await self._http.call_as("GET", "/lenses", _LENSES)

    async def create(self, lens: LensCreate) -> LensOut:
        """Create a lens.

        Args:
            lens: The name, filter, search, sort, grouping, layout and card fields.

        Example::

            lens = await lekto.lenses.create(LensCreate(name="To pay", grouping="due"))

        """
        return await self._http.call("POST", "/lenses", LensOut, json=body(lens))

    async def order(self, order: LensOrder) -> builtins.list[LensOut]:
        """Put the caller's lenses in a new order.

        Args:
            order: Each of the caller's lenses once, in the new order.

        Example::

            await lekto.lenses.order(LensOrder(ids=[second.id, first.id]))

        """
        return await self._http.call_as("PUT", "/lenses/order", _LENSES, json=body(order))

    async def get(self, lens_id: Id) -> LensOut:
        """Return a lens.

        Args:
            lens_id: The lens.

        Example::

            lens = await lekto.lenses.get(lens_id)

        """
        return await self._http.get(t"/lenses/{lens_id}", LensOut)

    async def update(self, lens_id: Id, changes: LensPatch) -> LensOut:
        """Change a lens; only the values set in ``changes`` change.

        Args:
            lens_id: The lens.
            changes: The new values.

        Example::

            await lekto.lenses.update(lens_id, LensPatch(name="Bills"))

        """
        return await self._http.call("PATCH", t"/lenses/{lens_id}", LensOut, json=body(changes))

    async def delete(self, lens_id: Id) -> None:
        """Delete a lens.

        Args:
            lens_id: The lens.

        Example::

            await lekto.lenses.delete(lens_id)

        """
        await self._http.call_empty("DELETE", t"/lenses/{lens_id}")
