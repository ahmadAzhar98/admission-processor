# 0006. Make every pipeline step idempotent

- Status: accepted
- Date: 2026-11-01

## Context

OpenFaaS asynchronous invocations are queued on NATS and delivered at least
once: a timeout, a crashed replica or a retry can run the same event twice.
Portals also retry uploads. Reprocessing must never duplicate documents,
results, review items, examples or applicant messages (CLAUDE.md).

## Decision

Each kind of effect has one idempotency mechanism:

| Effect | Mechanism |
| --- | --- |
| Upload | Document ID = hash(application ID, file SHA-256); `UNIQUE (tenant, application, sha256)` |
| Step result | Upsert on `(tenant_id, document_id, step)` |
| Status change | Set to a target state; the audit log records each actual change |
| Review item | Upsert on `(tenant_id, document_id)`, merging reasons |
| Few-shot example | Upsert on `(tenant_id, document_type, source_document_id)` |
| Notification | Claim row on `(tenant_id, subject_id, event)` before sending; release on failure |
| Application steps | Cross-check and decide run only when every document has settled; reruns overwrite |

Events carry no timestamps in their idempotency key
(`tenant:document:step`), so a redelivered event maps to the same work.

## Consequences

- Retries are always safe, so the queue's retry policy can be generous.
- Re-running a step (for example after fixing a tenant rule) is a supported
  operation, not an incident.
- Notifications are at-most-once per subject and event, except for a crash
  between delivery and the claim being kept, which could resend once. A
  duplicate message was judged better than a lost one.
- The audit log is append-only and may record the same transition twice if
  a step is replayed; it is a history, not a state.
