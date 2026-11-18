# pylekto

Async Python client for the [Lekto](https://github.com/lektohq/lekto) DMS REST API.

> [!NOTE]
> pylekto is at its very beginning: the repository is set up, the library itself is still to be
> designed. Nothing here is usable yet.

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
