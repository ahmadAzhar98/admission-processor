# Security and privacy notes

Admission documents carry national identity numbers, names, dates of birth,
family details and academic records. This page describes how the platform
handles them and what an operator must still do. It is **not** a statement
of compliance with any law or regulation (for example Pakistan's data
protection rules or a university's own policies). Each university must
assess that with its own legal advisers before processing real data.

## Data the platform holds

| Data | Where | Purpose |
| --- | --- | --- |
| Uploaded images | Object storage, `tenants/<id>/applications/...` | Evidence for review and audit |
| OCR text, extracted fields, rule outcomes | PostgreSQL `step_results` | Decisions and review |
| Review items and corrections | PostgreSQL `review_items` | Human review |
| Few-shot examples (OCR text + verified fields) | PostgreSQL `tenant_examples` | Improving extraction |
| Audit log | PostgreSQL `audit_log` | Who changed what, when |

The platform does **not** store applicants' phone numbers or e-mail
addresses. Notifications are addressed by application ID and delivered by
the university's portal.

## Controls in place

- **Tenant isolation.** The tenant comes from the caller's credential, not
  from request fields. Object keys are prefixed per tenant and checked on
  read. Every SQL statement must filter on the tenant ID or it is refused.
  Few-shot examples never cross tenants.
- **Separate credentials.** Portal upload keys, staff review keys and the
  platform admin key are different secrets. Only SHA-256 hashes are stored,
  as OpenFaaS secrets, never in the repository or tenant files. Unknown
  tenants and wrong keys produce the same 401.
- **No hosted AI services.** OCR and LLM calls run inside the deployment
  (PaddleOCR/Tesseract, Ollama), so document content is never sent to a
  third-party API.
- **Log masking.** Logs are structured JSON. CNIC/B-form numbers, phone
  numbers and e-mails are masked wherever they appear, and values under
  sensitive keys (names, dates of birth, roll numbers) are masked
  regardless of content. Error messages and rule outcomes name fields and
  scores, never values.
- **PII-free notifications.** Templates may only use the university name,
  application ID, document type, reasons and portal URL.
- **Audit trail.** Every status change, decision, review resolution,
  notification and stored example is written to an append-only audit log.
- **Least privilege for secrets.** Only intake and the quality precheck
  mount tenant upload-key secrets, only the review API mounts staff keys,
  and only onboarding mounts the admin key.
- **Synthetic development data.** The repository and tests use generated
  documents only. Committing real documents is prohibited by CLAUDE.md, and
  the pre-commit hooks check for private keys and large files.

## Operator responsibilities (not provided by the code)

- **Consent and notice.** The university must tell applicants how their
  documents are processed, including automated checks and human review,
  and obtain any consent its policies require. The portal is the place to
  do this.
- **Retention and deletion.** Each tenant config has a `retention_days`
  value, but **no automatic purge job is implemented**. Operators must
  schedule deletion of objects, results, review items and examples older
  than the period, and decide how long the audit log is kept.
- **Encryption.** Enable encryption at rest for the database and object
  storage volumes, and TLS on the gateway and between services. The compose
  stack uses plain HTTP and development passwords and must never hold real
  data.
- **Access to the review UI.** Put the review API and UI behind the
  university's single sign-on or VPN. The staff key is a shared secret, not
  per-person authentication; reviewer IDs in the audit log are self-reported.
- **Backups** of PostgreSQL and object storage, protected like the primary
  data.
- **Applicant rights.** Handle requests to access, correct or delete data
  by locating records by application ID across the stores listed above.

## Automated decisions

The system auto-approves only when every document is read confidently, all
rules and cross-checks pass, and the tenant's threshold is met. It rejects
only when a reject-severity rule fails on a confidently read value. Every
other case goes to a person. Universities should still let applicants
contest any automated outcome, and periodically audit a sample of
auto-approved and auto-rejected files.

## Reporting a vulnerability

Do not open a public issue. Contact the maintainers privately with steps to
reproduce, and never include real personal data in a report.
