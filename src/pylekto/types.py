"""Types of the requests that the OpenAPI description gives no model: query filters and parts.

The bodies of most requests are models in :mod:`pylekto.models`; what a request carries in its
query, and the parts of a page edit (sent as form fields), are described here.
"""

from collections.abc import Sequence
from datetime import date
from typing import Literal, NotRequired, TypedDict
from uuid import UUID

from pylekto._unknown import Unknown
from pylekto.models import LaneFilter

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


# The kind of an identifier, such as an IBAN or a customer number.
type IdentifierKind = (
    Literal[
        "iban",
        "vat_id",
        "customer_number",
        "personnel_number",
        "email_domain",
        "tax_id",
        "social_security_number",
        "health_insurance_number",
        "email_address",
        "creditor_id",
        "commercial_register",
        "tax_number",
        "contract_number",
        "meter_number",
        "mandate_reference",
        "license_plate",
        "invoice_number",
        "credit_note_number",
        "order_number",
        "file_reference",
        "our_reference",
        "claim_number",
        "ticket_number",
        "your_reference",
        "letter_date",
        "child_benefit_number",
    ]
    | Unknown
)

# What a tag is for.
type TagScope = Literal["document", "contact", "document_type", "topic"] | Unknown

# Where an open identifier comes from: learned from confirmed documents, or suggested.
type OpenSource = Literal["learned", "suggested"] | Unknown

# Whether a rule acts in every space or in one.
type RuleScope = Literal["global", "space"] | Unknown

# A tab of the inbox.
type InboxTab = Literal["new", "review", "intervene", "processing", "done"] | Unknown

# The outcome of a webhook delivery.
type DeliveryOutcome = Literal["delivered", "retrying", "gave_up", "dropped"] | Unknown

# What became of a mail a mailbox fetched.
type MailOutcome = Literal["taken", "no_rule", "nothing", "known", "too_large", "failed"] | Unknown

# The state of a job.
type JobState = Literal["running", "due", "planned", "done", "failed"] | Unknown

# The way a document came in.
type Channel = Literal["web", "api", "migration", "mail"] | Unknown

# The time an automation report looks back on.
type Period = Literal["30d", "12m", "all"] | Unknown
