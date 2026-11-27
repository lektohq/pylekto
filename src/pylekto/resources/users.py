"""``/users``: the users of the installation and their profiles (admins)."""

from typing import TYPE_CHECKING

from pydantic import TypeAdapter

from pylekto._http import body
from pylekto.models import (
    AccountOut,
    ProfileOut,
    ProfilePatch,
    UserCreate,
    UserOut,
    UserPatch,
    UserRemovalOut,
)
from pylekto.resources._base import Resource

if TYPE_CHECKING:
    import builtins

    from pylekto.types import Id

_USERS = TypeAdapter(list[UserOut])
_USER = TypeAdapter(AccountOut | UserOut)


class UsersResource(Resource):
    """The users: who may sign in, with which role, and their profiles.

    Creating a user with a password or the role admin, resetting a sign-in and deleting a user
    need a session; pylekto works with tokens only and leaves them out.
    """

    async def list(self) -> builtins.list[UserOut]:
        """Return every user.

        Example::

            for user in await lekto.users.list():
                print(user.username, user.role)

        """
        return await self._http.call_as("GET", "/users", _USERS)

    async def create(self, user: UserCreate) -> UserOut:
        """Create a user without a password (one who signs in through the identity provider).

        Args:
            user: The username, the display name and the role.

        Example::

            jane = await lekto.users.create(UserCreate(username="jane", display_name="Jane Doe"))

        """
        return await self._http.call("POST", "/users", UserOut, json=body(user))

    async def get(self, user_id: Id) -> AccountOut | UserOut:
        """Return a user; an admin also sees the account (sign-in, second factor, links).

        Args:
            user_id: The user.

        Example::

            user = await lekto.users.get(user_id)

        """
        return await self._http.call_as("GET", t"/users/{user_id}", _USER)

    async def update(self, user_id: Id, changes: UserPatch) -> UserOut:
        """Change a user's role or whether they are active.

        Args:
            user_id: The user.
            changes: The new role or state.

        Example::

            await lekto.users.update(user_id, UserPatch(active=False))

        """
        return await self._http.call("PATCH", t"/users/{user_id}", UserOut, json=body(changes))

    async def profile(self, user_id: Id) -> ProfileOut:
        """Return a user's profile: names, birth date, identifiers, numbers.

        Args:
            user_id: The user.

        Example::

            profile = await lekto.users.profile(user_id)

        """
        return await self._http.get(t"/users/{user_id}/profile", ProfileOut)

    async def update_profile(self, user_id: Id, changes: ProfilePatch) -> ProfileOut:
        """Change a user's profile; only the values set in ``changes`` change.

        Args:
            user_id: The user.
            changes: The new values.

        Example::

            await lekto.users.update_profile(user_id, ProfilePatch(display_name="Jane Doe"))

        """
        return await self._http.call(
            "PATCH", t"/users/{user_id}/profile", ProfileOut, json=body(changes)
        )

    async def removal(self, user_id: Id) -> UserRemovalOut:
        """Return what stops deleting a user, and what deleting them would take with them.

        Args:
            user_id: The user.

        Example::

            removal = await lekto.users.removal(user_id)

        """
        return await self._http.get(t"/users/{user_id}/removal", UserRemovalOut)
