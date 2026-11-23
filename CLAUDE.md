# CLAUDE.md

pylekto (technical name `pylekto`, on PyPI) is the async Python client of the Lekto DMS REST API
(`lektohq/lekto`). Python 3.14 only, because Home Assistant requires it. The architecture is
decided in `.knowledge/decisions/2026-11-18-pylekto-architecture.md`, the order of the work in
`.knowledge/plans/pylekto-library.md`.

## Layout

| Path | Content |
| --- | --- |
| `src/pylekto/` | The package (typed: `py.typed`): `client.py` (`LektoClient`), `_http.py` (requests, problem details as exceptions, pages), `exceptions.py`, `resources/` (one module per area of the API) |
| `src/pylekto/webhooks.py` | Receiving webhooks: `verify` (Standard Webhooks), `read_*` for each body, `task`, `answer`, `download` |
| `src/pylekto/models.py` | The models, generated from `openapi.json` by `script/generate_models.py` (datamodel-codegen, settings in `pyproject.toml`); never edited by hand |
| `openapi.json`, `src/pylekto/_lekto.py` | Lekto's OpenAPI description of the release `LEKTO_VERSION`, that version and the version of its API (`API_VERSION`, `info.version`), which is also the MAJOR.MINOR of pylekto's own version |
| `tests/` | pytest; `tests/ruff.toml` adjusts the rules for tests; `tests/snapshot/` the recorded answers of a Lekto instance, one JSON file per request |
| `script/` | `setup` (once: dependencies, Git hooks), `bootstrap` (every start of the devcontainer: dependencies), `generate_models.py` (the models), `update_openapi.py` (the description of another Lekto release), `record_snapshot.py` (the snapshot) |
| `.devcontainer/`, `Dockerfile.dev` | Devcontainer: Python 3.14, uv, gh, Claude Code; the virtual environment lives in `/home/vscode/.local/dev-venv` |
| `.github/` | Workflows (`ci.yml`, `release.yml`, `site.yml` (rebuilds lekto.dev on a release), Release Drafter, labels, stale, lock), labels, templates, `scripts/` (the version of the next release, the test of the action pins) |
| `.knowledge/` | The knowledge in German as small notes with frontmatter; start with `INDEX.md` and `README.md`. A checkout of the private repository `lektohq/lekto-knowledge`, shared with lekto and ignored by this one (see "Working style") |

## Commands

```sh
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest                    # with coverage; fails below 95 %
uv run typos
uv run yamllint .
uv run prek run --all-files      # every hook at once, as before each commit
python3 -m unittest discover -s .github/scripts   # the next version, the pins of the actions
uv run python script/generate_models.py   # the models from openapi.json again
uv run python script/update_openapi.py v0.16.0   # another Lekto release: description, version, models
```

Run all checks before every commit; `script/setup` installs them as a Git hook (`prek install`).

pylekto X.Y.Z speaks Lekto's API X.Y (`API_VERSION`); Z counts its releases for that API
(`.knowledge/decisions/2026-11-21-pylekto-version.md`). The Release Drafter gets the version from
`.github/scripts/release_version.py`: one past the highest tag vX.Y.* (a small `v`), so 0.3.0 and
0.4.0, which PyPI holds for the APIs 0.2 and 0.3 and which are withdrawn, are skipped. Publishing a
release on GitHub runs `.github/workflows/release.yml`: it stops unless the tag names
`API_VERSION`, sets the version from the tag, builds the package (`uv build`) and uploads it to
PyPI by Trusted Publishing (environment `release`, no token). The repository carries the version
`0.0.0`. Every action in a workflow is pinned to its commit with the version in a comment (`uses:
actions/checkout@<sha> # v7.0.1`, which Renovate updates); a test in `.github/scripts` fails on a
tag.

## Rules

- The client sends requests and reads the answers, nothing else: no repetitions, no waiting, no
  caching. Errors raise a subclass of `LektoError`; whether to try again is the caller's logic.
- Only API tokens: no sign-in with a password, no session. Endpoints that need a session stay out.
- Every area of the API is a class in `resources/` with explicit methods (`get`, `list`, `create`,
  …) that take and return the generated models under their OpenAPI names. A list that comes in
  pages has `page(...)` (one page, as Lekto answers it) and `list(...)` (an async iterator over
  every item: `_http.cursor_items`, `_http.offset_items`, or `_http.total_items` for a page that
  gives only its total). A body that is a single required
  value (`SearchIn.q`, `MoveRequest.space_id`, `RelateIn.document_id`) is passed as that value.
  Path ids are named for what they are (`document_id`, not `id`) and take `UUID` or `str`
  (`types.Id`). Query filters the description gives no model are `TypedDict`s in `types.py`
  (`DocumentFilter`), taken as keyword arguments, and so are choices the generator wrote inline
  (`IdentifierKind`, `TagScope`, `OpenSource`); tests keep them equal to the description's. Form fields always go as parts of a multipart body (`(None, text)`): Lekto reads
  them nowhere else.
- What Lekto sends to a webhook is recorded as it came (`tests/snapshot/webhooks/`, with the secret
  of a webhook deleted at the end): `record_snapshot.py --receiver <url Lekto reaches>
  --receiver-log <file a receiving server writes>`; the tests verify Lekto's real signatures.
- Streams (`GET /events`) are read line by line (`Http.lines`) with a read timeout of 30 s
  (`STREAM`), twice the 15 s after which Lekto sends a keep-alive comment, and parsed by `_sse.py`
  as the HTML standard says; a recording of a stream holds its text (`Recording.listen`, with a
  request that triggers events).
- `models.py` is generated; a test fails if it differs from what `script/generate_models.py`
  writes from `openapi.json`. Ruff and typos leave it out; mypy checks it.
- Every choice (an `enum` of strings, in the models and in `types.py`) is `Literal[...] | Unknown`:
  a value a newer Lekto sends and pylekto does not know reads as `pylekto.Unknown` (a `str`)
  instead of failing, and goes back to Lekto as a filter. A plain `str` is no `Unknown`, so type
  checkers keep requests to the known values. Unions with a discriminator stay closed.
- Connecting compares the version of Lekto's API (`api_version` of `GET /auth/me`) with
  `API_VERSION` and warns (`LektoVersionWarning`) when it may not fit: during the beta (`0.x`)
  every other MINOR, from `1.0` on another MAJOR or a smaller MINOR of the server; a Lekto
  without an API version as well. Lekto's own version is not compared. The rule is public as
  `api_fit(api_version)`: `"fits"`, `"newer"`, `"older"` or `"unknown"` (no or an unreadable
  version), so callers such as Home Assistant need not catch the warning.
- Ruff (`select = ["ALL"]`) and mypy (`strict`) report nothing on new or changed code.
- No suppressions (`# noqa`, `# type: ignore` and the like): fix the cause. Only `# noqa: F401` on
  a re-export in an `__init__.py` is allowed without asking.
- Dependencies state lower bounds only (`httpx2>=2.14`); `uv.lock` pins the development
  environment. The library must install beside Home Assistant, which pins its own versions. New
  dependencies need agreement first.
- Tests run against a snapshot of the API, never against a live instance: `tests/snapshot/<name>.json`
  holds a request and Lekto's answer. `script/record_snapshot.py` records them from a throwaway
  Lekto of the release `LEKTO_VERSION` filled with the synthetic documents of
  `lekto/examples/documents` (its docstring says how); a new area adds its `Recording`s there.
  In a test, `api.replay(name)` answers the request as Lekto did; `tests/test_snapshot.py` checks
  every recording against the model the OpenAPI description names for its answer.
  `tests/test_description.py` fails when an operation a token may use has no method, or neither a
  recording nor an entry in its `UNRECORDED` with the reason (a new Lekto release adds one).
- This repository will be public: every value in code, tests, fixtures, commits and pull requests
  is made up. No real names, companies, IBANs, addresses, numbers, hosts or tokens. The one
  exception: the webhook recordings (`tests/snapshot/webhooks/`) keep the signing secret and task
  tokens of a deleted webhook on a throwaway instance, and its address `127.0.0.1`, because the
  signature covers the body and the tests verify Lekto's own.
- Comments explain *why* (constraints, surprises, workarounds), never *what*; one short line or
  none. No section or divider comments.
- Keep try clauses minimal: wrap only the statement that can raise, catch only the expected
  exceptions. An `@asynccontextmanager` always uses `try`/`finally`.
- Docstrings: public APIs with a one-line summary, Google-style `Args:` and an `Example::` block
  (reStructuredText, no Markdown fences); private `_` symbols one or two lines on *why* only.

## Labels

Every pull request carries exactly one category label from `.github/labels.yml` (`new-feature`,
`bugfix`, `enhancement`, `refactor`, `performance`, `maintenance`, `ci`, `documentation`,
`dependencies`, `dev-deps`, `breaking-change`); a check fails without one, and the Release Drafter
sorts the release notes by them. Renovate (`renovate.json`, the hosted app) labels its own:
`dependencies`, `dev-deps` (development dependencies, the devcontainer, prek's hooks), `ci`
(actions); it suggests a version 10 days after its release at the earliest.
The version follows the API, not the labels: a pull request that brings another `API_VERSION`
starts the next release line, every other release counts Z on. pylekto is in beta like Lekto and
its API: no pull request carries `breaking-change`, even one that breaks. Tobi publishes and tags
the release from the draft.
A pull request a user notices fills the section `## Release notes` of its description with one
sentence on what changes for them; it stands under the title in the release notes.

## Language

Code, comments, commit messages and documentation (README, docstrings) are English. The notes in
`.knowledge/` are German.

## Working style

- Plan first: read the notes in `.knowledge/` (`INDEX.md` first, area `pylekto`), propose a plan,
  wait for approval.
- Decisions, plans, open points, working rules and history live only in the private repository
  `lektohq/lekto-knowledge`, checked out at `.knowledge/` (after a fresh clone:
  `git clone https://github.com/lektohq/lekto-knowledge.git .knowledge`). lekto has its own checkout
  of it: `git pull` before working, and commit and push every change straight to its `main`
  (`uv run tools/index.py` checks the notes and writes the index); nothing stays only local, and
  none of it goes into this repository. Notes about pylekto carry the area `pylekto` and their
  `code:` paths the prefix `pylekto/`. Docstrings point at notes as `.knowledge/<folder>/<name>.md`.
- If something is unclear or a decision is missing, ask before implementing. Do not deviate from
  the decisions in `.knowledge/decisions/` on your own.
- Small, thematically separate commits. Keep answers short and precise.
