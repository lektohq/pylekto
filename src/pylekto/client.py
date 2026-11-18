"""The client of one Lekto instance."""

import warnings
from typing import TYPE_CHECKING, Self

import httpx2

from pylekto._http import Http
from pylekto._lekto import LEKTO_VERSION
from pylekto.exceptions import LektoVersionWarning
from pylekto.resources import (
    AuthResource,
    AutomationResource,
    ClassifierResource,
    ContactsResource,
    DocumentsResource,
    DocumentTypesResource,
    ExpectedResource,
    FieldsResource,
    HealthResource,
    IdentifiersResource,
    InboxResource,
    JobsResource,
    LensesResource,
    MailboxesResource,
    MailRulesResource,
    PipelineResource,
    PushResource,
    RelationsResource,
    RulesResource,
    SearchResource,
    SpacesResource,
    TagsResource,
    UsersResource,
    WebhooksResource,
)

if TYPE_CHECKING:
    from types import TracebackType

    from pylekto.models import Me

# Only for the client pylekto makes itself; a client passed in keeps its own settings.
TIMEOUT = httpx2.Timeout(30.0, connect=10.0)


class LektoClient:
    """The client of one Lekto instance, authenticated with an API token.

    pylekto sends requests and reads the answers; it repeats nothing. An error raises a
    :class:`pylekto.LektoError`, and whether to try again is up to the caller.

    Args:
        url: The address of the instance, such as ``https://lekto.example.com``.
        token: A personal API token (``lekto_…``); its scope decides what the client may do.
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
        self.auth = AuthResource(http)
        self.automation = AutomationResource(http)
        self.classifier = ClassifierResource(http)
        self.contacts = ContactsResource(http)
        self.document_types = DocumentTypesResource(http)
        self.documents = DocumentsResource(http)
        self.expected = ExpectedResource(http)
        self.fields = FieldsResource(http)
        self.health = HealthResource(http)
        self.identifiers = IdentifiersResource(http)
        self.inbox = InboxResource(http)
        self.jobs = JobsResource(http)
        self.lenses = LensesResource(http)
        self.mail_rules = MailRulesResource(http)
        self.mailboxes = MailboxesResource(http)
        self.pipeline = PipelineResource(http)
        self.push = PushResource(http)
        self.relations = RelationsResource(http)
        self.rules = RulesResource(http)
        self.search = SearchResource(http)
        self.spaces = SpacesResource(http)
        self.tags = TagsResource(http)
        self.users = UsersResource(http)
        self.webhooks = WebhooksResource(http)
        self.lekto_version: str | None = None

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
        """Ask who calls and compare Lekto's version with the one whose API pylekto speaks.

        Another version gives a :class:`pylekto.LektoVersionWarning`: while Lekto is in beta,
        each release may change its API.

        Example::

            lekto = LektoClient("https://lekto.example.com", "lekto_…")
            me = await lekto.connect()
            print(lekto.lekto_version)

        """
        me = await self.auth.me()
        self.lekto_version = me.lekto_version
        if me.lekto_version != LEKTO_VERSION:
            warnings.warn(
                f"Lekto {me.lekto_version} answers; this pylekto speaks the API of Lekto "
                f"{LEKTO_VERSION}",
                LektoVersionWarning,
                stacklevel=2,
            )
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
