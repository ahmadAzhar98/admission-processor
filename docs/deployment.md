# Deployment guide

Three ways to run the platform, from cheapest to most realistic. Commands
and manifests are in [infra/README.md](../infra/README.md). This page
explains the choices.

| Mode | Use for | Exercised in this repository |
| --- | --- | --- |
| In-process (`functions/local_runner.py`) | Tests, evaluation, debugging a tenant config | Yes (end-to-end test, evaluation) |
| Compose services + functions on the host | Developing against real PostgreSQL/S3 | Yes (integration tests) |
| faasd on one VM | A pilot with one university | No (documented only) |
| k3s + OpenFaaS | Several universities, deadline-night scaling | No (manifests validated only) |

## Prerequisites

- PostgreSQL 16 with pgvector ≥ 0.8; run `make migrate` before deploying.
- S3-compatible storage (SeaweedFS in the manifests; MinIO or a cloud bucket
  also work) and a bucket named by `AP_S3_BUCKET`.
- Ollama with an instruct model (`AP_LLM_MODEL`, default
  `qwen2.5:7b-instruct`) and an embedding model with 768 dimensions
  (`AP_EMBEDDING_MODEL`, default `nomic-embed-text`). A different embedding
  size needs a migration of `tenant_examples.embedding`.
- OpenFaaS with the NATS JetStream queue worker for asynchronous calls.

## Configuration

Functions read `AP_*` environment variables (see `.env.example` and
`common/settings.py`). Secrets come from OpenFaaS secret files with
hyphenated names (`database-url`, `s3-access-key`, `s3-secret-key`,
`<tenant>-api-key`, `<tenant>-staff-key`, `platform-admin-key`). The key
secrets hold SHA-256 hashes, never the keys themselves.

## Building and deploying functions

Each release publishes ready-built images to GitHub Container Registry
(`ghcr.io/<owner>/admission-<function>:<version>`). To deploy a release
without building, point `faas-cli` at them:

```bash
REGISTRY=ghcr.io/<owner> TAG=1.1.0 faas-cli deploy -f stack.yml
```

Images are private by default for private repositories; give the cluster a
pull secret, or make the packages public.

To build from source instead:

`faas-cli up -f stack.yml` builds every function with the shared library and
tenant configs copied in (ADR 0004), pushes the images to `$REGISTRY`, and
deploys them. Classify, extract and onboarding images install Tesseract with
Urdu data and carry PaddleOCR, so they are large (several GB with
PaddlePaddle). Build them on a machine with enough disk, and expect slow
first starts while models load.

## Sizing notes for a pilot

- **Ollama** dominates: a 7B model wants a GPU, or 8+ CPU cores and 16 GB
  memory at several seconds per call. The pipeline calls it only for
  uncertain classifications and incomplete extractions.
- **classify** is the heaviest function (OCR). Cap its replicas (`scale.max`)
  to what the nodes can hold; the queue absorbs bursts.
- **intake** stays at one warm replica so uploads never wait for a cold
  start.

## Scaling behaviour

The labels in `stack.yml` express the intended policy: scale-to-zero for the
queue-driven steps and bounded maxima. OpenFaaS CE does not act on
scale-to-zero labels; that needs OpenFaaS Pro, or KEDA scaling on the
JetStream consumer lag. See [evaluation/cost-methodology.md](evaluation/cost-methodology.md)
for how to measure whether it pays off.

## Upgrades and tenant changes

- Tenant config changes ship as a pull request and a redeploy, so every
  requirement change is reviewed and versioned.
- Schema changes are new numbered migrations. Never edit an applied one.
- Steps are idempotent (ADR 0006), so redeploying in the middle of a cycle
  and replaying failed events are safe.

## Observability

Prometheus scrapes the gateway and the NATS exporter
(`infra/monitoring/prometheus.yml`). Grafana's "Admission pipeline"
dashboard shows invocations, replicas, latency, queue depth and errors.
Alerts fire on queue backlog, error rate and intake latency. Logs are JSON
with tenant, document and correlation IDs. Ship them to Loki or similar to
follow one document across functions.
