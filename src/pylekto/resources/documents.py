"""``/documents``: the documents, their files, text, facts and processing."""

import json
from typing import TYPE_CHECKING, Any, Literal, Unpack

from pydantic import TypeAdapter

from pylekto._http import Part, Upload, body, cursor_items, query
from pylekto.models import (
    BulkOperationOut,
    BulkRequest,
    ConfirmRequest,
    DocumentAccepted,
    DocumentChanged,
    DocumentCountOut,
    DocumentDetails,
    DocumentFacetsOut,
    DocumentFilesOut,
    DocumentListSort,
    DocumentOutOfReach,
    DocumentPage,
    DocumentPatch,
    DocumentPreviewOut,
    DocumentTextOut,
    EditedDocuments,
    ExchangeNode,
    FactDecisionIn,
    FactsOut,
    ListedDocument,
    LogEntry,
    OriginOut,
    PagePreviews,
    PlaceOut,
    ReadingOut,
    ReprocessRequest,
    ReviewOut,
    RunExchangeOut,
    StreamOut,
)
from pylekto.resources._base import Resource

if TYPE_CHECKING:
    import builtins
    from collections.abc import AsyncIterator, Mapping, Sequence

    from pylekto.types import DocumentFilter, EditPart, Id

# Lekto recognises a file by its content, not by the type a client names.
FILE_TYPE = "application/octet-stream"

_CHANGED = TypeAdapter(DocumentChanged | DocumentOutOfReach)
_CONFIRMED = TypeAdapter(DocumentDetails | DocumentOutOfReach)
_LOG = TypeAdapter(list[LogEntry])
_EXCHANGES = TypeAdapter(list[RunExchangeOut])
_STRUCTURE = TypeAdapter(dict[str, Any])


class DocumentsResource(Resource):
    """The documents the token's user may see, and what Lekto read in them."""

    def list(
        self,
        *,
        sort: DocumentListSort | None = None,
        sort_field_id: Id | None = None,
        page_size: int | None = None,
        **filters: Unpack[DocumentFilter],
    ) -> AsyncIterator[ListedDocument]:
        """Iterate over every document the filters take, page after page.

        Args:
            sort: The order; ``field`` or ``-field`` sorts by ``sort_field_id``.
            sort_field_id: The field to sort by.
            page_size: How many documents each request fetches.
            **filters: Which documents (:class:`pylekto.types.DocumentFilter`).

        Example::

            async for document in lekto.documents.list(lane=["red"], sort="-created_at"):
                print(document.id, document.title)

        """

        async def fetch(cursor: str | None) -> DocumentPage:
            return await self.page(
                cursor=cursor,
                limit=page_size,
                sort=sort,
                sort_field_id=sort_field_id,
                **filters,
            )

        return cursor_items(fetch)

    async def page(
        self,
        *,
        cursor: str | None = None,
        offset: int | None = None,
        limit: int | None = None,
        sort: DocumentListSort | None = None,
        sort_field_id: Id | None = None,
        **filters: Unpack[DocumentFilter],
    ) -> DocumentPage:
        """Return one page of documents; ``next_cursor`` leads to the next.

        Args:
            cursor: Where the page starts: the ``next_cursor`` of the page before.
            offset: Skip so many documents (pages by number); with ``cursor``, after it.
            limit: How many documents the page holds at most.
            sort: The order; ``field`` or ``-field`` sorts by ``sort_field_id``.
            sort_field_id: The field to sort by.
            **filters: Which documents (:class:`pylekto.types.DocumentFilter`).

        Example::

            page = await lekto.documents.page(limit=20)
            more = await lekto.documents.page(cursor=page.next_cursor, limit=20)

        """
        params = query(
            cursor=cursor,
            offset=offset,
            limit=limit,
            sort=sort,
            sort_field_id=sort_field_id,
            **filters,
        )
        return await self._http.get("/documents", DocumentPage, params=params)

    async def count(self, **filters: Unpack[DocumentFilter]) -> DocumentCountOut:
        """Count the documents the filters take.

        Args:
            **filters: Which documents (:class:`pylekto.types.DocumentFilter`).

        Example::

            red = await lekto.documents.count(lane=["red"])
            print(red.total)

        """
        return await self._http.get("/documents/count", DocumentCountOut, params=query(**filters))

    async def facets(self, **filters: Unpack[DocumentFilter]) -> DocumentFacetsOut:
        """Count the documents per value of each filter, within the filters given.

        Args:
            **filters: Which documents (:class:`pylekto.types.DocumentFilter`).

        Example::

            facets = await lekto.documents.facets(lane=["yellow"])

        """
        return await self._http.get("/documents/facets", DocumentFacetsOut, params=query(**filters))

    async def stream(self, **filters: Unpack[DocumentFilter]) -> StreamOut:
        """Return the documents of the stream view, by lane.

        Args:
            **filters: Which documents (:class:`pylekto.types.DocumentFilter`).

        Example::

            stream = await lekto.documents.stream()
            print([lane.lane for lane in stream.lanes])

        """
        return await self._http.get("/documents/stream", StreamOut, params=query(**filters))

    async def get(self, document_id: Id) -> DocumentDetails:
        """Return a document with its metadata, fields and state.

        Args:
            document_id: The document.

        Example::

            document = await lekto.documents.get(document_id)
            print(document.title, document.lane)

        """
        return await self._http.get(f"/documents/{document_id}", DocumentDetails)

    async def upload(
        self,
        file: Upload,
        filename: str,
        *,
        space_id: Id | None = None,
        channel: Literal["migration"] | None = None,
        uploaded_by: Id | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> DocumentAccepted:
        """Upload a file; Lekto processes it in the background.

        A file that lies in Lekto already raises :class:`pylekto.LektoConflictError` with the
        document it collided with, if the caller may read it.

        Args:
            file: The content: PDF, JPEG, PNG, TIFF or a mail (``.eml``), as bytes or a file.
            filename: The name of the file.
            space_id: The space it goes to; default: the uploader's personal space.
            channel: ``migration`` for imports from another system (admins only).
            uploaded_by: The user named as uploader (admins only).
            metadata: With ``channel="migration"``: the metadata the document comes with, as
                Lekto's ``ImportedMetadataIn`` (admins only).

        Example::

            with open("invoice.pdf", "rb") as file:
                accepted = await lekto.documents.upload(file, "invoice.pdf")
            print(accepted.id)

        """
        fields = {
            "space_id": space_id,
            "channel": channel,
            "uploaded_by": uploaded_by,
            "metadata": None if metadata is None else json.dumps(metadata),
        }
        parts: list[tuple[str, Part]] = [("file", (filename, file, FILE_TYPE))]
        parts += [(name, (None, str(value))) for name, value in fields.items() if value is not None]
        return await self._http.call("POST", "/documents", DocumentAccepted, files=parts)

    async def update(
        self, document_id: Id, changes: DocumentPatch, *, confirm: bool | None = None
    ) -> DocumentChanged | DocumentOutOfReach:
        """Change a document's metadata; only the values set in ``changes`` change.

        Args:
            document_id: The document.
            changes: The new values.
            confirm: Whether the change confirms the document (default: Lekto's).

        Example::

            changed = await lekto.documents.update(document_id, DocumentPatch(title="Rent"))

        """
        return await self._http.call_as(
            "PATCH",
            f"/documents/{document_id}",
            _CHANGED,
            params=query(confirm=confirm),
            json=body(changes),
        )

    async def dry_run(
        self, document_id: Id, changes: DocumentPatch, *, confirm: bool | None = None
    ) -> DocumentPreviewOut:
        """Show what a change of the metadata would do, without making it.

        Args:
            document_id: The document.
            changes: The new values.
            confirm: Whether the change would confirm the document.

        Example::

            preview = await lekto.documents.dry_run(document_id, DocumentPatch(title="Rent"))

        """
        return await self._http.call(
            "POST",
            f"/documents/{document_id}/dry-run",
            DocumentPreviewOut,
            params=query(confirm=confirm),
            json=body(changes),
        )

    async def delete(self, document_id: Id) -> None:
        """Delete a document.

        Args:
            document_id: The document.

        Example::

            await lekto.documents.delete(document_id)

        """
        await self._http.call_empty("DELETE", f"/documents/{document_id}")

    async def move(self, document_id: Id, space_id: Id) -> None:
        """Move a document to another space.

        Args:
            document_id: The document.
            space_id: The space it goes to.

        Example::

            await lekto.documents.move(document_id, space_id)

        """
        await self._http.call_empty(
            "POST", f"/documents/{document_id}/move", json={"space_id": str(space_id)}
        )

    async def original(self, document_id: Id) -> bytes:
        """Download the original file of the current version.

        Args:
            document_id: The document.

        Example::

            content = await lekto.documents.original(document_id)

        """
        return await self._http.download(f"/documents/{document_id}/original")

    async def version_original(self, document_id: Id, number: int) -> bytes:
        """Download the original file of a version.

        Args:
            document_id: The document.
            number: The version, from 1.

        Example::

            first = await lekto.documents.version_original(document_id, 1)

        """
        return await self._http.download(f"/documents/{document_id}/versions/{number}/original")

    async def archive(self, document_id: Id) -> bytes:
        """Download the archive PDF (PDF/A with a text layer).

        Args:
            document_id: The document.

        Example::

            pdf = await lekto.documents.archive(document_id)

        """
        return await self._http.download(f"/documents/{document_id}/archive")

    async def preview(self, document_id: Id) -> bytes:
        """Download the preview image of the first page (WebP).

        Args:
            document_id: The document.

        Example::

            image = await lekto.documents.preview(document_id)

        """
        return await self._http.download(f"/documents/{document_id}/preview")

    async def page_image(self, document_id: Id, number: int) -> bytes:
        """Download the image of one page (WebP).

        Args:
            document_id: The document.
            number: The page, from 1.

        Example::

            image = await lekto.documents.page_image(document_id, 2)

        """
        return await self._http.download(f"/documents/{document_id}/pages/{number}")

    async def text(
        self, document_id: Id, *, offset: int | None = None, limit: int | None = None
    ) -> DocumentTextOut:
        """Return the recognised text, or a part of it.

        Args:
            document_id: The document.
            offset: Where the part starts, in characters.
            limit: How many characters it holds at most.

        Example::

            text = await lekto.documents.text(document_id)
            print(text.text)

        """
        return await self._http.get(
            f"/documents/{document_id}/text",
            DocumentTextOut,
            params=query(offset=offset, limit=limit),
        )

    async def structure(self, document_id: Id) -> dict[str, Any]:
        """Return the parsed structure of the text (its form is Lekto's own).

        Args:
            document_id: The document.

        Example::

            structure = await lekto.documents.structure(document_id)

        """
        return await self._http.call_as("GET", f"/documents/{document_id}/structure", _STRUCTURE)

    async def exchanges(self, document_id: Id, node: ExchangeNode) -> builtins.list[RunExchangeOut]:
        """Return what a node sent to the language model and what came back.

        Args:
            document_id: The document.
            node: ``ocr``, ``signal_llm`` or ``fields``.

        Example::

            for exchange in await lekto.documents.exchanges(document_id, "fields"):
                print(exchange.model)

        """
        return await self._http.call_as(
            "GET", f"/documents/{document_id}/exchanges/{node}", _EXCHANGES
        )

    async def log(self, document_id: Id) -> builtins.list[LogEntry]:
        """Return the processing log: each node, its outcome and its reasons.

        Args:
            document_id: The document.

        Example::

            for entry in await lekto.documents.log(document_id):
                print(entry.node, entry.outcome)

        """
        return await self._http.call_as("GET", f"/documents/{document_id}/log", _LOG)

    async def retry(self, document_id: Id) -> DocumentDetails:
        """Repeat the node that failed.

        Args:
            document_id: The document.

        Example::

            document = await lekto.documents.retry(document_id)

        """
        return await self._http.call("POST", f"/documents/{document_id}/retry", DocumentDetails)

    async def vision(self, document_id: Id) -> DocumentDetails:
        """Have the vision language model read the document.

        Args:
            document_id: The document.

        Example::

            document = await lekto.documents.vision(document_id)

        """
        return await self._http.call("POST", f"/documents/{document_id}/vision", DocumentDetails)

    async def reprocess(self, document_id: Id, request: ReprocessRequest) -> DocumentDetails:
        """Process the document again from a node.

        Args:
            document_id: The document.
            request: The node to start from.

        Example::

            await lekto.documents.reprocess(document_id, ReprocessRequest(from_node="ocr"))

        """
        return await self._http.call(
            "POST", f"/documents/{document_id}/reprocess", DocumentDetails, json=body(request)
        )

    async def facts(self, document_id: Id) -> FactsOut:
        """Return what the document shows of its contact: identifiers, codes, roles.

        Args:
            document_id: The document.

        Example::

            facts = await lekto.documents.facts(document_id)

        """
        return await self._http.get(f"/documents/{document_id}/facts", FactsOut)

    async def decide_fact(self, document_id: Id, decision: FactDecisionIn) -> FactsOut:
        """Decide about a fact of the document: confirm, reject or correct it.

        Args:
            document_id: The document.
            decision: What to do with which fact.

        Example::

            facts = await lekto.documents.decide_fact(document_id, decision)

        """
        return await self._http.call(
            "POST", f"/documents/{document_id}/facts/decisions", FactsOut, json=body(decision)
        )

    async def place(self, document_id: Id, kind: str, ref: str) -> PlaceOut:
        """Return where an identifier stands in the document.

        Args:
            document_id: The document.
            kind: The kind of the identifier, such as ``iban``.
            ref: The reference to its value (from the facts or ``identifiers``).

        Example::

            place = await lekto.documents.place(document_id, "iban", ref)

        """
        return await self._http.get(f"/documents/{document_id}/places/{kind}/{ref}", PlaceOut)

    async def files(self, document_id: Id) -> DocumentFilesOut:
        """Return the document's files and their metadata.

        Args:
            document_id: The document.

        Example::

            files = await lekto.documents.files(document_id)

        """
        return await self._http.get(f"/documents/{document_id}/files", DocumentFilesOut)

    async def reading(self, document_id: Id) -> ReadingOut:
        """Return how the text was read: the way, its confidence, the vision model's offer.

        Args:
            document_id: The document.

        Example::

            reading = await lekto.documents.reading(document_id)

        """
        return await self._http.get(f"/documents/{document_id}/reading", ReadingOut)

    async def review(self, document_id: Id) -> ReviewOut:
        """Return what the model proposed for the document.

        Args:
            document_id: The document.

        Example::

            review = await lekto.documents.review(document_id)

        """
        return await self._http.get(f"/documents/{document_id}/review", ReviewOut)

    async def confirm(
        self, document_id: Id, request: ConfirmRequest | None = None
    ) -> DocumentDetails | DocumentOutOfReach:
        """Confirm a document from the inbox, with changes if given.

        Args:
            document_id: The document.
            request: Changes, whether to accept the suggestions, where to resume.

        Example::

            await lekto.documents.confirm(document_id)

        """
        request = request if request is not None else ConfirmRequest()
        return await self._http.call_as(
            "POST", f"/documents/{document_id}/confirm", _CONFIRMED, json=body(request)
        )

    async def mark_seen(self, document_id: Id) -> None:
        """Mark a document as seen.

        Args:
            document_id: The document.

        Example::

            await lekto.documents.mark_seen(document_id)

        """
        await self._http.call_empty("PUT", f"/documents/{document_id}/seen")

    async def mark_new(self, document_id: Id) -> None:
        """Mark a document as new again.

        Args:
            document_id: The document.

        Example::

            await lekto.documents.mark_new(document_id)

        """
        await self._http.call_empty("DELETE", f"/documents/{document_id}/seen")

    async def origin(self, document_id: Id) -> OriginOut:
        """Return where the document came from: upload, mail or migration.

        Args:
            document_id: The document.

        Example::

            origin = await lekto.documents.origin(document_id)

        """
        return await self._http.get(f"/documents/{document_id}/origin", OriginOut)

    async def add_version(self, document_id: Id, file: Upload, filename: str) -> DocumentDetails:
        """Replace the document's file with a new version.

        Args:
            document_id: The document.
            file: The new content: PDF, JPEG, PNG or TIFF.
            filename: The name of the file.

        Example::

            document = await lekto.documents.add_version(document_id, content, "scan.pdf")

        """
        return await self._http.call(
            "POST",
            f"/documents/{document_id}/versions",
            DocumentDetails,
            files=[("file", (filename, file, FILE_TYPE))],
        )

    async def edit_pages(self, document_id: Id, file: Upload, filename: str) -> PagePreviews:
        """Show the pages of a file that an edit could add to the document.

        Args:
            document_id: The document.
            file: The file: PDF, JPEG, PNG or TIFF.
            filename: The name of the file.

        Example::

            pages = await lekto.documents.edit_pages(document_id, content, "more.pdf")

        """
        return await self._http.call(
            "POST",
            f"/documents/{document_id}/edit/pages",
            PagePreviews,
            files=[("file", (filename, file, FILE_TYPE))],
        )

    async def edit(
        self,
        document_id: Id,
        parts: Sequence[EditPart],
        *,
        files: Sequence[tuple[str, Upload]] = (),
        documents: Sequence[Id] = (),
        target: Id | None = None,
    ) -> EditedDocuments:
        """Edit the pages: reorder, rotate, split, merge, take pages from other files.

        Args:
            document_id: The document.
            parts: Each a list of pages and whether it replaces the document; every other part
                becomes a new document.
            files: Files whose pages the parts take (sources 1, 2, …), as name and content.
            documents: Other documents whose pages the parts take (the sources after the files).
            target: In a merge, the document the replacing part makes the next version of.

        Example::

            split = await lekto.documents.edit(
                document_id,
                [{"pages": [{"page": 1}], "replaces": True}, {"pages": [{"page": 2}]}],
            )

        """
        sent = [{**part, "pages": [*part["pages"]]} for part in parts]
        fields: list[tuple[str, Part]] = [("parts", (None, json.dumps(sent)))]
        if documents:
            fields.append(("documents", (None, json.dumps([str(other) for other in documents]))))
        if target is not None:
            fields.append(("target", (None, str(target))))
        fields += [("files", (name, content, FILE_TYPE)) for name, content in files]
        return await self._http.call(
            "POST", f"/documents/{document_id}/edit", EditedDocuments, files=fields
        )

    async def bulk(
        self, request: BulkRequest, **filters: Unpack[DocumentFilter]
    ) -> BulkOperationOut:
        """Change many documents at once, in the background.

        Args:
            request: The action, and the documents by id or by a search.
            **filters: Which documents, if ``request`` names none by id.

        Example::

            operation = await lekto.documents.bulk(request, lane=["yellow"])
            progress = await lekto.documents.bulk_progress(operation.id)

        """
        return await self._http.call(
            "POST", "/documents/bulk", BulkOperationOut, params=query(**filters), json=body(request)
        )

    async def bulk_progress(self, operation_id: Id) -> BulkOperationOut:
        """Return the progress of a change of many documents.

        Args:
            operation_id: The change, as :meth:`bulk` returned it.

        Example::

            progress = await lekto.documents.bulk_progress(operation.id)
            print(progress.done, progress.total)

        """
        return await self._http.get(f"/documents/bulk/{operation_id}", BulkOperationOut)
