"""Tests of the inbox, the expected documents, the lenses and the rules against the snapshot."""

from collections.abc import Awaitable, Callable

import pytest

from pylekto import LektoClient
from pylekto.models import (
    ApplyPreviewRequest,
    ApplyRequest,
    LensCreate,
    LensOrder,
    LensPatch,
    RuleChange,
    RuleCreate,
    RulePatch,
    TemplatePreviewIn,
)

from .conftest import Api, Snapshot, assert_sent, expected, plain

type Call = Callable[[LektoClient, Snapshot], Awaitable[object]]


def first(recorded: Snapshot) -> str:
    """Return the id in the path of a recording (``/<area>/<id>/…``)."""
    return recorded.segment(2)


ANSWERS: dict[str, Call] = {
    "inbox_page": lambda lekto, _: lekto.inbox.page(tab="intervene", limit=5),
    "inbox_summary": lambda lekto, _: lekto.inbox.summary(),
    "inbox_mark_seen": lambda lekto, _: lekto.inbox.mark_seen(),
    "expected_list": lambda lekto, _: lekto.expected.list(tz="Europe/Berlin"),
    "lenses_create": lambda lekto, r: lekto.lenses.create(LensCreate.model_validate(r.json)),
    "lenses_list": lambda lekto, _: lekto.lenses.list(),
    "lenses_get": lambda lekto, r: lekto.lenses.get(first(r)),
    "lenses_update": lambda lekto, r: lekto.lenses.update(
        first(r), LensPatch.model_validate(r.json)
    ),
    "lenses_order": lambda lekto, r: lekto.lenses.order(LensOrder.model_validate(r.json)),
    "rules_create": lambda lekto, r: lekto.rules.create(RuleCreate.model_validate(r.json)),
    "rules_list": lambda lekto, _: lekto.rules.list(include_disabled=True),
    "rules_get": lambda lekto, r: lekto.rules.get(first(r)),
    "rules_replace": lambda lekto, r: lekto.rules.replace(
        first(r), RuleChange.model_validate(r.json)
    ),
    "rules_versions": lambda lekto, r: lekto.rules.versions(first(r)),
    "rules_version": lambda lekto, r: lekto.rules.version(first(r), int(r.segment(4))),
    "rules_preview_apply": lambda lekto, r: lekto.rules.preview_apply(
        first(r), ApplyPreviewRequest.model_validate(r.json)
    ),
    "rules_hits": lambda lekto, r: lekto.rules.hits(first(r), r.segment(5)),
    "rules_apply": lambda lekto, r: lekto.rules.apply(
        first(r), ApplyRequest.model_validate(r.json)
    ),
    "rules_application": lambda lekto, r: lekto.rules.application(first(r)),
    "rules_update": lambda lekto, r: lekto.rules.update(first(r), RulePatch.model_validate(r.json)),
    "templates_preview": lambda lekto, r: lekto.rules.preview_template(
        TemplatePreviewIn.model_validate(r.json)
    ),
}

EMPTY: dict[str, Call] = {
    "lenses_delete": lambda lekto, r: lekto.lenses.delete(first(r)),
    "rules_delete": lambda lekto, r: lekto.rules.delete(first(r)),
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


async def test_inbox_list_follows_the_cursor(api: Api, lekto: LektoClient) -> None:
    """``inbox.list`` yields the documents of every page of a tab."""
    recorded = api.replay("inbox_page")
    api.answer(
        "GET",
        "/inbox",
        json={**recorded.body, "next_cursor": "next"},
        when={"tab": "intervene"},
    )
    api.answer(
        "GET",
        "/inbox",
        json={"items": [], "next_cursor": None},
        when={"tab": "intervene", "cursor": "next"},
    )
    found = [item async for item in lekto.inbox.list(tab="intervene", page_size=5)]
    assert len(found) == len(recorded.body["items"])
    assert [request.url.params.get("cursor") for request in api.requests] == [None, "next"]
    assert all(request.url.params.get("limit") == "5" for request in api.requests)
