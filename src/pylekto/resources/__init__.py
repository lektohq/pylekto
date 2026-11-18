"""The areas of Lekto's REST API, one class each; :class:`pylekto.LektoClient` holds them."""

from pylekto.resources.auth import AuthResource
from pylekto.resources.documents import DocumentsResource
from pylekto.resources.health import HealthResource
from pylekto.resources.relations import RelationsResource
from pylekto.resources.search import SearchResource

__all__ = [
    "AuthResource",
    "DocumentsResource",
    "HealthResource",
    "RelationsResource",
    "SearchResource",
]
