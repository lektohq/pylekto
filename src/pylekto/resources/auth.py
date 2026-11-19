"""``/auth``: who calls. The rest of the area needs a session, which pylekto does not use."""

from pylekto.models import Me
from pylekto.resources._base import Resource


class AuthResource(Resource):
    """Who calls, with which token, on which Lekto."""

    async def me(self) -> Me:
        """Return the caller: the user, the rights of the token, the instance and its versions.

        ``rights`` are what the token may (an admin right only while the user is an active admin);
        ``token_scope`` names the preset they match, or is ``None`` for rights chosen one by one.
        ``instance_id`` stays the same for one Lekto instance.

        Example::

            me = await lekto.auth.me()
            if "documents:upload" not in me.rights:
                print(me.user.username, "may not upload")

        """
        return await self._http.get("/auth/me", Me)
