# 0002. Serverless, multi-tenant pipeline architecture

- Status: accepted
- Date: 2026-11-01

## Context

Lahore universities receive admission documents (CNIC/B-form, Matric and FSc
result cards, domicile, entry-test scorecards, fee challans) in bursts around
deadlines and are nearly idle the rest of the year. Each university has its own
required documents, fields and rules, and these change every admission cycle.
We want one platform that serves many universities without forking code, runs
on open-source software, and costs little when idle.

## Decision

1. **One function per pipeline step on OpenFaaS.** The steps are intake,
   quality-check, classify, extract, validate, cross-check, decide and notify,
   plus review and onboarding support functions. Each step scales
   independently; scale-to-zero keeps idle cost near zero.
2. **Asynchronous chaining through NATS.** A step hands work to the next one
   with an OpenFaaS asynchronous invocation (`/async-function/<name>`), which
   the gateway queues on NATS. Steps never call each other synchronously, so a
   burst is absorbed by the queue rather than by timeouts.
3. **Stateless functions.** Documents live in S3-compatible object storage;
   results, audit log, review queue and few-shot examples live in PostgreSQL
   (with pgvector); short-lived locks and caches live in Redis. A function can
   be killed at any moment without losing state.
4. **A tenant is a university; requirements are data.** Every request carries a
   tenant ID that flows through every call, log line and storage path.
   Required documents, fields, validation rules, thresholds and notification
   templates come from a validated tenant configuration file, never from code.
5. **Shared infrastructure, tenant-scoped data.** All tenants share the
   database and bucket. Isolation is enforced by a `tenant_id` column on every
   table and a `tenants/<tenant_id>/` prefix on every object key, applied in
   the shared library so individual functions cannot forget it.
6. **Idempotent steps.** Each step's output is keyed by
   `(tenant_id, document_id, step)`; reprocessing overwrites rather than
   duplicates, so queue redelivery is safe.
7. **Human in the loop.** Low-confidence or rule-failing results go to a review
   queue. Staff corrections are stored as tenant-specific few-shot examples
   that later extractions retrieve.

## Consequences

- Adding a university means writing a config file, not deploying code.
- Cold starts add latency to the first request after idle; this is acceptable
  for document processing and is measured rather than assumed.
- Shared-database tenancy is cheap and simple, but every query must filter by
  tenant. The shared library and tests are the guardrail; per-tenant databases
  remain an option for a tenant that demands physical isolation.
- Async chaining makes end-to-end tracing harder, so every event carries the
  tenant ID, document ID and a correlation ID, and every state change is
  written to an audit log.
