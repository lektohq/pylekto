"""The client of one Lekto instance."""

import json
import re
import warnings
from typing import TYPE_CHECKING, Self

import httpx2

from pylekto._http import TIMEOUT, Http, parse
from pylekto._lekto import API_VERSION, LEKTO_VERSION
from pylekto.exceptions import LektoVersionWarning
from pylekto.models import Me
from pylekto.resources import (
    AuthResource,
    AutomationResource,
    ClassifierResource,
    ContactsResource,
    DocumentsResource,
    DocumentTypesResource,
    EventsResource,
    ExpectedResource,
    FieldsResource,
    HealthResource,
    IdentifiersResource,
    InboxResource,
    JobsResource,
    LensesResource,
    MailboxesResource,
    MailRulesResource,
    OpenIdentifiersResource,
    PipelineResource,
    PushResource,
    RelationsResource,
    RulesResource,
    SearchResource,
    SpacesResource,
    TagsResource,
    UsersResource,
    VersionResource,
    WebhooksResource,
)

if TYPE_CHECKING:
    from types import TracebackType

_API_VERSION = re.compile(r"(\d+)\.(\d+)")


class LektoClient:
    """The client of one Lekto instance, authenticated with an API token.

    pylekto sends requests and reads the answers; it repeats nothing. An error raises a
    :class:`pylekto.LektoError`, and whether to try again is up to the caller.

    Args:
        url: The address of the instance, such as ``https://lekto.example.com``.
        token: A personal API token (``lekto_…``); its rights decide what the client may do.
        client: An httpx2 client to send the requests with, such as one the application shares.
            pylekto never closes it. Without one, pylekto makes its own and closes it in
            :meth:`close`.

    Example::

        async with LektoClient("https://lekto.example.com", "lekto_…") as lekto:
            me = await lekto.auth.me()
            print(me.user.username)

    """

    def __init__(self, url: str, token: str, *, client: httpx2.AsyncClient | None = None) -> None:
        """Prepare the client; nothing is sent before the first request."""
        self._own_client = client is None
        self._client = httpx2.AsyncClient(timeout=TIMEOUT) if client is None else client
        http = Http(url, token, self._client)
        self._http = http
        self.auth = AuthResource(http)
        self.automation = AutomationResource(http)
        self.classifier = ClassifierResource(http)
        self.contacts = ContactsResource(http)
        self.document_types = DocumentTypesResource(http)
        self.documents = DocumentsResource(http)
        self.events = EventsResource(http)
        self.expected = ExpectedResource(http)
        self.fields = FieldsResource(http)
        self.health = HealthResource(http)
        self.identifiers = IdentifiersResource(http)
        self.inbox = InboxResource(http)
        self.jobs = JobsResource(http)
        self.lenses = LensesResource(http)
        self.mail_rules = MailRulesResource(http)
        self.mailboxes = MailboxesResource(http)
        self.open_identifiers = OpenIdentifiersResource(http)
        self.pipeline = PipelineResource(http)
        self.push = PushResource(http)
        self.relations = RelationsResource(http)
        self.rules = RulesResource(http)
        self.search = SearchResource(http)
        self.spaces = SpacesResource(http)
        self.tags = TagsResource(http)
        self.users = UsersResource(http)
        self.version = VersionResource(http)
        self.webhooks = WebhooksResource(http)
        self.lekto_version: str | None = None
        self.api_version: str | None = None

    async def __aenter__(self) -> Self:
        """Connect (:meth:`connect`); a failure closes the client again."""
        try:
            await self.connect()
        except BaseException:
            await self.close()
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the client (:meth:`close`)."""
        await self.close()

    async def connect(self) -> Me:
        """Ask who calls and compare the version of Lekto's API with the one pylekto speaks.

        A version whose requests or answers may differ gives a
        :class:`pylekto.LektoVersionWarning`: during the beta (``0.x``) every other MINOR than
        :data:`pylekto.API_VERSION`, from ``1.0`` on another MAJOR or a smaller MINOR; so does a
        Lekto that names no version of its API (before 0.16).

        Example::

            lekto = LektoClient("https://lekto.example.com", "lekto_…")
            me = await lekto.connect()
            print(lekto.lekto_version, lekto.api_version)

        """
        response = await self._http.request("GET", "/auth/me")
        # Read before the model, which a Lekto without an API version does not fit.
        answered = _field(response, "api_version")
        if answered is None or not _fits(answered, API_VERSION):
            lekto = _field(response, "lekto_version")
            who = f"Lekto {lekto}" if lekto else "Lekto"
            api = f"the API {answered}" if answered else "no API version"
            warnings.warn(
                f"{who} answers with {api}; this pylekto speaks the API {API_VERSION} "
                f"of Lekto {LEKTO_VERSION}",
                LektoVersionWarning,
                stacklevel=2,
            )
        me = parse(response, Me)
        self.lekto_version = me.lekto_version
        self.api_version = me.api_version
        return me

    async def close(self) -> None:
        """Close the httpx2 client pylekto made; one passed in stays open.

        Example::

            lekto = LektoClient("https://lekto.example.com", "lekto_…")
            try:
                health = await lekto.health.get()
            finally:
                await lekto.close()

        """
        if self._own_client:
            await self._client.aclose()


def _field(response: httpx2.Response, name: str) -> str | None:
    """Return a text field of a JSON answer, or None where it has none."""
    try:
        body = json.loads(response.content)
    except ValueError:
        return None
    value = body.get(name) if isinstance(body, dict) else None
    return value if isinstance(value, str) else None


def _fits(answered: str, spoken: str) -> bool:
    """Whether the API ``answered`` takes pylekto's requests and sends what its models read.

    During the beta every change raises MINOR, breaking or not; from 1.0 on a breaking one raises
    MAJOR (.knowledge/open/api-version-fas.md).
    """
    server = _API_VERSION.fullmatch(answered)
    ours = _API_VERSION.fullmatch(spoken)
    if server is None or ours is None:
        return False
    major, minor = int(server[1]), int(server[2])
    our_major, our_minor = int(ours[1]), int(ours[2])
    if major == 0 or our_major == 0:
        return (major, minor) == (our_major, our_minor)
    return major == our_major and minor >= our_minor
