"""The areas of Lekto's REST API, one class each; :class:`pylekto.LektoClient` holds them."""

from pylekto.resources.auth import AuthResource
from pylekto.resources.documents import DocumentsResource
from pylekto.resources.health import HealthResource
from pylekto.resources.identifiers import IdentifiersResource
from pylekto.resources.inbox import ExpectedResource, InboxResource
from pylekto.resources.lenses import LensesResource
from pylekto.resources.master_data import (
    ContactsResource,
    DocumentTypesResource,
    FieldsResource,
    TagsResource,
)
from pylekto.resources.relations import RelationsResource
from pylekto.resources.rules import RulesResource
from pylekto.resources.search import SearchResource
from pylekto.resources.spaces import SpacesResource
from pylekto.resources.users import UsersResource

__all__ = [
    "AuthResource",
    "ContactsResource",
    "DocumentTypesResource",
    "DocumentsResource",
    "ExpectedResource",
    "FieldsResource",
    "HealthResource",
    "IdentifiersResource",
    "InboxResource",
    "LensesResource",
    "RelationsResource",
    "RulesResource",
    "SearchResource",
    "SpacesResource",
    "TagsResource",
    "UsersResource",
]
