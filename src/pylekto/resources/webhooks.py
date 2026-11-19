"""``/webhooks``: the endpoints Lekto tells about events and asks for tasks."""

from typing import TYPE_CHECKING

from pydantic import TypeAdapter

from pylekto._http import body, offset_items, query
from pylekto.models import (
    DeliveryOut,
    DeliveryPageOut,
    DeliverySummaryOut,
    WebhookCreate,
    WebhookCreated,
    WebhookOut,
    WebhookPatch,
)
from pylekto.resources._base import Resource

if TYPE_CHECKING:
    import builtins
    from collections.abc import AsyncIterator, Sequence

    from pylekto.types import DeliveryOutcome, Id

_WEBHOOKS = TypeAdapter(list[WebhookOut])


class WebhooksResource(Resource):
    """The webhooks: where Lekto sends events and tasks, signed, and the log of the deliveries.

    To receive what they send, see :mod:`pylekto.webhooks`.
    """

    async def list(self, *, owner: Id | None = None) -> builtins.list[WebhookOut]:
        """Return the caller's webhooks, or those of another user (admins).

        Args:
            owner: The user whose webhooks to list.

        Example::

            hooks = await lekto.webhooks.list()

        """
        return await self._http.call_as("GET", "/webhooks", _WEBHOOKS, params=query(owner=owner))

    async def create(self, webhook: WebhookCreate) -> WebhookCreated:
        """Create a webhook; the answer holds its secret, which Lekto never shows again.

        The webhook belongs to the token that creates it: revoking the token deletes it.

        Args:
            webhook: The name, address, events, whether it is signed, headers and body.

        Example::

            created = await lekto.webhooks.create(
                WebhookCreate(name="n8n", url="https://n8n.example.com/webhook/lekto")
            )
            store(created.secret)

        """
        return await self._http.call("POST", "/webhooks", WebhookCreated, json=body(webhook))

    async def get(self, webhook_id: Id) -> WebhookOut:
        """Return a webhook.

        Args:
            webhook_id: The webhook.

        Example::

            hook = await lekto.webhooks.get(webhook_id)

        """
        return await self._http.get(f"/webhooks/{webhook_id}", WebhookOut)

    async def update(self, webhook_id: Id, changes: WebhookPatch) -> WebhookOut:
        """Change a webhook or switch it on or off; only the values set in ``changes`` change.

        Args:
            webhook_id: The webhook.
            changes: The new values.

        Example::

            await lekto.webhooks.update(webhook_id, WebhookPatch(active=False))

        """
        return await self._http.call(
            "PATCH", f"/webhooks/{webhook_id}", WebhookOut, json=body(changes)
        )

    async def delete(self, webhook_id: Id) -> None:
        """Delete a webhook.

        Args:
            webhook_id: The webhook.

        Example::

            await lekto.webhooks.delete(webhook_id)

        """
        await self._http.call_empty("DELETE", f"/webhooks/{webhook_id}")

    async def renew_secret(self, webhook_id: Id) -> WebhookCreated:
        """Give a webhook a new secret; the old one stays valid for a while.

        Args:
            webhook_id: The webhook.

        Example::

            renewed = await lekto.webhooks.renew_secret(webhook_id)
            store(renewed.secret)

        """
        return await self._http.call("POST", f"/webhooks/{webhook_id}/secret", WebhookCreated)

    async def stop_signing(self, webhook_id: Id) -> WebhookOut:
        """Send a webhook's requests unsigned from now on.

        Args:
            webhook_id: The webhook.

        Example::

            await lekto.webhooks.stop_signing(webhook_id)

        """
        return await self._http.call("DELETE", f"/webhooks/{webhook_id}/secret", WebhookOut)

    async def test(self, webhook_id: Id) -> DeliveryOut:
        """Send a webhook a test request and return how it went.

        Args:
            webhook_id: The webhook.

        Example::

            delivery = await lekto.webhooks.test(webhook_id)
            print(delivery.outcome, delivery.status)

        """
        return await self._http.call("POST", f"/webhooks/{webhook_id}/test", DeliveryOut)

    def deliveries(
        self,
        webhook_id: Id,
        *,
        outcome: Sequence[DeliveryOutcome] | None = None,
        event_type: str | None = None,
        page_size: int | None = None,
    ) -> AsyncIterator[DeliveryOut]:
        """Iterate over the delivery log of a webhook, page after page.

        Args:
            webhook_id: The webhook.
            outcome: Only deliveries with these outcomes.
            event_type: Only deliveries of this event.
            page_size: How many deliveries each request fetches.

        Example::

            async for delivery in lekto.webhooks.deliveries(webhook_id, outcome=["gave_up"]):
                print(delivery.event_type)

        """

        async def fetch(offset: int) -> DeliveryPageOut:
            return await self.deliveries_page(
                webhook_id,
                outcome=outcome,
                event_type=event_type,
                offset=offset,
                limit=page_size,
            )

        return offset_items(fetch)

    async def deliveries_page(
        self,
        webhook_id: Id,
        *,
        outcome: Sequence[DeliveryOutcome] | None = None,
        event_type: str | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> DeliveryPageOut:
        """Return one page of the delivery log of a webhook.

        Args:
            webhook_id: The webhook.
            outcome: Only deliveries with these outcomes.
            event_type: Only deliveries of this event.
            offset: Skip so many deliveries.
            limit: How many deliveries the page holds at most.

        Example::

            page = await lekto.webhooks.deliveries_page(webhook_id, limit=20)

        """
        params = query(outcome=outcome, event_type=event_type, offset=offset, limit=limit)
        return await self._http.get(
            f"/webhooks/{webhook_id}/deliveries", DeliveryPageOut, params=params
        )

    async def deliveries_summary(
        self, webhook_id: Id, *, event_type: str | None = None
    ) -> DeliverySummaryOut:
        """Count the deliveries of a webhook by outcome.

        Args:
            webhook_id: The webhook.
            event_type: Only deliveries of this event.

        Example::

            summary = await lekto.webhooks.deliveries_summary(webhook_id)

        """
        return await self._http.get(
            f"/webhooks/{webhook_id}/deliveries/summary",
            DeliverySummaryOut,
            params=query(event_type=event_type),
        )
