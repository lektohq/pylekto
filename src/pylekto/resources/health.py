"""``/health``: whether Lekto and the services behind it work."""

from http import HTTPStatus

from pylekto.models import Health
from pylekto.resources._base import Resource


class HealthResource(Resource):
    """The health of Lekto."""

    async def get(self) -> Health:
        """Return the state of the API and of each service it needs.

        A Lekto that is not healthy answers 503 with the same body, so this returns it as well.

        Example::

            health = await lekto.health.get()
            if health.status != "ok":
                print({name: state for name, state in health.checks.items() if state != "ok"})

        """
        return await self._http.get("/health", Health, accept={HTTPStatus.SERVICE_UNAVAILABLE})
