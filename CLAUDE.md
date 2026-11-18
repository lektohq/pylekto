# CLAUDE.md

pylekto (technical name `pylekto`, on PyPI) is the async Python client of the Lekto DMS REST API
(`lektohq/lekto`). Python 3.14 only, because Home Assistant requires it. The library is not
designed yet; this file grows with it.

## Layout

| Path | Content |
| --- | --- |
| `src/pylekto/` | The package (typed: `py.typed`) |
| `tests/` | pytest; `tests/ruff.toml` adjusts the rules for tests |
| `script/` | `setup` (once: dependencies, Git hooks), `bootstrap` (every start of the devcontainer: dependencies) |
| `.devcontainer/`, `Dockerfile.dev` | Devcontainer: Python 3.14, uv, gh, Claude Code; the virtual environment lives in `/home/vscode/.local/dev-venv` |
| `.github/` | Workflows (`ci.yml`, `release.yml`, Release Drafter, labels, stale, lock), labels, templates, `scripts/` (the test of the action pins) |
| `.idea/` | The knowledge in German as small notes with frontmatter; start with `INDEX.md` and `README.md`. A checkout of the private repository `lektohq/lekto-knowledge`, shared with lekto and ignored by this one (see "Working style") |

## Commands

```sh
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest                    # with coverage; fails below 95 %
uv run typos
uv run yamllint .
uv run prek run --all-files      # every hook at once, as before each commit
python3 -m unittest discover -s .github/scripts   # every action is pinned to a commit
```

Run all checks before every commit; `script/setup` installs them as a Git hook (`prek install`).

Publishing a release on GitHub runs `.github/workflows/release.yml`: it sets the version from the
tag, builds the package (`uv build`) and uploads it to PyPI by Trusted Publishing (environment
`release`, no token). The repository carries the version `0.0.0`. Every action in a workflow is
pinned to its commit with the version in a comment (`uses: actions/checkout@<sha> # v7.0.1`,
which Renovate updates); a test in `.github/scripts` fails on a tag.

## Rules

- Ruff (`select = ["ALL"]`) and mypy (`strict`) report nothing on new or changed code.
- No suppressions (`# noqa`, `# type: ignore` and the like): fix the cause. Only `# noqa: F401` on
  a re-export in an `__init__.py` is allowed without asking.
- Dependencies state lower bounds only (`httpx2>=2.14`); `uv.lock` pins the development
  environment. The library must install beside Home Assistant, which pins its own versions. New
  dependencies need agreement first.
- Tests run against a snapshot of the API: JSON recorded from a Lekto instance filled with the
  synthetic documents of `lekto/examples/documents`, and a copy of lekto's `web/openapi.json`.
  Never against a live instance.
- This repository will be public: every value in code, tests, fixtures, commits and pull requests
  is made up. No real names, companies, IBANs, addresses, numbers, hosts or tokens.
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
builds the release notes from them. Renovate (`renovate.json`, the hosted app) labels its own:
`dependencies`, `dev-deps` (development dependencies, the devcontainer, prek's hooks), `ci`
(actions); it suggests a version 10 days after its release at the earliest.
The version bump follows the labels (`breaking-change` or `major`: major; `new-feature` or
`minor`: minor; else patch). Tobi publishes and tags the release from the draft.
A pull request a user notices fills the section `## Release notes` of its description with one
sentence on what changes for them; it stands under the title in the release notes.

## Language

Code, comments, commit messages and documentation (README, docstrings) are English. The notes in
`.idea/` are German.

## Working style

- Plan first: read the notes in `.idea/` (`INDEX.md` first, area `pylekto`), propose a plan, wait
  for approval.
- Decisions, plans, open points, working rules and history live only in the private repository
  `lektohq/lekto-knowledge`, checked out at `.idea/` (after a fresh clone:
  `git clone https://github.com/lektohq/lekto-knowledge.git .idea`). lekto has its own checkout of
  it: `git pull` before working, and commit and push every change straight to its `main`
  (`uv run tools/index.py` checks the notes and writes the index); nothing stays only local, and
  none of it goes into this repository. Notes about pylekto carry the area `pylekto` and their
  `code:` paths the prefix `pylekto/`. Docstrings point at notes as `.idea/<folder>/<name>.md`.
- If something is unclear or a decision is missing, ask before implementing. Do not deviate from
  the decisions in `.idea/decisions/` on your own.
- Small, thematically separate commits. Keep answers short and precise.
