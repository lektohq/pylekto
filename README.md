# pylekto

Async Python client for the [Lekto](https://github.com/lektohq/lekto) DMS REST API.

pylekto reaches every operation of the API an API token may use: `auth` (who calls), `health`,
`version` (and whether a newer Lekto is out), `documents` (with uploads, downloads, facts, page
edits, changes of many documents), `search`, `relations`, the master data (`contacts`,
`document_types`, `tags`, `fields`), `spaces`, `users`, `identifiers`, the `open_identifiers`, the
`inbox`, the `expected` documents, `lenses`, `rules` (with templates), `mailboxes`, `mail_rules`,
`webhooks`, `push`, the `pipeline`, `jobs`, `automation`, the `classifier` and the `events` as they
happen. `pylekto.webhooks` receives what Lekto sends to a webhook.

```python
import asyncio

from pylekto import LektoClient


async def main() -> None:
    async with LektoClient("https://lekto.example.com", "lekto_…") as lekto:
        me = await lekto.auth.me()
        print(me.user.username, me.token_scope)

        async for document in lekto.documents.list(lane=["red"]):
            print(document.title)

        inbox = await lekto.documents.count(in_inbox=True)
        print(inbox.total)

        result = await lekto.search.page("electricity bill", limit=5)
        print([hit.document.title for hit in result.items])

        async for event in lekto.events.listen():  # until the stream ends or raises a LektoError
            print(event.type, event.document_id)


asyncio.run(main())
```

- **Token only.** A personal API token from Lekto; its rights (chosen one by one, or a preset:
  `read`, `read_write`, `upload`) decide what the client may do, and `lekto.auth.me()` names them.
- **Your own httpx2 client** if you like (`LektoClient(url, token, client=...)`): pylekto sends its
  requests with it and leaves it open.
- **Errors raise.** Each subclass of `LektoError` says what went wrong; a refusal carries Lekto's
  problem details with a reason code. pylekto repeats nothing: whether to try again is up to you.
- **New values read.** A choice in the models is `Literal[...] | Unknown`: a value that a newer
  Lekto sends and this pylekto does not know arrives as `pylekto.Unknown` (a `str`) instead of
  failing; `case Unknown():` matches it.
- **One version of the API.** pylekto speaks the API `pylekto.API_VERSION` of Lekto
  `pylekto.LEKTO_VERSION`; its models are generated from that release's OpenAPI description.
  From 0.2.0 on, pylekto's version names that API: pylekto `X.Y.Z` speaks the API `X.Y`, so
  `pylekto==0.3.*` stays with the API 0.3. Withdrawn: 0.3.0 (API 0.2) and 0.4.0 (API 0.3, again
  as 0.3.1).
  Connecting to a Lekto whose API may differ warns (`LektoVersionWarning`): during the beta
  (`0.x`) every other MINOR, from `1.0` on another MAJOR or a smaller MINOR.
  `pylekto.api_fit(lekto.api_version)` returns the same rule as `"fits"`, `"newer"` (update
  pylekto), `"older"` (update Lekto) or `"unknown"` (no or an unreadable version).

### Receiving webhooks

Lekto signs what it sends to a webhook (Standard Webhooks). In whatever web framework receives it:

```python
from pylekto import webhooks
from pylekto.models import TaskAnswer


async def receive(headers: dict[str, str], body: bytes) -> None:
    webhooks.verify(headers, body, "whsec_…")  # raises WebhookVerificationError
    asked = webhooks.read_rule_ask(body)  # or read_event, read_rule_send, read_propose …
    task = webhooks.read_task(headers)
    if task is not None:
        await webhooks.answer(task, TaskAnswer(status="ok", answer={"paid": True}))
```

## Requirements

Python 3.14 or newer.

## Development

Open the repository in its devcontainer (`.devcontainer/`); it runs `script/setup`, which
installs the dependencies and the Git hooks. Outside the devcontainer, `script/setup` creates a
local `.venv` first.

```sh
uv sync
uv run prek run --all-files   # every check: Ruff, mypy, pytest with coverage, typos, yamllint
```

## License

MIT, see [LICENSE](LICENSE).
