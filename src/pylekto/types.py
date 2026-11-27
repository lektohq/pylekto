"""Types of the requests that the OpenAPI description gives no model: query filters and parts.

The bodies of most requests are models in :mod:`pylekto.models`; what a request carries in its
query, and the parts of a page edit (sent as form fields), are described here.
"""

from collections.abc import Sequence
from datetime import date
from typing import Literal, NotRequired, TypedDict
from uuid import UUID

from pylekto.models import (
    Channel,
    DeliveryOutcome,
    IdentifierKind,
    InboxTab,
    JobState,
    LaneFilter,
    MailOutcome,
    OpenSource,
    Period,
)

# The id of an object: a UUID, or its text.
type Id = UUID | str


class DocumentFilter(TypedDict, total=False):
    """Which documents the stream, a search or a change of many documents takes.

    Every key narrows the documents; values in a list mean any of them. A list, its count and
    its facets take a :class:`ListedFilter`, which adds to it.

    Example::

        async for document in lekto.documents.list(lane=["red"], document_type_id=[invoices]):
            print(document.title)

    """

    all_users: bool
    """Every user's documents instead of the caller's reach (admins)."""
    ids: Sequence[str]
    """Documents by id: the whole id, or its end of at least 8 characters."""
    contact_id: Sequence[Id]
    document_type_id: Sequence[Id]
    tag_id: Sequence[Id]
    space_id: Sequence[Id]
    lane: Sequence[LaneFilter]
    field_id: Id
    """Documents that have a value for this field."""
    contact_group_id: Sequence[Id]
    document_type_group_id: Sequence[Id]
    topic_id: Sequence[Id]
    document_date_from: date
    document_date_to: date
    fact: Sequence[str]
    """Facts the document has, as ``kind:ref:role`` (``ref`` from ``identifiers.ref``)."""


class ListedFilter(DocumentFilter, total=False):
    """Which documents a list, its count or its facets take: a :class:`DocumentFilter` and more.

    The stream, the search and a change of many documents do not take ``in_inbox``.

    Example::

        inbox = await lekto.documents.count(in_inbox=True)
        print(inbox.total)

    """

    in_inbox: bool
    """Documents open in the caller's inbox (``True``) or not (``False``), as each document's
    ``in_inbox`` marks them and ``GET /inbox/summary`` counts them: in processing, to review, to
    intervene, or new and not seen by the caller since; in the spaces the caller edits, with
    ``all_users`` in every user's inbox, with the caller's own seen marks."""


class InboxFilter(TypedDict, total=False):
    """Which documents of the inbox a list takes.

    Example::

        async for item in lekto.inbox.list(tab="review", all_users=True):
            print(item.document.title)

    """

    tab: InboxTab
    """The tab; default: everything open."""
    all_users: bool
    """Every user's inbox (admins)."""


class OpenIdentifierFilter(TypedDict, total=False):
    """Which open identifiers a list or a search takes.

    Example::

        page = await lekto.open_identifiers.page(kind="iban", recommended=True)

    """

    source: OpenSource
    """Only those learned from confirmed documents, or only suggested ones."""
    kind: IdentifierKind
    """Only identifiers of this kind."""
    recommended: bool
    """Only those their documents recommend for a contact."""


class JobFilter(TypedDict, total=False):
    """Which jobs a list takes.

    Example::

        async for job in lekto.jobs.list(state=["failed"], kind="pipeline.node"):
            print(job.error)

    """

    state: Sequence[JobState]
    """Only jobs in these states."""
    kind: str
    """Only jobs of this kind, such as ``pipeline.node``."""


class MailFilter(TypedDict, total=False):
    """Which mails of a mailbox's log a list takes.

    Example::

        page = await lekto.mailboxes.mails_page(mailbox_id, outcome=["failed"])

    """

    outcome: Sequence[MailOutcome]
    """Only mails with these outcomes."""
    rule_id: Id
    """Only mails this mail rule took."""


class DeliveryFilter(TypedDict, total=False):
    """Which deliveries of a webhook's log a list takes.

    Example::

        page = await lekto.webhooks.deliveries_page(webhook_id, outcome=["gave_up"])

    """

    outcome: Sequence[DeliveryOutcome]
    """Only deliveries with these outcomes."""
    event_type: str
    """Only deliveries of this event."""


class AutomationFilter(TypedDict, total=False):
    """Which documents a report of the automation looks at.

    Example::

        report = await lekto.automation.get(channel=["mail"], period="30d", tz="Europe/Berlin")

    """

    channel: Sequence[Channel]
    """Only documents that came in these ways."""
    period: Period
    """The time to look back on."""
    tz: str
    """The IANA time zone the days and months begin in."""


class DocumentCounts(TypedDict, total=False):
    """Whether a list of master data counts the documents of each item.

    Example::

        for contact in await lekto.contacts.list(document_counts=True):
            print(contact.name, contact.document_count)

    """

    document_counts: bool
    """Count the documents of each item."""
    all_users: bool
    """Count every user's documents, not only the caller's reach (admins)."""


class PagePick(TypedDict):
    """One page of a part of a page edit."""

    page: int
    """The page of the source, from 1; an image's frames."""
    source: NotRequired[int]
    """0 (the default): the document's original; 1, 2, …: the files sent along, then the
    originals of the other documents, in their order."""
    rotate: NotRequired[Literal[0, 90, 180, 270]]
    """Degrees clockwise, beyond how the page is shown now."""


class EditPart(TypedDict):
    """One part of a page edit: its pages, and whether it replaces the document."""

    pages: Sequence[PagePick]
    """Its pages in their order; each page goes in one part at most."""
    replaces: NotRequired[bool]
    """It becomes the document's next version; every other part becomes a new document."""
