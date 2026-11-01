# tenants

One configuration file per tenant (university), named `<tenant_id>.yaml`.
Required documents, fields, validation rules, thresholds and notification
templates live here as data; pipeline code never hard-codes them. All
tenants are fictional.

| Tenant | Profile | Notable requirements |
| --- | --- | --- |
| `uni-a` | Selective private | Own admission test, 70% minimums (reject), 0.95 auto-approve |
| `uni-b` | Public, merit-based | Punjab domicile, recognised board, 33% entry test, Urdu SMS |
| `uni-c` | High-volume private | No test or domicile, 45% minimums (review), 0.85 auto-approve |

## File structure

| Key | Purpose |
| --- | --- |
| `tenant_id` | Slug; must equal the file name |
| `status` | `active`, or `pending_approval` for drafts (ignored by the pipeline) |
| `auth.api_key_secret` | OpenFaaS secret holding the SHA-256 of the tenant's API key |
| `documents[]` | Accepted document types, `alternatives`, and `fields` to extract |
| `rules[]` | Typed rules: `min_percentage`, `range`, `allowed_values`, `age`, `date_window` |
| `cross_checks[]` | Fields that must agree across documents (`exact` or `fuzzy`) |
| `quality` | Image limits below which a re-upload is requested |
| `decision` | Classification fallback, auto-approve confidence, few-shot count |
| `notifications` | Language, channel, and an English + Urdu template per event |
| `retention_days` | How long documents and results are kept |

Every rule `severity` is `review` (send to staff) or `reject`. Templates may
only use `{university}`, `{application_id}`, `{document_type}`, `{reasons}`
and `{portal_url}`, so notifications can never contain personal data.

Validate a file by running the test suite (`make test`); every file in this
directory is loaded and cross-checked by `test_shipped_tenants.py`.
