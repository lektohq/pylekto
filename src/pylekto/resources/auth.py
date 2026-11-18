"""``/auth``: who calls. The rest of the area needs a session, which pylekto does not use."""

from pylekto.models import Me
from pylekto.resources._base import Resource


class AuthResource(Resource):
    """Who calls, with which token, on which Lekto."""

    async def me(self) -> Me:
        """Return the caller: the user, the scope of the token and the version of Lekto.

        Example::

            me = await lekto.auth.me()
            print(me.user.username, me.token_scope, me.lekto_version)

        """
        return await self._http.get("/auth/me", Me)
