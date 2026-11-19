"""Tests that every choice in the models also takes a value that a newer Lekto may send."""

import json
import types
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Literal,
    TypeAliasType,
    Union,
    get_args,
    get_origin,
)

import pytest
from pydantic import BaseModel, TypeAdapter

from pylekto import LektoClient, Unknown, models
from pylekto._http import body

from .conftest import snapshot

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .conftest import Api

NEW_VALUE = "a-value-of-a-newer-lekto"

type Choice = tuple[object, object]


def choices(annotation: object, union: object = None) -> Iterator[Choice]:
    """Yield each ``Literal`` in an annotation with the union it stands in, or None."""
    if isinstance(annotation, TypeAliasType):
        yield from choices(annotation.__value__, union)
        return
    origin = get_origin(annotation)
    arguments = get_args(annotation)
    if origin is Literal:
        yield annotation, union
    elif origin is Annotated:
        yield from choices(arguments[0], union)
    elif origin in {Union, types.UnionType}:
        for argument in arguments:
            yield from choices(argument, annotation)
    else:
        for argument in arguments:
            yield from choices(argument)


def all_choices() -> list[Choice]:
    """Return every choice of more than one value in the models and their type aliases."""
    found: list[Choice] = []
    for value in vars(models).values():
        if isinstance(value, TypeAliasType):
            found.extend(choices(value))
        elif isinstance(value, type) and issubclass(value, BaseModel) and value is not BaseModel:
            for field in value.model_fields.values():
                found.extend(choices(field.annotation))
    return [(literal, union) for literal, union in found if len(get_args(literal)) > 1]


CHOICES = all_choices()


def test_every_choice_is_open() -> None:
    """Each ``Literal`` of more than one value stands in a union with ``Unknown``."""
    assert len(CHOICES) > 100
    closed = [literal for literal, union in CHOICES if Unknown not in get_args(union)]
    assert closed == []


@pytest.mark.parametrize("union", sorted({union for _, union in CHOICES}, key=repr))
def test_a_new_value_reads_as_unknown(union: Any) -> None:
    """A value the choice does not list becomes ``Unknown``; a listed one stays a ``str``."""
    adapter: TypeAdapter[Any] = TypeAdapter(union)
    new = adapter.validate_json(json.dumps(NEW_VALUE))
    assert isinstance(new, Unknown)
    assert new == NEW_VALUE
    literal = next(member for member in get_args(union) if get_origin(member) is Literal)
    for known in get_args(literal):
        assert type(adapter.validate_json(json.dumps(known))) is str


async def test_an_answer_with_a_new_value_reads(api: Api, lekto: LektoClient) -> None:
    """A document in a lane this pylekto does not know reads, with that lane as ``Unknown``."""
    recorded = snapshot("documents_get")
    api.answer("GET", recorded.path, json=recorded.body | {"lane": NEW_VALUE})
    document = await lekto.documents.get(recorded.segment(2))
    assert isinstance(document.lane, Unknown)
    assert document.lane == NEW_VALUE


def test_a_request_sends_an_unknown_as_written() -> None:
    """A value given as ``Unknown`` goes to Lekto as its text."""
    mailbox = models.MailboxCreate.model_validate(
        snapshot("mailboxes_create").json | {"security": Unknown(NEW_VALUE)}
    )
    assert body(mailbox)["security"] == NEW_VALUE
