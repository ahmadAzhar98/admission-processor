# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

Multi-tenant, AI-assisted admission-document platform for Lahore universities.
Python functions on OpenFaaS process uploaded documents (CNIC, FSc/Matric result
cards, domicile, etc.) through a pipeline: intake -> quality-check -> classify ->
extract -> validate -> cross-check -> decide -> notify.

- Each university is a **tenant**. Requirements are **configuration (data), never code**.
- Functions are **stateless**. State lives in PostgreSQL, Redis, or object storage.
- **Synthetic data only.** Never commit real CNICs, transcripts, or personal data.

## Repository layout

```
functions/<name>/     One OpenFaaS function: handler.py, requirements.txt, tests/
libs/common/          Shared code (tenant context, db, storage, logging, schemas)
tenants/              Tenant configuration files (YAML/JSON), one per tenant
synthetic/            Synthetic document generator and fixtures
infra/                Docker Compose, Helm values, k8s manifests
load-tests/           k6 / Locust scripts
docs/                 Architecture, ADRs (docs/adr/), report material
stack.yml             OpenFaaS stack definition
```

## Commands

```
make setup      # create venv, install deps, install pre-commit hooks
make lint       # ruff check + ruff format --check
make typecheck  # mypy
make test       # pytest (unit tests, no network)
make check      # lint + typecheck + test; must pass before every commit
pytest functions/extract/tests/test_handler.py::test_name   # single test
```

`make check` must exit 0 before committing. Fix failures; never bypass them.

## Git workflow (strict)

### Branching: GitHub Flow, short-lived branches

- `main` is always deployable. **Never commit or push directly to `main`.**
- Branch from an up-to-date `main`. Name: `<type>/<short-kebab-description>`,
  e.g. `feat/extract-cnic-fields`, `fix/quality-check-blur-threshold`.
- Allowed branch types match commit types: `feat fix docs refactor test chore ci perf build`.
- One branch = one logical change. Keep branches small and short-lived.
- Releases are tagged on `main` with SemVer: `v0.1.0`, `v0.2.0`, ...

### Commits: Conventional Commits 1.0.0

Format:

```
<type>(<scope>): <imperative summary, lowercase, no period, max 72 chars>

<body: explain WHY, not what. Wrap at 72 chars. Optional.>

<footer: Refs #12 / BREAKING CHANGE: ... Optional.>
```

- Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `perf`, `build`, `revert`.
- Scopes: `intake`, `quality`, `classify`, `extract`, `validate`, `crosscheck`,
  `decide`, `notify`, `tenant`, `common`, `synthetic`, `infra`, `ui`, `docs`, `deps`.
- Summary uses imperative mood: "add cnic regex validator", not "added" or "adds".
- **Atomic commits**: one logical change each, and the project builds and tests
  pass at every commit. Never mix a refactor with a feature or fix.
- Tests and the code they cover go in the same commit (or tests first).
- Stage deliberately with `git add -p`. Never `git add .` or `git add -A` blindly.
- No "WIP", "fix stuff", "update", "misc", or "final" commit messages.
- Reference issues in the footer: `Refs #12`, `Closes #12`.

### History maintenance

- Before opening a PR, clean up local history with `git rebase -i origin/main`
  (squash fixups, reword unclear messages, reorder for readability).
- Keep branches current with `git rebase origin/main`, not merge commits.
- Merge PRs with **rebase-and-merge** (linear history, atomic commits preserved).
  Use squash only if the branch history is genuinely noisy.
- Never rewrite history that has already landed on `main`.
- Use `git revert` to undo something on `main`.
- Generate `CHANGELOG.md` from commits (commitizen); do not hand-edit it.

### Pull requests

- Title follows Conventional Commits. Fill in the PR template (what, why, how
  tested, screenshots/logs if relevant).
- Keep PRs reviewable: aim for under ~400 changed lines.
- All CI checks must pass before merge.

## Code standards (Python 3.11+)

- Format and lint with **ruff**; type-check with **mypy** (strict for `libs/` and `functions/`).
- Type hints on every function signature. Prefer `pydantic` models for data crossing boundaries.
- Docstrings (Google style) on all public functions and modules, stating purpose and non-obvious behavior.
- Small, single-purpose functions. Handler files stay thin: parse input, call
  logic in a separate module, return output.
- No hard-coded university names, thresholds, or document rules. Read them from tenant config.
- Every handler requires a tenant ID and passes it through all calls, logs, and storage paths.
- Use the `logging` module with structured fields (tenant_id, document_id). **No `print`.**
- Never log CNICs, names, or full extracted fields. Mask PII in logs.
- Handle errors explicitly. No bare `except:`. Raise specific exceptions.
- Operations must be **idempotent**: reprocessing the same document must not duplicate results.
- Secrets come from environment variables or OpenFaaS secrets. Never commit them.
- Add a new dependency only with justification in the commit body; pin versions.

## Testing

- `pytest`, with tests co-located per function in `functions/<name>/tests/`.
- Unit tests must not call the network, an LLM, or a real database. Use fakes or fixtures.
- Test the tenant-config behavior: the same input under two tenants must produce
  tenant-appropriate results.
- New behavior needs a test. Bug fixes need a regression test.
- Report extraction accuracy using the synthetic dataset, never anecdotal examples.

## Documentation

- Architectural decisions go in `docs/adr/NNNN-title.md` (context, decision, consequences).
- Update `README.md` and relevant docs in the same PR as the behavior change.

## Never do (without explicit confirmation from the user)

- Push to `main`, force-push, or run `git reset --hard`, `git clean -fd`, or `git rebase` on shared branches.
- Use `--no-verify` or otherwise skip hooks and checks.
- Commit secrets, `.env` files, model weights, or real personal data.
- Edit generated files (`CHANGELOG.md`, lockfiles by hand, `build/`).
- Make unrelated "drive-by" changes. Raise them separately instead.
- Add dependencies, new top-level directories, or change `stack.yml` structure silently.

## Definition of done

A task is done when: `make check` passes, tests cover the change, docs are
updated, the working tree is clean, and commits are atomic with Conventional
Commit messages on a properly named branch. Summarize what changed and why in
two or three sentences. Do not push or open a PR unless asked.

## When unsure

Ask a short question instead of guessing, especially about tenant-config design,
privacy handling, and anything that changes git history.
