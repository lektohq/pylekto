"""Tests of users, spaces, identifiers and the master data against the snapshot."""

from collections.abc import Awaitable, Callable

import pytest
from pydantic import TypeAdapter

from pylekto import LektoClient, LektoForbiddenError, LektoServerError
from pylekto.models import (
    ContactCreate,
    ContactPatch,
    DocumentTypeCreate,
    DocumentTypePatch,
    FieldAssignmentsIn,
    FieldCreate,
    FieldPatch,
    IdentifierIn,
    MemberIn,
    OpenDecisionsIn,
    ProfilePatch,
    RefIn,
    SpaceCreate,
    SpacePatch,
    TagCreate,
    TagPatch,
    UserCreate,
    UserPatch,
)
from pylekto.types import IdentifierKind

from .conftest import Api, Snapshot, assert_sent, expected, plain

type Call = Callable[[LektoClient, Snapshot], Awaitable[object]]


def first(recorded: Snapshot) -> str:
    """Return the id in the path of a recording (``/<area>/<id>/…``)."""
    return recorded.segment(2)


def kind(recorded: Snapshot) -> IdentifierKind:
    """Return the kind of identifier in the path of a recording (``/identifiers/…/<kind>/…``)."""
    return TypeAdapter(IdentifierKind).validate_python(recorded.segment(3))


ANSWERS: dict[str, Call] = {
    "users_list": lambda lekto, _: lekto.users.list(),
    "users_create": lambda lekto, r: lekto.users.create(UserCreate.model_validate(r.json)),
    "users_get": lambda lekto, r: lekto.users.get(first(r)),
    "users_update": lambda lekto, r: lekto.users.update(first(r), UserPatch.model_validate(r.json)),
    "users_profile": lambda lekto, r: lekto.users.profile(first(r)),
    "users_update_profile": lambda lekto, r: lekto.users.update_profile(
        first(r), ProfilePatch.model_validate(r.json)
    ),
    "users_removal": lambda lekto, r: lekto.users.removal(first(r)),
    "spaces_list": lambda lekto, _: lekto.spaces.list(),
    "spaces_create": lambda lekto, r: lekto.spaces.create(SpaceCreate.model_validate(r.json)),
    "spaces_get": lambda lekto, r: lekto.spaces.get(first(r)),
    "spaces_update": lambda lekto, r: lekto.spaces.update(
        first(r), SpacePatch.model_validate(r.json)
    ),
    "spaces_set_member": lambda lekto, r: lekto.spaces.set_member(
        first(r), r.segment(4), MemberIn.model_validate(r.json)
    ),
    "spaces_remove_member": lambda lekto, r: lekto.spaces.remove_member(first(r), r.segment(4)),
    "contacts_list": lambda lekto, _: lekto.contacts.list(document_counts=True),
    "contacts_create": lambda lekto, r: lekto.contacts.create(ContactCreate.model_validate(r.json)),
    "contacts_get": lambda lekto, r: lekto.contacts.get(first(r)),
    "contacts_update": lambda lekto, r: lekto.contacts.update(
        first(r), ContactPatch.model_validate(r.json)
    ),
    "contacts_attach_identifier": lambda lekto, r: lekto.contacts.attach_identifier(
        first(r), IdentifierIn.model_validate(r.json)
    ),
    "document_types_list": lambda lekto, _: lekto.document_types.list(document_counts=True),
    "document_types_create": lambda lekto, r: lekto.document_types.create(
        DocumentTypeCreate.model_validate(r.json)
    ),
    "document_types_get": lambda lekto, r: lekto.document_types.get(first(r)),
    "document_types_update": lambda lekto, r: lekto.document_types.update(
        first(r), DocumentTypePatch.model_validate(r.json)
    ),
    "document_types_set_fields": lambda lekto, r: lekto.document_types.set_fields(
        first(r), FieldAssignmentsIn.model_validate(r.json)
    ),
    "tags_list": lambda lekto, _: lekto.tags.list(scope="document"),
    "tags_create": lambda lekto, r: lekto.tags.create(TagCreate.model_validate(r.json)),
    "tags_get": lambda lekto, r: lekto.tags.get(first(r)),
    "tags_update": lambda lekto, r: lekto.tags.update(first(r), TagPatch.model_validate(r.json)),
    "fields_list": lambda lekto, _: lekto.fields.list(),
    "fields_create": lambda lekto, r: lekto.fields.create(FieldCreate.model_validate(r.json)),
    "fields_get": lambda lekto, r: lekto.fields.get(first(r)),
    "fields_update": lambda lekto, r: lekto.fields.update(
        first(r), FieldPatch.model_validate(r.json)
    ),
    "identifiers_open": lambda lekto, _: lekto.identifiers.open(limit=5),
    "identifiers_search_open": lambda lekto, r: lekto.identifiers.search_open(r.json["q"], limit=5),
    "identifiers_open_summary": lambda lekto, _: lekto.identifiers.open_summary(),
    "identifiers_open_identifier": lambda lekto, r: lekto.identifiers.open_identifier(
        kind(r), r.segment(4)
    ),
    "identifiers_ref": lambda lekto, r: lekto.identifiers.ref(RefIn.model_validate(r.json)),
    "identifiers_value": lambda lekto, r: lekto.identifiers.value(kind(r), r.segment(4)),
    "identifiers_places": lambda lekto, r: lekto.identifiers.places(kind(r), r.segment(4)),
    "identifiers_decide": lambda lekto, r: lekto.identifiers.decide(
        OpenDecisionsIn.model_validate(r.json)
    ),
    "identifiers_confirm_recommended": lambda lekto, _: lekto.identifiers.confirm_recommended(),
}

EMPTY: dict[str, Call] = {
    "spaces_delete": lambda lekto, r: lekto.spaces.delete(first(r)),
    "contacts_delete_logo": lambda lekto, r: lekto.contacts.delete_logo(first(r)),
    "contacts_delete": lambda lekto, r: lekto.contacts.delete(first(r)),
    "document_types_delete": lambda lekto, r: lekto.document_types.delete(first(r)),
    "tags_delete": lambda lekto, r: lekto.tags.delete(first(r)),
    "fields_delete": lambda lekto, r: lekto.fields.delete(first(r)),
}


@pytest.mark.parametrize("name", sorted(ANSWERS))
async def test_answer(api: Api, lekto: LektoClient, name: str) -> None:
    """The method sends the recorded request and reads Lekto's answer."""
    recorded = api.replay(name)
    answer = await ANSWERS[name](lekto, recorded)
    assert_sent(api, recorded)
    assert plain(answer) == expected(answer, recorded.body)


@pytest.mark.parametrize("name", sorted(EMPTY))
async def test_empty_answer(api: Api, lekto: LektoClient, name: str) -> None:
    """The method sends the recorded request; Lekto answers without a body."""
    recorded = api.replay(name)
    assert await EMPTY[name](lekto, recorded) is None
    assert_sent(api, recorded)


async def test_remove_own_membership(api: Api, lekto: LektoClient) -> None:
    """Removing oneself from a space answers 204, without the space."""
    space, user = "0199a3c4-0000-7000-8000-0000000000aa", "0199a3c4-0000-7000-8000-0000000000bb"
    api.answer("DELETE", f"/spaces/{space}/members/{user}", 204)
    assert await lekto.spaces.remove_member(space, user) is None


async def test_profile_needs_a_session_beyond_name_and_mail(api: Api, lekto: LektoClient) -> None:
    """A token sets only the display name and the e-mail of a profile; more is forbidden."""
    recorded = api.replay("users_update_profile_refused")
    with pytest.raises(LektoForbiddenError) as raised:
        await lekto.users.update_profile(first(recorded), ProfilePatch(aliases=["Jane"]))
    assert raised.value.reason is not None
    assert raised.value.reason.code == "session_needed_profile"


async def test_logo_not_fetched(api: Api, lekto: LektoClient) -> None:
    """An installation that fetches no logos answers 503."""
    recorded = api.replay("contacts_fetch_logo")
    with pytest.raises(LektoServerError, match="does not fetch logos"):
        await lekto.contacts.fetch_logo(first(recorded))


async def test_logos_not_fetched(api: Api, lekto: LektoClient) -> None:
    """An installation that fetches no logos answers 503 to fetching them all."""
    api.replay("contacts_fetch_logos")
    with pytest.raises(LektoServerError, match="does not fetch logos"):
        await lekto.contacts.fetch_logos()


async def test_fetch_logos(api: Api, lekto: LektoClient) -> None:
    """Fetching the missing logos says how many it queued."""
    api.answer("POST", "/contacts/logos/fetch", 202, json={"queued": 3})
    assert (await lekto.contacts.fetch_logos()).queued == 3


async def test_fetch_logo(api: Api, lekto: LektoClient) -> None:
    """Fetching one logo is queued without an answer."""
    contact = "0199a3c4-0000-7000-8000-0000000000cc"
    api.answer("POST", f"/contacts/{contact}/logo/fetch", 202)
    await lekto.contacts.fetch_logo(contact)
    assert api.requests[-1].url.path == f"/api/v1/contacts/{contact}/logo/fetch"


async def test_upload_logo(api: Api, lekto: LektoClient) -> None:
    """A logo goes as the file of a multipart body; the contact comes back."""
    recorded = api.replay("contacts_upload_logo")
    contact = await lekto.contacts.upload_logo(first(recorded), b"\x89PNG made up", "logo.png")
    assert str(contact.id) == recorded.body["id"]
    request = api.requests[-1]
    assert request.method == "PUT"
    assert b'name="file"; filename="logo.png"' in request.content


async def test_logo(api: Api, lekto: LektoClient) -> None:
    """A logo downloads as bytes."""
    contact = "0199a3c4-0000-7000-8000-0000000000cc"
    api.answer("GET", f"/contacts/{contact}/logo", content=b"RIFF made up WEBP")
    assert await lekto.contacts.logo(contact) == b"RIFF made up WEBP"
