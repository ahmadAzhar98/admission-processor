# 0004. Package functions with the shared library via faas-cli copy

- Status: accepted
- Date: 2026-11-01

## Context

Every function imports `libs/common` and reads tenant configs from
`tenants/`. OpenFaaS templates build each function from its own handler
directory, so code outside that directory is not in the image by default.
The options were to publish `common` as a wheel to a package index, to keep
a custom template with the library baked in, or to use the `copy`
setting in `stack.yml` (supported by `faas-cli`).

## Decision

- Use the stock `python3-http` template so upgrades come from upstream.
- List `./libs` and `./tenants` under `configuration.copy` in `stack.yml`;
  `faas-cli build` copies them into each function's build context.
- Set `PYTHONPATH=/home/app/function/libs` and
  `AP_TENANTS_DIR=/home/app/function/tenants` in each function's environment.
- Function directories use underscores (`functions/quality_check`) so they
  import as packages in tests; deployed names use hyphens (`quality-check`).
  Handlers import their own modules relatively (`from .service import ...`),
  which works both in the template (`function` package) and in tests.
- Each function's `requirements.txt` lists the pinned runtime dependencies it
  needs, including those of `common`.

## Consequences

- No private package index or custom template to maintain.
- Every image contains the whole shared library and every tenant config;
  both are small. A tenant config change requires redeploying functions,
  which also gives an auditable rollout of requirement changes.
- Dependency pins exist in `pyproject.toml` and in each `requirements.txt`;
  they must be updated together.
