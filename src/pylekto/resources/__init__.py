"""The areas of Lekto's REST API, one class each; :class:`pylekto.LektoClient` holds them."""

from pylekto.resources.auth import AuthResource
from pylekto.resources.health import HealthResource

__all__ = ["AuthResource", "HealthResource"]
