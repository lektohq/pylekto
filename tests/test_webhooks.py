"""Tests of receiving webhooks: signatures, bodies and tasks, with requests Lekto really sent."""

import base64
import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx2
import pytest
from pydantic import BaseModel

from pylekto import (
    LektoAuthenticationError,
    LektoConflictError,
    LektoResponseError,
    WebhookVerificationError,
    models,
    webhooks,
)
from pylekto.models import TaskAnswer

from .conftest import SNAPSHOT

if TYPE_CHECKING:
    from pathlib import Path

RECORDED = SNAPSHOT / "webhooks"


def recorded(name: str) -> dict[str, Any]:
    """Return a request Lekto sent to a webhook: its headers, body and the webhook's secret."""
    request: dict[str, Any] = json.loads((RECORDED / f"{name}.json").read_text(encoding="utf-8"))
    return request


def sent_at(request: dict[str, Any]) -> datetime:
    """Return the time a recorded request was signed."""
    headers = {name.lower(): value for name, value in request["headers"].items()}
    return datetime.fromtimestamp(int(headers["webhook-timestamp"]), UTC)


@pytest.mark.parametrize("path", sorted(RECORDED.glob("*.json")), ids=lambda path: path.stem)
def test_lekto_signs_as_pylekto_checks(path: Path) -> None:
    """Every request Lekto sent passes the check with its webhook's secret."""
    request = recorded(path.stem)
    webhooks.verify(
        request["headers"], request["body"].encode(), request["secret"], now=sent_at(request)
    )


def test_the_example_of_standard_webhooks() -> None:
    """The signature of the example in the Standard Webhooks specification passes."""
    headers = {
        "Webhook-Id": "msg_p5jXN8AQM9LWM0D4loKWxJek",
        "Webhook-Timestamp": "1614265330",
        "Webhook-Signature": "v1,g0hM9SsE+OTPJTGt/tmIKtSyZlE3uFJELVlNIOLJ1OE=",
    }
    webhooks.verify(
        headers,
        b'{"test": 2432232314}',
        "whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw",
        now=datetime.fromtimestamp(1614265330, UTC),
    )


def changed(request: dict[str, Any], **headers: str) -> dict[str, str]:
    """Return the headers of a request with some of them changed or, given as '', left out."""
    sent = {name.lower(): value for name, value in request["headers"].items()}
    sent.update(headers)
    return {name: value for name, value in sent.items() if value}


@pytest.mark.parametrize(
    ("headers", "content", "message"),
    [
        ({}, b"{}", "no signature"),
        ({"webhook-signature": ""}, None, "not signed"),
        ({"webhook-timestamp": "yesterday"}, None, "no number"),
        ({"webhook-signature": "v1,AAAA"}, None, "no signature"),
        ({"webhook-signature": "v2,AAAA"}, None, "no signature"),
    ],
)
def test_what_fails_the_check(headers: dict[str, str], content: bytes | None, message: str) -> None:
    """A changed body, a missing or wrong signature or timestamp fails the check."""
    request = recorded("rule_send")
    with pytest.raises(WebhookVerificationError, match=message):
        webhooks.verify(
            changed(request, **headers),
            content if content is not None else request["body"].encode(),
            request["secret"],
            now=sent_at(request),
        )


def test_a_request_too_old_or_from_the_future_fails() -> None:
    """A request signed more than five minutes from now fails, either way."""
    request = recorded("rule_send")
    for shift in (timedelta(minutes=6), -timedelta(minutes=6)):
        with pytest.raises(WebhookVerificationError, match="too far"):
            webhooks.verify(
                request["headers"],
                request["body"].encode(),
                request["secret"],
                now=sent_at(request) + shift,
            )
    webhooks.verify(
        request["headers"],
        request["body"].encode(),
        request["secret"],
        now=sent_at(request) + timedelta(minutes=6),
        tolerance=timedelta(minutes=10),
    )


def test_secrets_while_one_replaces_another() -> None:
    """With several secrets, one that signed the request passes; another secret alone fails."""
    request = recorded("document_filed")
    other = "whsec_" + base64.b64encode(b"another made-up secret").decode()
    for secrets in ([other, request["secret"]], [request["secret"], other]):
        webhooks.verify(request["headers"], request["body"].encode(), secrets, now=sent_at(request))
    with pytest.raises(WebhookVerificationError):
        webhooks.verify(request["headers"], request["body"].encode(), other, now=sent_at(request))
    signatures = changed(request)["webhook-signature"]
    several = changed(request, **{"webhook-signature": f"v1,AAAA {signatures}"})
    webhooks.verify(several, request["body"].encode(), request["secret"], now=sent_at(request))


@pytest.mark.parametrize("secret", ["no prefix", "whsec_not base64!"])
def test_a_secret_that_is_none(secret: str) -> None:
    """A secret that is not a webhook's is a mistake of the caller."""
    request = recorded("rule_send")
    with pytest.raises(ValueError, match="not a webhook secret"):
        webhooks.verify(request["headers"], request["body"].encode(), secret, now=sent_at(request))
    with pytest.raises(ValueError, match="not a webhook secret"):
        webhooks.verify({}, b"", [request["secret"], secret])


def test_bodies_read_as_their_models() -> None:
    """Each body Lekto sent reads as the model of its kind."""
    event = webhooks.read_event(recorded("document_filed")["body"])
    assert event.type == "document.filed"
    assert event.document is not None
    sent = webhooks.read_rule_send(recorded("rule_send")["body"].encode())
    assert sent.rule.name == "Muster Question"
    asked = webhooks.read_rule_ask(recorded("rule_ask")["body"])
    assert asked.task.token.startswith("lkt_")
    proposal = webhooks.read_propose(recorded("external_propose")["body"])
    assert proposal.task.kind == "external.propose"


@pytest.mark.parametrize(
    ("name", "model"),
    [
        ("document_filed", models.EventBody),
        ("rule_send", models.RuleSendBody),
        ("rule_ask", models.RuleAskBody),
        ("external_propose", models.ProposeContext),
    ],
)
def test_bodies_hold_only_listed_values(name: str, model: type[BaseModel]) -> None:
    """What Lekto sent holds only values its description lists: it reads strictly, no Unknown."""
    model.model_validate_json(recorded(name)["body"], strict=True)


def test_extract_reads_as_its_model() -> None:
    """A model call that reads fields reads as ExtractContext.

    Lekto sends it only when a proposal leaves fields open; the body is made here from the parts
    it shares with the recorded proposal, with the name of a document type.
    """
    proposal = json.loads(recorded("external_propose")["body"])
    content = {
        "contract": "extract-ext-1",
        "task": {**proposal["task"], "kind": "external.extract"},
        "document": proposal["document"],
        "document_type": proposal["document_types"][0]["name"],
        "fields": proposal["fields"],
        "answer_schema": proposal["answer_schema"],
    }
    context = webhooks.read_extract(json.dumps(content))
    assert context.task.kind == "external.extract"
    assert context.document_type == proposal["document_types"][0]["name"]


def test_a_body_of_another_kind() -> None:
    """A body that is not of the kind read raises a response error."""
    with pytest.raises(LektoResponseError, match="no RuleAskBody"):
        webhooks.read_rule_ask(recorded("document_filed")["body"])


def test_task_from_the_headers() -> None:
    """A request that asks names its task in the headers; one that does not, none."""
    asked = recorded("rule_ask")
    task = webhooks.read_task(asked["headers"])
    assert task is not None
    content = webhooks.read_rule_ask(asked["body"])
    assert task.id == str(content.task.id)
    assert task.token == content.task.token
    assert task.callback == content.task.callback
    assert task.deadline == content.task.deadline
    assert task.deadline.tzinfo is not None
    assert webhooks.read_task(recorded("rule_send")["headers"]) is None


@pytest.mark.parametrize("deadline", ["soon", "2026-11-24T10:32:44", "2026-11-24"])
def test_task_with_a_deadline_that_is_no_time(deadline: str) -> None:
    """A deadline pylekto cannot read, or one without a zone, is no answer of its models."""
    headers = {name.lower(): value for name, value in recorded("rule_ask")["headers"].items()}
    with pytest.raises(LektoResponseError, match=f"is no time with a zone: '{deadline}'"):
        webhooks.read_task(headers | {"lekto-deadline": deadline})


def test_task_without_a_deadline() -> None:
    """A task whose request names no deadline has none."""
    headers = {name.lower(): value for name, value in recorded("rule_ask")["headers"].items()}
    del headers["lekto-deadline"]
    task = webhooks.read_task(headers)
    assert task is not None
    assert task.deadline is None


TASK = webhooks.Task(
    id="0199a3c4-0000-7000-8000-0000000000aa",
    callback="https://lekto.example.com/api/v1/external/tasks/0199a3c4-0000-7000-8000-0000000000aa/result",
    token="lkt_made-up-token",
    deadline=None,
)


async def test_answer() -> None:
    """An answer goes to the callback with the task's token, as JSON."""
    sent: list[httpx2.Request] = []

    def lekto(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return httpx2.Response(204)

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(lekto)) as client:
        result = TaskAnswer(status="ok", producer="Muster Flow", answer={"paid": True})
        await webhooks.answer(TASK, result, client=client)
    assert str(sent[0].url) == TASK.callback
    assert sent[0].headers["Authorization"] == "Bearer lkt_made-up-token"
    assert json.loads(sent[0].content) == {
        "status": "ok",
        "producer": "Muster Flow",
        "answer": {"paid": True},
    }


@pytest.mark.parametrize(
    ("status", "error"), [(401, LektoAuthenticationError), (409, LektoConflictError)]
)
async def test_answer_refused(status: int, error: type[Exception]) -> None:
    """An answer to an unknown token or a stale task raises its error."""

    def lekto(_: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(status, json={"title": "Refused", "status": status})

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(lekto)) as client:
        with pytest.raises(error):
            await webhooks.answer(TASK, TaskAnswer(status="error", reason="no"), client=client)


async def test_answer_and_download_with_a_client_of_their_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a client, each makes one for the moment and closes it again."""
    made: list[httpx2.AsyncClient] = []
    original = httpx2.AsyncClient

    def lekto(request: httpx2.Request) -> httpx2.Response:
        if request.method == "GET":
            return httpx2.Response(200, content=b"RIFF made up WEBP")
        return httpx2.Response(204)

    def client(**settings: object) -> httpx2.AsyncClient:
        assert "timeout" in settings
        made.append(original(transport=httpx2.MockTransport(lekto)))
        return made[-1]

    monkeypatch.setattr(httpx2, "AsyncClient", client)
    await webhooks.answer(TASK, TaskAnswer(status="ok"))
    link = (
        "https://lekto.example.com/api/v1/external/tasks/1/files/pages/1.webp?expires=1&signature=x"
    )
    assert await webhooks.download(link) == b"RIFF made up WEBP"
    assert len(made) == 2
    assert all(client.is_closed for client in made)
