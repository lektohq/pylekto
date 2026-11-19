"""``/version``: which Lekto answers, and whether a newer one is out."""

from pylekto.models import VersionOut
from pylekto.resources._base import Resource


class VersionResource(Resource):
    """The versions of Lekto and of its API, and the newest release."""

    async def get(self) -> VersionOut:
        """Return the versions of Lekto and its API, and whether a newer Lekto is out.

        Needs the right ``system:read``. Unless ``LEKTO_UPDATE_CHECK`` turns it off
        (``update_check``), Lekto looks for its releases on GitHub once an hour; ``latest`` is the
        newest one that was news at the last look (``checked_at``).

        Example::

            version = await lekto.version.get()
            if version.update_available and version.latest is not None:
                print(version.latest.version, version.latest.url)

        """
        return await self._http.get("/version", VersionOut)
