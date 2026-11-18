# pylekto

Async Python client for the [Lekto](https://github.com/lektohq/lekto) DMS REST API.

> [!NOTE]
> pylekto is at its beginning: the client stands, the areas of the API follow one by one. So far
> it covers `auth` (who calls), `health`, `documents` (with uploads, downloads, facts, page
> edits, changes of many documents), `search` and `relations`.

```python
import asyncio

from pylekto import LektoClient


async def main() -> None:
    async with LektoClient("https://lekto.example.com", "lekto_…") as lekto:
        me = await lekto.auth.me()
        print(me.user.username, me.token_scope)

        async for document in lekto.documents.list(lane=["red"]):
            print(document.title)

        result = await lekto.search.page("electricity bill", limit=5)
        print([hit.document.title for hit in result.items])


asyncio.run(main())
```

- **Token only.** A personal API token from Lekto; its scope (`read`, `upload`, `read_write`)
  decides what the client may do.
- **Your own httpx2 client** if you like (`LektoClient(url, token, client=...)`): pylekto sends its
  requests with it and leaves it open.
- **Errors raise.** Each subclass of `LektoError` says what went wrong; a refusal carries Lekto's
  problem details with a reason code. pylekto repeats nothing: whether to try again is up to you.
- **One Lekto release.** pylekto speaks the API of `pylekto.LEKTO_VERSION`; its models are
  generated from that release's OpenAPI description. While Lekto is in beta, each release may
  change its API, so connecting to another version warns (`LektoVersionWarning`).

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
