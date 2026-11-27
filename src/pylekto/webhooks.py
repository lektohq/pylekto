"""Receiving what Lekto sends to a webhook: check its signature, read its body, answer a task.

Lekto signs a webhook's requests as Standard Webhooks says (https://www.standardwebhooks.com),
if the webhook has a secret (``whsec_…``): the headers ``webhook-id``, ``webhook-timestamp`` and
``webhook-signature`` (``v1,<base64 HMAC-SHA256 of id.timestamp.body>``; several while a
renewed secret still has its predecessor). What the body holds depends on what the webhook is
for: events, a rule's step that sends or asks, a model call. A request that asks is a task: its
headers ``lekto-task-*`` say where and with which one-time token to answer it.

Example::

    from pylekto import webhooks

    webhooks.verify(request.headers, request.body, secret)
    event = webhooks.read_event(request.body)
    task = webhooks.read_task(request.headers)
    if task is not None:
        await webhooks.answer(task, TaskAnswer(status="ok", answer={"paid": True}))

"""

import base64
import binascii
import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from pydantic import BaseModel, ValidationError

from pylekto._http import body, exchange, http_client
from pylekto.exceptions import LektoResponseError, WebhookVerificationError
from pylekto.models import (
    EventBody,
    ExtractContext,
    ProposeContext,
    RuleAskBody,
    RuleSendBody,
    TaskAnswer,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    import httpx2

_KEY_PREFIX = "whsec_"
_SIGNATURE_VERSION = "v1"
# How far the timestamp of a request may lie from now: an older request may be a repeated one.
TOLERANCE = timedelta(minutes=5)


def verify(
    headers: Mapping[str, str],
    content: bytes,
    secret: str | Sequence[str],
    *,
    tolerance: timedelta = TOLERANCE,
    now: datetime | None = None,
) -> None:
    """Check that Lekto signed a request with the webhook's secret, and not too long ago.

    Raises :class:`pylekto.WebhookVerificationError` if not: then do not trust the request.
    A ``secret`` that is no webhook secret raises a ``ValueError``, whatever the request.

    Args:
        headers: The request's headers (any case).
        content: The request's body, exactly as it came.
        secret: The webhook's secret (``whsec_…``), or several while one replaces another.
        tolerance: How far the request's timestamp may lie from now.
        now: The time to compare with; default: the clock.

    Example::

        webhooks.verify(request.headers, await request.body(), secret)

    """
    # First, so that a secret that is none shows with any request, a signed one or not.
    keys = [_key(key) for key in ([secret] if isinstance(secret, str) else secret)]
    named = _named(headers)
    message_id = named.get("webhook-id")
    timestamp = named.get("webhook-timestamp")
    signatures = named.get("webhook-signature")
    if not message_id or not timestamp or not signatures:
        message = "the request is not signed: webhook-id, -timestamp or -signature is missing"
        raise WebhookVerificationError(message)
    try:
        sent = int(timestamp)
    except ValueError:
        message = f"webhook-timestamp is no number: {timestamp!r}"
        raise WebhookVerificationError(message) from None
    moment = now if now is not None else datetime.now(UTC)
    if abs(moment.timestamp() - sent) > tolerance.total_seconds():
        message = "the request's timestamp lies too far from now"
        raise WebhookVerificationError(message)
    signed = f"{message_id}.{timestamp}.".encode() + content
    expected = [base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()) for key in keys]
    for entry in signatures.split():
        version, _, value = entry.partition(",")
        if version == _SIGNATURE_VERSION and any(
            hmac.compare_digest(value.encode(), digest) for digest in expected
        ):
            return
    message = "no signature of the request matches the secret"
    raise WebhookVerificationError(message)


def _named(headers: Mapping[str, str]) -> dict[str, str]:
    """Return the headers by their names in lower case: a framework may hand them in any case."""
    return {name.lower(): value for name, value in headers.items()}


def _key(secret: str) -> bytes:
    """Return the key of a webhook's secret: the bytes of its base64 after ``whsec_``."""
    if not secret.startswith(_KEY_PREFIX):
        message = "not a webhook secret: it does not start with whsec_"
        raise ValueError(message)
    try:
        return base64.b64decode(secret.removeprefix(_KEY_PREFIX), validate=True)
    except binascii.Error:
        message = "not a webhook secret: no base64 after whsec_"
        raise ValueError(message) from None


def _read[M: BaseModel](content: bytes | str, model: type[M]) -> M:
    """Read a webhook's body as a model; one that does not fit raises LektoResponseError."""
    try:
        return model.model_validate_json(content)
    except ValidationError as error:
        message = f"the webhook's body is no {model.__name__}"
        raise LektoResponseError(message) from error


def read_event(content: bytes | str) -> EventBody:
    """Read the body of an event (body ``thin`` or ``full``).

    Args:
        content: The request's body.

    Example::

        event = webhooks.read_event(await request.body())
        print(event.type, event.document_id)

    """
    return _read(content, EventBody)


def read_rule_send(content: bytes | str) -> RuleSendBody:
    """Read the body of a rule's step that sends (``rule.send``).

    Args:
        content: The request's body.

    Example::

        sent = webhooks.read_rule_send(await request.body())
        print(sent.rule.name)

    """
    return _read(content, RuleSendBody)


def read_rule_ask(content: bytes | str) -> RuleAskBody:
    """Read the body of a rule's step that asks (``rule.ask``, a task).

    Args:
        content: The request's body.

    Example::

        asked = webhooks.read_rule_ask(await request.body())
        print(asked.rule.name, asked.task.deadline)

    """
    return _read(content, RuleAskBody)


def read_propose(content: bytes | str) -> ProposeContext:
    """Read the body of a model call that proposes contact, type and fields (a task).

    Args:
        content: The request's body.

    Example::

        context = webhooks.read_propose(await request.body())

    """
    return _read(content, ProposeContext)


def read_extract(content: bytes | str) -> ExtractContext:
    """Read the body of a model call that reads fields (a task).

    Args:
        content: The request's body.

    Example::

        context = webhooks.read_extract(await request.body())

    """
    return _read(content, ExtractContext)


@dataclass(frozen=True)
class Task:
    """A request that asks: where and with which one-time token to answer it, and until when."""

    id: str
    callback: str
    token: str
    deadline: datetime | None


def read_task(headers: Mapping[str, str]) -> Task | None:
    """Return the task of a request from its headers ``lekto-task-*``, or None for none.

    A deadline that is no time raises :class:`pylekto.LektoResponseError`.

    Args:
        headers: The request's headers (any case).

    Example::

        task = webhooks.read_task(request.headers)

    """
    named = _named(headers)
    task_id = named.get("lekto-task-id")
    callback = named.get("lekto-callback")
    token = named.get("lekto-task-token")
    if not task_id or not callback or not token:
        return None
    return Task(task_id, callback, token, _deadline(named.get("lekto-deadline")))


def _deadline(header: str | None) -> datetime | None:
    """Read ``lekto-deadline`` (ISO 8601 with its zone), as the body's ``task.deadline`` is."""
    if header is None:
        return None
    try:
        deadline = datetime.fromisoformat(header)
    except ValueError:
        deadline = None
    if deadline is None or deadline.tzinfo is None:
        message = f"the webhook's lekto-deadline is no time with a zone: {header!r}"
        raise LektoResponseError(message)
    return deadline


async def answer(
    task: Task, result: TaskAnswer, *, client: httpx2.AsyncClient | None = None
) -> None:
    """Answer a task at its callback, with its one-time token.

    Lekto refuses an answer to a stale run or one given already (409), an unknown or expired
    token (401) and an answer that does not fit (422); each raises its LektoApiError.

    Args:
        task: The task, from :func:`read_task`.
        result: ``status`` ``ok`` with the ``answer``, or ``error`` with a ``reason``.
        client: An httpx2 client to send it with; default: one made for the moment.

    Example::

        await webhooks.answer(task, TaskAnswer(status="ok", answer={"paid": True}))

    """
    headers = {"Authorization": f"Bearer {task.token}"}
    async with http_client(client) as http:
        await exchange(http, "POST", task.callback, headers, json=body(result))


async def download(url: str, *, client: httpx2.AsyncClient | None = None) -> bytes:
    """Download a file a model call links (signed, valid until the task's deadline).

    Args:
        url: The link from the model call's body, with its ``expires`` and ``signature``.
        client: An httpx2 client to send it with; default: one made for the moment.

    Example::

        content = await webhooks.download(context.document.files.content)

    """
    async with http_client(client) as http:
        return (await exchange(http, "GET", url, {})).content
