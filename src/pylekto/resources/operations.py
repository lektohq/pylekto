"""Running Lekto: notifications, the pipeline, jobs, the automation's report, the classifier."""

from typing import TYPE_CHECKING, Literal

from pydantic import TypeAdapter

from pylekto._http import body, offset_items, query
from pylekto.models import (
    AutomationOut,
    ClassifierModelOut,
    ClassifierStatusOut,
    HolderCasesOut,
    HolderOutcome,
    HoldersOut,
    JobDurationsOut,
    JobOut,
    JobPageOut,
    JobsSummaryOut,
    PipelineOut,
    PushDeviceIn,
    PushDeviceOut,
    PushPreferencesBody,
    PushSettingsOut,
    PushTestOut,
    QueuedOut,
    SignalsOut,
)
from pylekto.resources._base import Resource

if TYPE_CHECKING:
    import builtins
    from collections.abc import AsyncIterator, Sequence

    from pylekto.models import Channel, IdentifierKind, JobState, Period
    from pylekto.types import Id

_DEVICES = TypeAdapter(list[PushDeviceOut])
_MODELS = TypeAdapter(list[ClassifierModelOut])


class PushResource(Resource):
    """Push notifications: the caller's devices and what they are told about."""

    async def settings(self) -> PushSettingsOut:
        """Return whether this server sends notifications, and its public key.

        Example::

            settings = await lekto.push.settings()

        """
        return await self._http.get("/push", PushSettingsOut)

    async def devices(self) -> builtins.list[PushDeviceOut]:
        """Return the caller's devices that receive notifications.

        Example::

            devices = await lekto.push.devices()

        """
        return await self._http.call_as("GET", "/push/devices", _DEVICES)

    async def add_device(self, device: PushDeviceIn) -> PushDeviceOut:
        """Receive notifications on a device (its Web Push subscription).

        Args:
            device: The subscription's endpoint and keys, a name and the language.

        Example::

            device = await lekto.push.add_device(PushDeviceIn.model_validate(subscription))

        """
        return await self._http.call("POST", "/push/devices", PushDeviceOut, json=body(device))

    async def remove_device(self, device_id: Id) -> None:
        """Receive no notifications on a device any more.

        Args:
            device_id: The device.

        Example::

            await lekto.push.remove_device(device_id)

        """
        await self._http.call_empty("DELETE", t"/push/devices/{device_id}")

    async def test_device(self, device_id: Id) -> PushTestOut:
        """Send a device a test notification.

        Args:
            device_id: The device.

        Example::

            result = await lekto.push.test_device(device_id)

        """
        return await self._http.call("POST", t"/push/devices/{device_id}/test", PushTestOut)

    async def preferences(self) -> PushPreferencesBody:
        """Return what the caller is told about.

        Example::

            preferences = await lekto.push.preferences()

        """
        return await self._http.get("/push/preferences", PushPreferencesBody)

    async def set_preferences(self, preferences: PushPreferencesBody) -> PushPreferencesBody:
        """Choose what the caller is told about.

        Args:
            preferences: The kinds of notification, and whether they show titles.

        Example::

            await lekto.push.set_preferences(
                PushPreferencesBody(kinds=["waiting"], titles=False)
            )

        """
        return await self._http.call(
            "PUT", "/push/preferences", PushPreferencesBody, json=body(preferences)
        )


class PipelineResource(Resource):
    """The processing graph, and running parts of it again for every document (admins)."""

    async def get(self) -> PipelineOut:
        """Return the processing graph: its nodes, lanes and the steps between them.

        Example::

            pipeline = await lekto.pipeline.get()

        """
        return await self._http.get("/pipeline", PipelineOut)

    async def reparse(self) -> QueuedOut:
        """Read the text of every document again, in the background.

        Example::

            queued = await lekto.pipeline.reparse()

        """
        return await self._http.call("POST", "/pipeline/reparse", QueuedOut)

    async def relate(self) -> QueuedOut:
        """Find the relations of every document again, in the background.

        Example::

            queued = await lekto.pipeline.relate()

        """
        return await self._http.call("POST", "/pipeline/relate", QueuedOut)

    async def render_pages(self) -> QueuedOut:
        """Render the missing page images, in the background.

        Example::

            queued = await lekto.pipeline.render_pages()

        """
        return await self._http.call("POST", "/pipeline/render-pages", QueuedOut)

    async def read_facts(self) -> QueuedOut:
        """Read the facts of every document again, in the background.

        Example::

            queued = await lekto.pipeline.read_facts()

        """
        return await self._http.call("POST", "/pipeline/read-facts", QueuedOut)


class JobsResource(Resource):
    """The jobs of the worker: what waits, runs, failed (admins)."""

    async def summary(self) -> JobsSummaryOut:
        """Count the jobs by kind and state.

        Example::

            summary = await lekto.jobs.summary()

        """
        return await self._http.get("/jobs/summary", JobsSummaryOut)

    def list(
        self,
        *,
        state: Sequence[JobState] | None = None,
        kind: str | None = None,
        page_size: int | None = None,
    ) -> AsyncIterator[JobOut]:
        """Iterate over the jobs, page after page.

        Args:
            state: Only jobs in these states.
            kind: Only jobs of this kind, such as ``pipeline.node``.
            page_size: How many jobs each request fetches.

        Example::

            async for job in lekto.jobs.list(state=["failed"]):
                print(job.kind, job.error)

        """

        async def fetch(offset: int) -> JobPageOut:
            return await self.page(state=state, kind=kind, offset=offset, limit=page_size)

        return offset_items(fetch)

    async def page(
        self,
        *,
        state: Sequence[JobState] | None = None,
        kind: str | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> JobPageOut:
        """Return one page of the jobs.

        Args:
            state: Only jobs in these states.
            kind: Only jobs of this kind, such as ``pipeline.node``.
            offset: Skip so many jobs.
            limit: How many jobs the page holds at most.

        Example::

            page = await lekto.jobs.page(state=["failed"], limit=20)

        """
        params = query(state=state, kind=kind, offset=offset, limit=limit)
        return await self._http.get("/jobs", JobPageOut, params=params)

    async def durations(self) -> JobDurationsOut:
        """Return how long the jobs wait and run, by kind.

        Example::

            durations = await lekto.jobs.durations()

        """
        return await self._http.get("/jobs/durations", JobDurationsOut)

    async def retry(self, job_id: Id) -> JobOut:
        """Try a failed job again.

        Args:
            job_id: The job.

        Example::

            job = await lekto.jobs.retry(job_id)

        """
        return await self._http.call("POST", t"/jobs/{job_id}/retry", JobOut)


class AutomationResource(Resource):
    """How well Lekto worked by itself: lanes, signals and the holders of identifiers."""

    async def get(
        self,
        *,
        channel: Sequence[Channel] | None = None,
        period: Period | None = None,
        tz: str | None = None,
    ) -> AutomationOut:
        """Return how the automation did: documents by lane, over time.

        Args:
            channel: Only documents that came in these ways.
            period: The time to look back on.
            tz: The IANA time zone the days and months begin in.

        Example::

            report = await lekto.automation.get(period="30d", tz="Europe/Berlin")

        """
        params = query(channel=channel, period=period, tz=tz)
        return await self._http.get("/automation", AutomationOut, params=params)

    async def signals(
        self,
        *,
        channel: Sequence[Channel] | None = None,
        period: Period | None = None,
        tz: str | None = None,
    ) -> SignalsOut:
        """Return how often each signal hit.

        Args:
            channel: Only documents that came in these ways.
            period: The time to look back on.
            tz: The IANA time zone the days and months begin in.

        Example::

            signals = await lekto.automation.signals(period="12m")

        """
        params = query(channel=channel, period=period, tz=tz)
        return await self._http.get("/automation/signals", SignalsOut, params=params)

    async def holders(self) -> HoldersOut:
        """Return how the holders Lekto found compare with the decisions at the contacts.

        Example::

            holders = await lekto.automation.holders()

        """
        return await self._http.get("/automation/holders", HoldersOut)

    async def holder_cases(
        self, measure: IdentifierKind | Literal["recommendation"], outcome: HolderOutcome
    ) -> HolderCasesOut:
        """Return the decisions behind one number of :meth:`holders`.

        Args:
            measure: The kind of identifier, or ``recommendation``.
            outcome: Which outcome to show the cases of.

        Example::

            cases = await lekto.automation.holder_cases("iban", "learned_rejected")

        """
        params = query(measure=measure, outcome=outcome)
        return await self._http.get("/automation/holders/cases", HolderCasesOut, params=params)


class ClassifierResource(Resource):
    """The classifier that proposes contact and document type from the text."""

    async def status(self) -> ClassifierStatusOut:
        """Return the classifier's state: its model, accuracy and whether it trains.

        Example::

            status = await lekto.classifier.status()

        """
        return await self._http.get("/classifier", ClassifierStatusOut)

    async def models(self) -> builtins.list[ClassifierModelOut]:
        """Return every model trained.

        Example::

            models = await lekto.classifier.models()

        """
        return await self._http.call_as("GET", "/classifier/models", _MODELS)

    async def train(self) -> None:
        """Train the classifier, in the background.

        Example::

            await lekto.classifier.train()

        """
        await self._http.call_empty("POST", "/classifier/train")
