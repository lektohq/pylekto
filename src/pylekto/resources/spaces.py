"""``/spaces``: where documents lie, and who may read or edit them there."""

from typing import TYPE_CHECKING

from pydantic import TypeAdapter

from pylekto._http import body, parse, query
from pylekto.models import MemberIn, SpaceCreate, SpaceOut, SpacePatch
from pylekto.resources._base import Resource

if TYPE_CHECKING:
    import builtins

    from pylekto.types import Id

_SPACES = TypeAdapter(list[SpaceOut])


class SpacesResource(Resource):
    """The spaces: each holds documents and grants its members read or edit."""

    async def list(self, *, all_users: bool | None = None) -> builtins.list[SpaceOut]:
        """Return the spaces the caller is a member of, or every space.

        Args:
            all_users: Every space, not only the caller's (admins).

        Example::

            for space in await lekto.spaces.list():
                print(space.name)

        """
        return await self._http.call_as(
            "GET", "/spaces", _SPACES, params=query(all_users=all_users)
        )

    async def create(self, space: SpaceCreate) -> SpaceOut:
        """Create a space, with members if given.

        Args:
            space: The name, a description and the members.

        Example::

            space = await lekto.spaces.create(SpaceCreate(name="Household"))

        """
        return await self._http.call("POST", "/spaces", SpaceOut, json=body(space))

    async def get(self, space_id: Id) -> SpaceOut:
        """Return a space with its members.

        Args:
            space_id: The space.

        Example::

            space = await lekto.spaces.get(space_id)

        """
        return await self._http.get(f"/spaces/{space_id}", SpaceOut)

    async def update(self, space_id: Id, changes: SpacePatch) -> SpaceOut:
        """Rename a space or change its description.

        Args:
            space_id: The space.
            changes: The new name or description.

        Example::

            await lekto.spaces.update(space_id, SpacePatch(name="Family"))

        """
        return await self._http.call("PATCH", f"/spaces/{space_id}", SpaceOut, json=body(changes))

    async def delete(self, space_id: Id) -> None:
        """Delete a space; it must hold no documents.

        Args:
            space_id: The space.

        Example::

            await lekto.spaces.delete(space_id)

        """
        await self._http.call_empty("DELETE", f"/spaces/{space_id}")

    async def set_member(self, space_id: Id, user_id: Id, member: MemberIn) -> SpaceOut:
        """Add a member to a space or change their role.

        Args:
            space_id: The space.
            user_id: The user.
            member: Their role: ``read`` or ``edit``.

        Example::

            await lekto.spaces.set_member(space_id, user_id, MemberIn(role="edit"))

        """
        return await self._http.call(
            "PUT", f"/spaces/{space_id}/members/{user_id}", SpaceOut, json=body(member)
        )

    async def remove_member(self, space_id: Id, user_id: Id) -> SpaceOut | None:
        """Remove a member from a space.

        Args:
            space_id: The space.
            user_id: The user.

        Returns the space, or None if the caller removed themselves and no longer sees it.

        Example::

            await lekto.spaces.remove_member(space_id, user_id)

        """
        response = await self._http.request("DELETE", f"/spaces/{space_id}/members/{user_id}")
        return parse(response, SpaceOut) if response.content else None
