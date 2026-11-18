"""Tests of mail, webhooks, push, pipeline, jobs, automation and classifier against the snapshot."""

from collections.abc import Awaitable, Callable

import pytest

from pylekto import LektoClient, LektoConflictError, LektoValidationError
from pylekto.models import (
    ConnectionTestBody,
    MailboxCreate,
    MailboxPatch,
    MailRuleCreate,
    MailRuleDryRun,
    MailRulePatch,
    PushDeviceIn,
    PushPreferencesBody,
    WebhookCreate,
    WebhookPatch,
)

from .conftest import Api, Snapshot, assert_sent, expected, plain

type Call = Callable[[LektoClient, Snapshot], Awaitable[object]]


def first(recorded: Snapshot) -> str:
    """Return the id in the path of a recording (``/<area>/<id>/…``)."""
    return recorded.segment(2)


ANSWERS: dict[str, Call] = {
    "mailboxes_create": lambda lekto, r: lekto.mailboxes.create(
        MailboxCreate.model_validate(r.json)
    ),
    "mailboxes_list": lambda lekto, _: lekto.mailboxes.list(),
    "mailboxes_get": lambda lekto, r: lekto.mailboxes.get(first(r)),
    "mailboxes_update": lambda lekto, r: lekto.mailboxes.update(
        first(r), MailboxPatch.model_validate(r.json)
    ),
    "mailboxes_test": lambda lekto, r: lekto.mailboxes.test(
        ConnectionTestBody.model_validate(r.json)
    ),
    "mailboxes_mails_page": lambda lekto, r: lekto.mailboxes.mails_page(first(r), limit=5),
    "mailboxes_mails_summary": lambda lekto, r: lekto.mailboxes.mails_summary(first(r)),
    "mail_rules_create": lambda lekto, r: lekto.mail_rules.create(
        MailRuleCreate.model_validate(r.json)
    ),
    "mail_rules_list": lambda lekto, _: lekto.mail_rules.list(),
    "mail_rules_get": lambda lekto, r: lekto.mail_rules.get(first(r)),
    "mail_rules_update": lambda lekto, r: lekto.mail_rules.update(
        first(r), MailRulePatch.model_validate(r.json)
    ),
    "mail_rules_dry_run": lambda lekto, r: lekto.mail_rules.dry_run(
        MailRuleDryRun.model_validate(r.json)
    ),
    "webhooks_create": lambda lekto, r: lekto.webhooks.create(WebhookCreate.model_validate(r.json)),
    "webhooks_list": lambda lekto, _: lekto.webhooks.list(),
    "webhooks_get": lambda lekto, r: lekto.webhooks.get(first(r)),
    "webhooks_update": lambda lekto, r: lekto.webhooks.update(
        first(r), WebhookPatch.model_validate(r.json)
    ),
    "webhooks_test": lambda lekto, r: lekto.webhooks.test(first(r)),
    "webhooks_deliveries_page": lambda lekto, r: lekto.webhooks.deliveries_page(first(r), limit=5),
    "webhooks_deliveries_summary": lambda lekto, r: lekto.webhooks.deliveries_summary(first(r)),
    "webhooks_renew_secret": lambda lekto, r: lekto.webhooks.renew_secret(first(r)),
    "webhooks_stop_signing": lambda lekto, r: lekto.webhooks.stop_signing(first(r)),
    "push_settings": lambda lekto, _: lekto.push.settings(),
    "push_add_device": lambda lekto, r: lekto.push.add_device(PushDeviceIn.model_validate(r.json)),
    "push_devices": lambda lekto, _: lekto.push.devices(),
    "push_preferences": lambda lekto, _: lekto.push.preferences(),
    "push_set_preferences": lambda lekto, r: lekto.push.set_preferences(
        PushPreferencesBody.model_validate(r.json)
    ),
    "pipeline_get": lambda lekto, _: lekto.pipeline.get(),
    "pipeline_reparse": lambda lekto, _: lekto.pipeline.reparse(),
    "pipeline_relate": lambda lekto, _: lekto.pipeline.relate(),
    "pipeline_render_pages": lambda lekto, _: lekto.pipeline.render_pages(),
    "pipeline_read_facts": lambda lekto, _: lekto.pipeline.read_facts(),
    "jobs_summary": lambda lekto, _: lekto.jobs.summary(),
    "jobs_page": lambda lekto, _: lekto.jobs.page(limit=5),
    "jobs_durations": lambda lekto, _: lekto.jobs.durations(),
    "automation_get": lambda lekto, _: lekto.automation.get(period="all", tz="Europe/Berlin"),
    "automation_signals": lambda lekto, _: lekto.automation.signals(
        period="all", tz="Europe/Berlin"
    ),
    "automation_holders": lambda lekto, _: lekto.automation.holders(),
    "automation_holder_cases": lambda lekto, _: lekto.automation.holder_cases("iban", "right"),
    "classifier_status": lambda lekto, _: lekto.classifier.status(),
    "classifier_models": lambda lekto, _: lekto.classifier.models(),
}

EMPTY: dict[str, Call] = {
    "mail_rules_delete": lambda lekto, r: lekto.mail_rules.delete(first(r)),
    "mailboxes_delete": lambda lekto, r: lekto.mailboxes.delete(first(r)),
    "webhooks_delete": lambda lekto, r: lekto.webhooks.delete(first(r)),
    "push_remove_device": lambda lekto, r: lekto.push.remove_device(r.segment(3)),
    "classifier_train": lambda lekto, _: lekto.classifier.train(),
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


async def test_paused_mailbox_is_not_fetched(api: Api, lekto: LektoClient) -> None:
    """Fetching a paused mailbox is refused with a reason."""
    recorded = api.replay("mailboxes_fetch")
    with pytest.raises(LektoValidationError) as raised:
        await lekto.mailboxes.fetch(first(recorded))
    assert raised.value.reason is not None
    assert raised.value.reason.code == "mailbox_paused"


async def test_fetch(api: Api, lekto: LektoClient) -> None:
    """Fetching an active mailbox is queued without an answer."""
    mailbox = "0199a3c4-0000-7000-8000-0000000000aa"
    api.answer("POST", f"/mailboxes/{mailbox}/fetch", 202)
    await lekto.mailboxes.fetch(mailbox)
    assert api.requests[-1].url.path == f"/api/v1/mailboxes/{mailbox}/fetch"


async def test_push_off(api: Api, lekto: LektoClient) -> None:
    """A server without notifications refuses a device."""
    recorded = api.replay("push_add_device_refused")
    with pytest.raises(LektoConflictError) as raised:
        await lekto.push.add_device(PushDeviceIn.model_validate(recorded.json))
    assert raised.value.reason is not None
    assert raised.value.reason.code == "push_off"


async def test_test_device(api: Api, lekto: LektoClient) -> None:
    """A test notification says how the push service took it."""
    device = "0199a3c4-0000-7000-8000-0000000000bb"
    api.answer("POST", f"/push/devices/{device}/test", json={"outcome": "delivered"})
    assert (await lekto.push.test_device(device)).outcome == "delivered"


async def test_retry_of_a_job_that_did_not_fail(api: Api, lekto: LektoClient) -> None:
    """Only a failed job can be tried again."""
    recorded = api.replay("jobs_retry")
    with pytest.raises(LektoConflictError, match="only a failed job"):
        await lekto.jobs.retry(first(recorded))


async def test_retry(api: Api, lekto: LektoClient) -> None:
    """A failed job tried again comes back."""
    recorded = api.replay("jobs_page")
    job = recorded.body["items"][0]
    api.answer("POST", f"/jobs/{job['id']}/retry", json=job)
    assert str((await lekto.jobs.retry(job["id"])).id) == job["id"]


async def test_jobs_list_follows_the_offset(api: Api, lekto: LektoClient) -> None:
    """``jobs.list`` yields the jobs of every page, with the filters in each request."""
    recorded = api.replay("jobs_page")
    last = {**recorded.body, "next_offset": None}
    api.answer("GET", "/jobs", json=recorded.body, when={"offset": "0"})
    api.answer("GET", "/jobs", json=last, when={"offset": str(recorded.body["next_offset"])})
    found = [
        job async for job in lekto.jobs.list(state=["done"], kind="pipeline.node", page_size=5)
    ]
    assert len(found) == 2 * len(recorded.body["items"])
    assert all(request.url.params.get_list("state") == ["done"] for request in api.requests)
    assert all(request.url.params.get("kind") == "pipeline.node" for request in api.requests)


async def test_deliveries_and_mails_iterate(api: Api, lekto: LektoClient) -> None:
    """The delivery log of a webhook and the mail log of a mailbox are iterated page by page."""
    deliveries = api.replay("webhooks_deliveries_page")
    mails = api.replay("mailboxes_mails_page")
    webhook, mailbox = first(deliveries), first(mails)
    found = [item async for item in lekto.webhooks.deliveries(webhook, outcome=["delivered"])]
    assert len(found) == len(deliveries.body["items"])
    assert api.requests[-1].url.params.get_list("outcome") == ["delivered"]
    found_mails = [item async for item in lekto.mailboxes.mails(mailbox, outcome=["failed"])]
    assert len(found_mails) == len(mails.body["items"])
    assert api.requests[-1].url.params.get_list("outcome") == ["failed"]
