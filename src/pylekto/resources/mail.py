"""``/mailboxes`` and ``/mail-rules``: documents that come in by mail (admins)."""

from typing import TYPE_CHECKING

from pydantic import TypeAdapter

from pylekto._http import body, offset_items, query
from pylekto.models import (
    ConnectionTestBody,
    ConnectionTestOut,
    DryRunMailOut,
    MailboxCreate,
    MailboxOut,
    MailboxPatch,
    MailOut,
    MailPageOut,
    MailRuleCreate,
    MailRuleDryRun,
    MailRuleOut,
    MailRulePatch,
    MailSummaryOut,
)
from pylekto.resources._base import Resource

if TYPE_CHECKING:
    import builtins
    from collections.abc import AsyncIterator, Sequence

    from pylekto.models import MailOutcome
    from pylekto.types import Id

_MAILBOXES = TypeAdapter(list[MailboxOut])
_MAIL_RULES = TypeAdapter(list[MailRuleOut])
_DRY_RUN = TypeAdapter(list[DryRunMailOut])


class MailboxesResource(Resource):
    """The mailboxes Lekto fetches from (IMAP), and the log of the mails they fetched."""

    async def list(self) -> builtins.list[MailboxOut]:
        """Return every mailbox.

        Example::

            for mailbox in await lekto.mailboxes.list():
                print(mailbox.name, mailbox.enabled)

        """
        return await self._http.call_as("GET", "/mailboxes", _MAILBOXES)

    async def create(self, mailbox: MailboxCreate) -> MailboxOut:
        """Create a mailbox.

        Args:
            mailbox: The connection, the folders, how often and from when to fetch.

        Example::

            mailbox = await lekto.mailboxes.create(MailboxCreate.model_validate(settings))

        """
        return await self._http.call("POST", "/mailboxes", MailboxOut, json=body(mailbox))

    async def test(self, connection: ConnectionTestBody) -> ConnectionTestOut:
        """Test a connection to a mail server, and list its folders.

        Args:
            connection: Host, port, security and sign-in (or a mailbox's stored password).

        Example::

            result = await lekto.mailboxes.test(ConnectionTestBody.model_validate(settings))

        """
        return await self._http.call(
            "POST", "/mailboxes/test", ConnectionTestOut, json=body(connection)
        )

    async def get(self, mailbox_id: Id) -> MailboxOut:
        """Return a mailbox.

        Args:
            mailbox_id: The mailbox.

        Example::

            mailbox = await lekto.mailboxes.get(mailbox_id)

        """
        return await self._http.get(f"/mailboxes/{mailbox_id}", MailboxOut)

    async def update(self, mailbox_id: Id, changes: MailboxPatch) -> MailboxOut:
        """Change a mailbox; only the values set in ``changes`` change.

        Args:
            mailbox_id: The mailbox.
            changes: The new values.

        Example::

            await lekto.mailboxes.update(mailbox_id, MailboxPatch(enabled=False))

        """
        return await self._http.call(
            "PATCH", f"/mailboxes/{mailbox_id}", MailboxOut, json=body(changes)
        )

    async def delete(self, mailbox_id: Id) -> None:
        """Delete a mailbox and its mail rules.

        Args:
            mailbox_id: The mailbox.

        Example::

            await lekto.mailboxes.delete(mailbox_id)

        """
        await self._http.call_empty("DELETE", f"/mailboxes/{mailbox_id}")

    async def fetch(self, mailbox_id: Id) -> None:
        """Fetch a mailbox now, in the background.

        Args:
            mailbox_id: The mailbox.

        Example::

            await lekto.mailboxes.fetch(mailbox_id)

        """
        await self._http.call_empty("POST", f"/mailboxes/{mailbox_id}/fetch")

    def mails(
        self,
        mailbox_id: Id,
        *,
        outcome: Sequence[MailOutcome] | None = None,
        rule_id: Id | None = None,
        page_size: int | None = None,
    ) -> AsyncIterator[MailOut]:
        """Iterate over the log of the mails a mailbox fetched, page after page.

        Args:
            mailbox_id: The mailbox.
            outcome: Only mails with these outcomes.
            rule_id: Only mails this mail rule took.
            page_size: How many mails each request fetches.

        Example::

            async for mail in lekto.mailboxes.mails(mailbox_id, outcome=["failed"]):
                print(mail.subject)

        """

        async def fetch(offset: int) -> MailPageOut:
            return await self.mails_page(
                mailbox_id, outcome=outcome, rule_id=rule_id, offset=offset, limit=page_size
            )

        return offset_items(fetch)

    async def mails_page(
        self,
        mailbox_id: Id,
        *,
        outcome: Sequence[MailOutcome] | None = None,
        rule_id: Id | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> MailPageOut:
        """Return one page of the log of the mails a mailbox fetched.

        Args:
            mailbox_id: The mailbox.
            outcome: Only mails with these outcomes.
            rule_id: Only mails this mail rule took.
            offset: Skip so many mails.
            limit: How many mails the page holds at most.

        Example::

            page = await lekto.mailboxes.mails_page(mailbox_id, limit=20)
            print(page.total)

        """
        params = query(outcome=outcome, rule_id=rule_id, offset=offset, limit=limit)
        return await self._http.get(f"/mailboxes/{mailbox_id}/mails", MailPageOut, params=params)

    async def mails_summary(self, mailbox_id: Id, *, rule_id: Id | None = None) -> MailSummaryOut:
        """Count the mails of a mailbox's log by outcome.

        Args:
            mailbox_id: The mailbox.
            rule_id: Only mails this mail rule took.

        Example::

            summary = await lekto.mailboxes.mails_summary(mailbox_id)

        """
        return await self._http.get(
            f"/mailboxes/{mailbox_id}/mails/summary", MailSummaryOut, params=query(rule_id=rule_id)
        )


class MailRulesResource(Resource):
    """The mail rules: which mails of a mailbox become documents, for whom, and what then."""

    async def list(self) -> builtins.list[MailRuleOut]:
        """Return every mail rule.

        Example::

            rules = await lekto.mail_rules.list()

        """
        return await self._http.call_as("GET", "/mail-rules", _MAIL_RULES)

    async def create(self, rule: MailRuleCreate) -> MailRuleOut:
        """Create a mail rule.

        Args:
            rule: The mailbox, name, conditions, the parts to take, for whom and what then.

        Example::

            rule = await lekto.mail_rules.create(MailRuleCreate.model_validate(definition))

        """
        return await self._http.call("POST", "/mail-rules", MailRuleOut, json=body(rule))

    async def dry_run(self, rule: MailRuleDryRun) -> builtins.list[DryRunMailOut]:
        """Show which mails of the mailbox a mail rule would take, without taking them.

        Args:
            rule: The rule to try, and the stored rule it would replace.

        Example::

            mails = await lekto.mail_rules.dry_run(MailRuleDryRun.model_validate(definition))

        """
        return await self._http.call_as("POST", "/mail-rules/dry-run", _DRY_RUN, json=body(rule))

    async def get(self, rule_id: Id) -> MailRuleOut:
        """Return a mail rule.

        Args:
            rule_id: The mail rule.

        Example::

            rule = await lekto.mail_rules.get(rule_id)

        """
        return await self._http.get(f"/mail-rules/{rule_id}", MailRuleOut)

    async def update(self, rule_id: Id, changes: MailRulePatch) -> MailRuleOut:
        """Change a mail rule; only the values set in ``changes`` change.

        Args:
            rule_id: The mail rule.
            changes: The new values.

        Example::

            await lekto.mail_rules.update(rule_id, MailRulePatch(enabled=False))

        """
        return await self._http.call(
            "PATCH", f"/mail-rules/{rule_id}", MailRuleOut, json=body(changes)
        )

    async def delete(self, rule_id: Id) -> None:
        """Delete a mail rule.

        Args:
            rule_id: The mail rule.

        Example::

            await lekto.mail_rules.delete(rule_id)

        """
        await self._http.call_empty("DELETE", f"/mail-rules/{rule_id}")
