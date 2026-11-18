"""``/rules`` and ``/templates``: what Lekto does with documents by itself, and its templates."""

from typing import TYPE_CHECKING

from pydantic import TypeAdapter

from pylekto._http import body, query
from pylekto.models import (
    ApplyPreviewOut,
    ApplyPreviewRequest,
    ApplyRequest,
    RuleApplicationOut,
    RuleChange,
    RuleCreate,
    RuleOut,
    RulePatch,
    RuleVersionOut,
    TemplatePreviewIn,
    TemplatePreviewOut,
    TextHitsOut,
)
from pylekto.resources._base import Resource

if TYPE_CHECKING:
    import builtins

    from pylekto.types import Id, RuleScope

_RULES = TypeAdapter(list[RuleOut])
_VERSIONS = TypeAdapter(list[RuleVersionOut])


class RulesResource(Resource):
    """The rules: conditions and actions Lekto applies to documents, with their versions."""

    async def list(
        self,
        *,
        scope: RuleScope | None = None,
        space_id: Id | None = None,
        include_disabled: bool | None = None,
        all_users: bool | None = None,
    ) -> builtins.list[RuleOut]:
        """Return the rules the caller may see, in the order Lekto applies them.

        Args:
            scope: Only global rules, or only those of spaces.
            space_id: Only the rules of this space.
            include_disabled: Also the disabled rules.
            all_users: The rules of every space (admins).

        Example::

            for rule in await lekto.rules.list(include_disabled=True):
                print(rule.name, rule.enabled)

        """
        params = query(
            scope=scope,
            space_id=space_id,
            include_disabled=include_disabled,
            all_users=all_users,
        )
        return await self._http.call_as("GET", "/rules", _RULES, params=params)

    async def create(self, rule: RuleCreate) -> RuleOut:
        """Create a rule.

        Args:
            rule: The name, priority, triggers, conditions, actions and scope.

        Example::

            rule = await lekto.rules.create(RuleCreate.model_validate(definition))

        """
        return await self._http.call("POST", "/rules", RuleOut, json=body(rule))

    async def get(self, rule_id: Id) -> RuleOut:
        """Return a rule.

        Args:
            rule_id: The rule.

        Example::

            rule = await lekto.rules.get(rule_id)

        """
        return await self._http.get(f"/rules/{rule_id}", RuleOut)

    async def replace(self, rule_id: Id, rule: RuleChange) -> RuleOut:
        """Replace a rule's definition; the rule gets a new version.

        Args:
            rule_id: The rule.
            rule: The whole new definition.

        Example::

            rule = await lekto.rules.replace(rule_id, RuleChange.model_validate(definition))

        """
        return await self._http.call("PUT", f"/rules/{rule_id}", RuleOut, json=body(rule))

    async def update(self, rule_id: Id, changes: RulePatch) -> RuleOut:
        """Enable or disable a rule.

        Args:
            rule_id: The rule.
            changes: Whether it is enabled.

        Example::

            await lekto.rules.update(rule_id, RulePatch(enabled=False))

        """
        return await self._http.call("PATCH", f"/rules/{rule_id}", RuleOut, json=body(changes))

    async def delete(self, rule_id: Id) -> None:
        """Delete a rule.

        Args:
            rule_id: The rule.

        Example::

            await lekto.rules.delete(rule_id)

        """
        await self._http.call_empty("DELETE", f"/rules/{rule_id}")

    async def versions(self, rule_id: Id) -> builtins.list[RuleVersionOut]:
        """Return every version of a rule.

        Args:
            rule_id: The rule.

        Example::

            versions = await lekto.rules.versions(rule_id)

        """
        return await self._http.call_as("GET", f"/rules/{rule_id}/versions", _VERSIONS)

    async def version(self, rule_id: Id, number: int) -> RuleVersionOut:
        """Return one version of a rule.

        Args:
            rule_id: The rule.
            number: The version, from 1.

        Example::

            first = await lekto.rules.version(rule_id, 1)

        """
        return await self._http.get(f"/rules/{rule_id}/versions/{number}", RuleVersionOut)

    async def preview_apply(self, rule_id: Id, request: ApplyPreviewRequest) -> ApplyPreviewOut:
        """Show what applying a rule to the existing documents would change.

        Args:
            rule_id: The rule.
            request: Where the page of documents starts, and how many it holds.

        Example::

            preview = await lekto.rules.preview_apply(rule_id, ApplyPreviewRequest(limit=50))

        """
        return await self._http.call(
            "POST", f"/rules/{rule_id}/apply/preview", ApplyPreviewOut, json=body(request)
        )

    async def hits(self, rule_id: Id, document_id: Id) -> TextHitsOut:
        """Return where a rule's text conditions hit a document.

        Args:
            rule_id: The rule.
            document_id: The document.

        Example::

            hits = await lekto.rules.hits(rule_id, document_id)

        """
        return await self._http.get(f"/rules/{rule_id}/apply/hits/{document_id}", TextHitsOut)

    async def apply(self, rule_id: Id, request: ApplyRequest) -> RuleApplicationOut:
        """Apply a version of a rule to existing documents, in the background.

        Args:
            rule_id: The rule.
            request: The version, the documents and the conflicts to accept.

        Example::

            application = await lekto.rules.apply(rule_id, request)
            progress = await lekto.rules.application(application.id)

        """
        return await self._http.call(
            "POST", f"/rules/{rule_id}/apply", RuleApplicationOut, json=body(request)
        )

    async def application(self, application_id: Id) -> RuleApplicationOut:
        """Return the progress of applying a rule.

        Args:
            application_id: The application, as :meth:`apply` returned it.

        Example::

            progress = await lekto.rules.application(application_id)

        """
        return await self._http.get(f"/rule-applications/{application_id}", RuleApplicationOut)

    async def preview_template(self, template: TemplatePreviewIn) -> TemplatePreviewOut:
        """Check a template and render it with a document.

        Args:
            template: The template, its purpose and the document to render it with.

        Example::

            preview = await lekto.rules.preview_template(
                TemplatePreviewIn(template="{{ title }}", document_id=document_id)
            )

        """
        return await self._http.call(
            "POST", "/templates/preview", TemplatePreviewOut, json=body(template)
        )
