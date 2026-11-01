# Admission Processor

A multi-tenant, AI-assisted platform that checks university admission
documents. Python functions on OpenFaaS take uploaded documents through
quality checks, classification, field extraction, rule validation and
cross-document consistency checks. Then they either approve a file or send it
to a human reviewer. Each university is a tenant, and its requirements are
configuration rather than code.

> All data in this repository is synthetic. The universities ("University A",
> "University B", "University C") are fictional.

## Problem

Every admission season, universities in Lahore receive tens of thousands of
scanned or phone-photographed documents: CNICs or B-forms, Matric and FSc result
cards from different boards, domicile certificates, entry-test scorecards and
fee challans. Staff check them by hand against requirements that differ by
university and change every year. The work arrives in a burst before each
deadline, which leaves documents in queues and lets mistakes through. The rest
of the year the same staff and servers sit idle.

This project automates the routine checks, sends only uncertain cases to
people, and learns from their corrections. Serverless functions scale with the
deadline-night burst and down to zero afterwards.

## Architecture

```mermaid
flowchart LR
    U[Applicant upload] --> I[intake]
    I --> Q[quality-check]
    Q -->|re-upload needed| N[notify]
    Q --> C[classify]
    C --> E[extract]
    E --> V[validate]
    V --> X[cross-check]
    X --> D[decide]
    D -->|approved| N
    D -->|low confidence / rule failure| R[review queue]
    R -->|staff correction| F[feedback examples]
    F -.few-shot.-> E
    R --> N
```

- **OpenFaaS + NATS**: one function per step, chained by asynchronous
  invocations queued on NATS.
- **PostgreSQL + pgvector**: results, audit log, review queue, and the
  few-shot examples each tenant builds up from corrections.
- **S3-compatible object storage**: uploaded files under tenant-scoped keys.
- **PaddleOCR (Tesseract fallback)** for text, **Ollama** for local LLM and
  vision models. No document leaves the deployment.
- **Tenant configuration** in `tenants/`: required documents, fields,
  validation rules, thresholds, and English/Urdu notification templates.

Design decisions are recorded in [docs/adr/](docs/adr/).

## Repository layout

| Path | Contents |
| --- | --- |
| `functions/` | One OpenFaaS function per directory |
| `libs/common/` | Shared library: settings, tenant context, logging, storage, db, schemas |
| `tenants/` | Tenant configuration files |
| `synthetic/` | Synthetic document generator |
| `infra/` | Docker Compose, manifests, monitoring |
| `load-tests/` | k6 scripts |
| `docs/` | Architecture docs and ADRs |

## Getting started

Requires Python 3.11+ and GNU Make.

```bash
make setup    # create .venv, install dev dependencies, install git hooks
make check    # lint + typecheck + unit tests
make help     # list all targets
```

## Contributing

Work happens on short-lived branches with Conventional Commits; see
[CLAUDE.md](CLAUDE.md) for the full workflow. `make check` must pass before
every commit.

## License

[MIT](LICENSE)
