"""Types of the requests that the OpenAPI description gives no model: query filters and parts.

The bodies of most requests are models in :mod:`pylekto.models`; what a request carries in its
query, and the parts of a page edit (sent as form fields), are described here.
"""

from collections.abc import Sequence
from datetime import date
from typing import Literal, NotRequired, TypedDict
from uuid import UUID

from pylekto.models import LaneFilter

# The id of an object: a UUID, or its text.
type Id = UUID | str


class DocumentFilter(TypedDict, total=False):
    """Which documents a list, a count, a search or a change of many documents takes.

    Every key narrows the documents; values in a list mean any of them.

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
