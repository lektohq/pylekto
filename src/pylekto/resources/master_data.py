"""The master data: contacts, document types, tags and fields (changed by admins)."""

from typing import TYPE_CHECKING

from pydantic import TypeAdapter

from pylekto._http import FILE_TYPE, Upload, body, query
from pylekto.models import (
    ContactCreate,
    ContactOut,
    ContactPatch,
    DocumentTypeCreate,
    DocumentTypeOut,
    DocumentTypePatch,
    FieldAssignmentsIn,
    FieldCreate,
    FieldOut,
    FieldPatch,
    IdentifierIn,
    QueuedOut,
    TagCreate,
    TagOut,
    TagPatch,
)
from pylekto.resources._base import Resource

if TYPE_CHECKING:
    import builtins

    from pylekto.models import TagScope
    from pylekto.types import Id

_CONTACTS = TypeAdapter(list[ContactOut])
_DOCUMENT_TYPES = TypeAdapter(list[DocumentTypeOut])
_TAGS = TypeAdapter(list[TagOut])
_FIELDS = TypeAdapter(list[FieldOut])


class ContactsResource(Resource):
    """The contacts: who sends documents, with aliases, identifiers and logos."""

    async def list(
        self, *, document_counts: bool | None = None, all_users: bool | None = None
    ) -> builtins.list[ContactOut]:
        """Return every contact.

        Args:
            document_counts: Count each contact's documents.
            all_users: Count every user's documents, not only the caller's reach (admins).

        Example::

            for contact in await lekto.contacts.list(document_counts=True):
                print(contact.name, contact.document_count)

        """
        params = query(document_counts=document_counts, all_users=all_users)
        return await self._http.call_as("GET", "/contacts", _CONTACTS, params=params)

    async def create(self, contact: ContactCreate) -> ContactOut:
        """Create a contact.

        Args:
            contact: The name, aliases, identifiers, groups and topics.

        Example::

            bakery = await lekto.contacts.create(ContactCreate(name="Muster Bäckerei"))

        """
        return await self._http.call("POST", "/contacts", ContactOut, json=body(contact))

    async def get(self, contact_id: Id) -> ContactOut:
        """Return a contact.

        Args:
            contact_id: The contact.

        Example::

            contact = await lekto.contacts.get(contact_id)

        """
        return await self._http.get(t"/contacts/{contact_id}", ContactOut)

    async def update(self, contact_id: Id, changes: ContactPatch) -> ContactOut:
        """Change a contact; only the values set in ``changes`` change.

        Args:
            contact_id: The contact.
            changes: The new values.

        Example::

            await lekto.contacts.update(contact_id, ContactPatch(aliases=["Muster"]))

        """
        return await self._http.call(
            "PATCH", t"/contacts/{contact_id}", ContactOut, json=body(changes)
        )

    async def delete(self, contact_id: Id) -> None:
        """Delete a contact.

        Args:
            contact_id: The contact.

        Example::

            await lekto.contacts.delete(contact_id)

        """
        await self._http.call_empty("DELETE", t"/contacts/{contact_id}")

    async def attach_identifier(self, contact_id: Id, identifier: IdentifierIn) -> ContactOut:
        """Attach an identifier from a document's facts to a contact.

        Args:
            contact_id: The contact.
            identifier: The kind and value, and the topic or user it belongs to.

        Example::

            await lekto.contacts.attach_identifier(
                contact_id, IdentifierIn(kind="customer_number", value="12345")
            )

        """
        return await self._http.call(
            "POST", t"/contacts/{contact_id}/identifiers", ContactOut, json=body(identifier)
        )

    async def logo(self, contact_id: Id) -> bytes:
        """Download a contact's logo (WebP).

        Args:
            contact_id: The contact.

        Example::

            image = await lekto.contacts.logo(contact_id)

        """
        return await self._http.download(t"/contacts/{contact_id}/logo")

    async def upload_logo(self, contact_id: Id, file: Upload, filename: str) -> ContactOut:
        """Upload a contact's logo: PNG, JPEG or WebP, at most 1 MiB.

        Args:
            contact_id: The contact.
            file: The image.
            filename: The name of the file.

        Example::

            await lekto.contacts.upload_logo(contact_id, image, "logo.png")

        """
        return await self._http.call(
            "PUT",
            t"/contacts/{contact_id}/logo",
            ContactOut,
            files=[("file", (filename, file, FILE_TYPE))],
        )

    async def delete_logo(self, contact_id: Id) -> None:
        """Remove a contact's logo.

        Args:
            contact_id: The contact.

        Example::

            await lekto.contacts.delete_logo(contact_id)

        """
        await self._http.call_empty("DELETE", t"/contacts/{contact_id}/logo")

    async def fetch_logo(self, contact_id: Id) -> None:
        """Fetch a contact's logo from its website, in the background.

        Args:
            contact_id: The contact.

        Example::

            await lekto.contacts.fetch_logo(contact_id)

        """
        await self._http.call_empty("POST", t"/contacts/{contact_id}/logo/fetch")

    async def fetch_logos(self) -> QueuedOut:
        """Fetch the missing logos of every contact with a website, in the background.

        Example::

            queued = await lekto.contacts.fetch_logos()

        """
        return await self._http.call("POST", "/contacts/logos/fetch", QueuedOut)


class DocumentTypesResource(Resource):
    """The document types, their title patterns and their fields."""

    async def list(
        self, *, document_counts: bool | None = None, all_users: bool | None = None
    ) -> builtins.list[DocumentTypeOut]:
        """Return every document type.

        Args:
            document_counts: Count each type's documents.
            all_users: Count every user's documents, not only the caller's reach (admins).

        Example::

            names = [kind.name for kind in await lekto.document_types.list()]

        """
        params = query(document_counts=document_counts, all_users=all_users)
        return await self._http.call_as("GET", "/document-types", _DOCUMENT_TYPES, params=params)

    async def create(self, document_type: DocumentTypeCreate) -> DocumentTypeOut:
        """Create a document type.

        Args:
            document_type: The name, a description, a title pattern, groups and fields.

        Example::

            policy = await lekto.document_types.create(DocumentTypeCreate(name="Policy"))

        """
        return await self._http.call(
            "POST", "/document-types", DocumentTypeOut, json=body(document_type)
        )

    async def get(self, document_type_id: Id) -> DocumentTypeOut:
        """Return a document type.

        Args:
            document_type_id: The document type.

        Example::

            document_type = await lekto.document_types.get(document_type_id)

        """
        return await self._http.get(t"/document-types/{document_type_id}", DocumentTypeOut)

    async def update(self, document_type_id: Id, changes: DocumentTypePatch) -> DocumentTypeOut:
        """Change a document type; only the values set in ``changes`` change.

        Args:
            document_type_id: The document type.
            changes: The new values.

        Example::

            await lekto.document_types.update(document_type_id, DocumentTypePatch(icon="file"))

        """
        return await self._http.call(
            "PATCH", t"/document-types/{document_type_id}", DocumentTypeOut, json=body(changes)
        )

    async def delete(self, document_type_id: Id) -> None:
        """Delete a document type.

        Args:
            document_type_id: The document type.

        Example::

            await lekto.document_types.delete(document_type_id)

        """
        await self._http.call_empty("DELETE", t"/document-types/{document_type_id}")

    async def set_fields(
        self, document_type_id: Id, fields: FieldAssignmentsIn
    ) -> builtins.list[FieldOut]:
        """Set the fields of a document type, in their order.

        Args:
            document_type_id: The document type.
            fields: Each field and whether it is required.

        Example::

            await lekto.document_types.set_fields(
                document_type_id, FieldAssignmentsIn(fields=[FieldAssignmentIn(field_id=amount)])
            )

        """
        return await self._http.call_as(
            "PUT", t"/document-types/{document_type_id}/fields", _FIELDS, json=body(fields)
        )


class TagsResource(Resource):
    """The tags of documents, contacts, document types and topics."""

    async def list(
        self,
        *,
        scope: TagScope | None = None,
        document_counts: bool | None = None,
        all_users: bool | None = None,
    ) -> builtins.list[TagOut]:
        """Return every tag, or those of one scope.

        Args:
            scope: Only the tags of documents, contacts, document types or topics.
            document_counts: Count each tag's documents.
            all_users: Count every user's documents, not only the caller's reach (admins).

        Example::

            topics = await lekto.tags.list(scope="topic")

        """
        params = query(scope=scope, document_counts=document_counts, all_users=all_users)
        return await self._http.call_as("GET", "/tags", _TAGS, params=params)

    async def create(self, tag: TagCreate) -> TagOut:
        """Create a tag.

        Args:
            tag: The name, scope, parent, how it is assigned and how it shows.

        Example::

            tag = await lekto.tags.create(TagCreate(name="Tax", scope="document"))

        """
        return await self._http.call("POST", "/tags", TagOut, json=body(tag))

    async def get(self, tag_id: Id) -> TagOut:
        """Return a tag.

        Args:
            tag_id: The tag.

        Example::

            tag = await lekto.tags.get(tag_id)

        """
        return await self._http.get(t"/tags/{tag_id}", TagOut)

    async def update(self, tag_id: Id, changes: TagPatch) -> TagOut:
        """Change a tag; only the values set in ``changes`` change.

        Args:
            tag_id: The tag.
            changes: The new values.

        Example::

            await lekto.tags.update(tag_id, TagPatch(color="#0d6b6b"))

        """
        return await self._http.call("PATCH", t"/tags/{tag_id}", TagOut, json=body(changes))

    async def delete(self, tag_id: Id) -> None:
        """Delete a tag.

        Args:
            tag_id: The tag.

        Example::

            await lekto.tags.delete(tag_id)

        """
        await self._http.call_empty("DELETE", t"/tags/{tag_id}")


class FieldsResource(Resource):
    """The field definitions: what Lekto reads from documents besides title and date."""

    async def list(
        self, *, document_counts: bool | None = None, all_users: bool | None = None
    ) -> builtins.list[FieldOut]:
        """Return every field definition.

        Args:
            document_counts: Count the documents with a value of each field.
            all_users: Count every user's documents, not only the caller's reach (admins).

        Example::

            for field in await lekto.fields.list():
                print(field.name, field.data_type)

        """
        params = query(document_counts=document_counts, all_users=all_users)
        return await self._http.call_as("GET", "/fields", _FIELDS, params=params)

    async def create(self, field: FieldCreate) -> FieldOut:
        """Create a field definition.

        Args:
            field: The name, the data type, choices and the document types it belongs to.

        Example::

            amount = await lekto.fields.create(FieldCreate(name="Amount", data_type="money"))

        """
        return await self._http.call("POST", "/fields", FieldOut, json=body(field))

    async def get(self, field_id: Id) -> FieldOut:
        """Return a field definition.

        Args:
            field_id: The field.

        Example::

            field = await lekto.fields.get(field_id)

        """
        return await self._http.get(t"/fields/{field_id}", FieldOut)

    async def update(self, field_id: Id, changes: FieldPatch) -> FieldOut:
        """Change a field definition; only the values set in ``changes`` change.

        Args:
            field_id: The field.
            changes: The new values.

        Example::

            await lekto.fields.update(field_id, FieldPatch(required=True))

        """
        return await self._http.call("PATCH", t"/fields/{field_id}", FieldOut, json=body(changes))

    async def delete(self, field_id: Id) -> None:
        """Delete a field definition and its values.

        Args:
            field_id: The field.

        Example::

            await lekto.fields.delete(field_id)

        """
        await self._http.call_empty("DELETE", t"/fields/{field_id}")
