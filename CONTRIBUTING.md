# Contributing

Thank you for helping. This project processes personal documents, so two
rules come before everything else:

- **Use synthetic data only.** Never commit, attach or paste real CNICs,
  transcripts or any personal data, including in issues, logs and test
  fixtures. Generate documents with `make synthetic`.
- **Requirements are configuration.** University-specific documents, fields,
  rules and thresholds belong in `tenants/*.yaml`, never in code.

## Setup

```bash
make setup     # .venv, dev dependencies, pre-commit and commit-msg hooks
make check     # ruff, mypy (strict), pytest; must pass before every commit
make up && make migrate && make test-integration   # optional, needs Docker
```

## Branches

GitHub Flow with short-lived branches cut from an up-to-date `main`:

```
<type>/<short-kebab-description>    e.g. feat/extract-cnic-fields, fix/quality-check-blur-threshold
```

Types: `feat fix docs refactor test chore ci perf build`. One branch holds
one logical change. Never commit directly to `main`.

## Commits

[Conventional Commits 1.0.0](https://www.conventionalcommits.org/), enforced
by the commit-msg hook (commitizen):

```
<type>(<scope>): <imperative summary, lowercase, no period, ≤ 72 chars>

<body: why, wrapped at 72>

<footer: Refs #12 / BREAKING CHANGE: ...>
```

- Scopes: `intake quality classify extract validate crosscheck decide notify
  tenant common synthetic infra ui docs deps`.
- **Atomic commits:** one logical change each, and `make check` passes at
  every commit. Do not mix a refactor with a feature or fix. Tests go in the
  same commit as the code they cover, or just before it.
- Stage deliberately (`git add -p` or explicit paths), never `git add .`.
- No "WIP", "fix stuff", "update" or "final" messages. Fix mistakes on an
  unmerged branch with `git commit --fixup <sha>` and
  `git rebase -i --autosquash origin/main`.
- A new dependency needs a justification in the commit body and an exact pin
  in `pyproject.toml` and the relevant `functions/*/requirements.txt`.
- Never use `--no-verify`.

## Pull requests

- Rebase on `origin/main` (no merge commits) and tidy history first.
- Title in Conventional Commit form, and fill in the template: what, why,
  how tested.
- Aim for fewer than about 400 changed lines; CI must be green.
- Merged with **rebase-and-merge**, which keeps history linear and commits
  atomic. Never rewrite history on `main`; use `git revert`.

## Code standards

Python 3.11+, ruff and strict mypy, type hints everywhere, Google-style
docstrings on public functions. Handlers stay thin (parse, call the
service, respond). Pass the tenant ID through every call. Log with
`logging`, never `print`, and never log personal values. Raise the specific
errors from `common.errors`. Every step must be idempotent (ADR 0006).

## Tests

- Unit tests live in `functions/<name>/tests/` and `libs/common/tests/`, and
  must not touch the network, a database or an LLM; use the in-memory
  runtime and fakes.
- Tenant behaviour needs a test showing two tenants judging the same input
  differently.
- Bug fixes need a regression test. Report accuracy with the evaluation
  scripts on the synthetic dataset, never with anecdotes.

## Decisions and docs

Record architectural decisions in `docs/adr/NNNN-title.md`. Update the
README and the relevant docs in the same pull request as the behaviour
change.

## Releases

Releases are tagged on `main` with SemVer by `cz bump` on a
`chore/release-vX.Y.Z` branch. Commitizen generates `CHANGELOG.md`; never
edit it by hand.
