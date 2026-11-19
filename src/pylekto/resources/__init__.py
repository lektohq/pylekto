"""The areas of Lekto's REST API, one class each; :class:`pylekto.LektoClient` holds them."""

from pylekto.resources.auth import AuthResource
from pylekto.resources.documents import DocumentsResource
from pylekto.resources.events import EventsResource
from pylekto.resources.health import HealthResource
from pylekto.resources.identifiers import IdentifiersResource
from pylekto.resources.inbox import ExpectedResource, InboxResource
from pylekto.resources.lenses import LensesResource
from pylekto.resources.mail import MailboxesResource, MailRulesResource
from pylekto.resources.master_data import (
    ContactsResource,
    DocumentTypesResource,
    FieldsResource,
    TagsResource,
)
from pylekto.resources.open_identifiers import OpenIdentifiersResource
from pylekto.resources.operations import (
    AutomationResource,
    ClassifierResource,
    JobsResource,
    PipelineResource,
    PushResource,
)
from pylekto.resources.relations import RelationsResource
from pylekto.resources.rules import RulesResource
from pylekto.resources.search import SearchResource
from pylekto.resources.spaces import SpacesResource
from pylekto.resources.users import UsersResource
from pylekto.resources.version import VersionResource
from pylekto.resources.webhooks import WebhooksResource

__all__ = [
    "AuthResource",
    "AutomationResource",
    "ClassifierResource",
    "ContactsResource",
    "DocumentTypesResource",
    "DocumentsResource",
    "EventsResource",
    "ExpectedResource",
    "FieldsResource",
    "HealthResource",
    "IdentifiersResource",
    "InboxResource",
    "JobsResource",
    "LensesResource",
    "MailRulesResource",
    "MailboxesResource",
    "OpenIdentifiersResource",
    "PipelineResource",
    "PushResource",
    "RelationsResource",
    "RulesResource",
    "SearchResource",
    "SpacesResource",
    "TagsResource",
    "UsersResource",
    "VersionResource",
    "WebhooksResource",
]
