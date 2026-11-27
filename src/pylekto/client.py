"""The client of one Lekto instance."""

import json
import re
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Self

from pylekto._http import Http, new_client, parse
from pylekto._lekto import API_VERSION, LEKTO_VERSION
from pylekto.exceptions import LektoResponseError, LektoVersionWarning
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

    import httpx2

# ASCII and bounded: int() refuses over 4300 digits, and \d also takes other scripts.
_API_VERSION = re.compile(r"([0-9]{1,9})\.([0-9]{1,9})")

# The warning names the caller's line, also through ``async with`` (``__aenter__``).
_PACKAGE = (str(Path(__file__).parent),)

type ApiFit = Literal["fits", "newer", "older", "unknown"]


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
        self._client = new_client() if client is None else client
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

        A version of the API that does not fit (:func:`pylekto.api_fit`) gives a
        :class:`pylekto.LektoVersionWarning`; so does a Lekto that names no version of its API
        (before 0.16).

        Example::

            lekto = LektoClient("https://lekto.example.com", "lekto_…")
            me = await lekto.connect()
            print(lekto.lekto_version, lekto.api_version)

        """
        response = await self._http.request("GET", "/auth/me")
        try:
            me = parse(response, Me)
        except LektoResponseError:
            # A Lekto without an API version does not fit the model: warn from what it sent.
            sent = _texts(response)
            _warn_unless_fit(sent.get("api_version"), sent.get("lekto_version"))
            raise
        _warn_unless_fit(me.api_version, me.lekto_version)
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


def _texts(response: httpx2.Response) -> dict[str, str]:
    """Return the text fields of a JSON answer; none of an answer that is no object."""
    try:
        body = json.loads(response.content)
    except ValueError:
        return {}
    if not isinstance(body, dict):
        return {}
    return {name: value for name, value in body.items() if isinstance(value, str)}


def _warn_unless_fit(answered: str | None, lekto: str | None) -> None:
    """Warn that Lekto's API may differ from pylekto's, naming both, unless it fits."""
    if api_fit(answered) == "fits":
        return
    who = f"Lekto {lekto}" if lekto else "Lekto"
    api = f"the API {answered}" if answered else "no API version"
    warnings.warn(
        f"{who} answers with {api}; this pylekto speaks the API {API_VERSION} "
        f"of Lekto {LEKTO_VERSION}",
        LektoVersionWarning,
        skip_file_prefixes=_PACKAGE,
    )


def api_fit(api_version: str | None) -> ApiFit:
    """Tell whether a version of Lekto's API fits :data:`pylekto.API_VERSION`, and if not, how.

    During the beta (``0.x``) only the same MINOR fits; from ``1.0`` on the same MAJOR with at
    least pylekto's MINOR. ``"newer"``: Lekto speaks a newer API, pylekto needs an update.
    ``"older"``: Lekto speaks an older API, Lekto needs an update. ``"unknown"``: no version or
    one pylekto cannot read, such as from a Lekto before 0.16.

    Args:
        api_version: The version of Lekto's API, such as :attr:`LektoClient.api_version` or
            ``api_version`` of ``GET /auth/me``.

    Example::

        match api_fit(lekto.api_version):
            case "newer":
                print("Update pylekto")
            case "older":
                print("Update Lekto")

    """
    return _fit(api_version, API_VERSION)


def _fit(answered: str | None, spoken: str) -> ApiFit:
    """Compare against ``spoken`` so the tests reach the rules from 1.0 on.

    During the beta every change raises MINOR, breaking or not; from 1.0 on a breaking one raises
    MAJOR (.knowledge/open/api-version-fas.md).
    """
    server = _API_VERSION.fullmatch(answered or "")
    ours = _API_VERSION.fullmatch(spoken)
    if server is None or ours is None:
        return "unknown"
    theirs = (int(server[1]), int(server[2]))
    mine = (int(ours[1]), int(ours[2]))
    if theirs[0] == 0 or mine[0] == 0:
        fits = theirs == mine
    else:
        fits = theirs[0] == mine[0] and theirs[1] >= mine[1]
    if fits:
        return "fits"
    return "newer" if theirs > mine else "older"
