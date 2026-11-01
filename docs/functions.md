# Functions

Every function lives in `functions/<name>/` with a thin `handler.py`, its
logic in separate modules, a pinned `requirements.txt` and `tests/`.
Pipeline steps after intake receive a `PipelineEvent` JSON body from the
queue (`tenant_id`, `application_id`, `document_id`, `step`,
`correlation_id`, `payload`) and respond `200` with a short summary. Errors
use `{"error": "<code>"}` with the status from `common.errors`.

## intake (`POST /function/intake`)

Raw file body. Headers: `X-Tenant-Id`, `X-Api-Key`, `X-Application-Id`,
`Content-Type` (`image/png|jpeg|tiff`), optional `X-Document-Type`.

- `202 {"document_id", "status", "duplicate": false}` for a new document;
  `200` with `"duplicate": true` for identical bytes already received.
- `401` for bad credentials (unknown tenant and wrong key look the same),
  `400` for bad metadata, `413` above `AP_MAX_UPLOAD_BYTES`.
- Stores at `tenants/<tenant>/applications/<application>/<document>.<ext>`
  and enqueues `quality-check`.

## quality-check

- **Step mode:** measures resolution, blur (contrast-normalised Laplacian
  variance), skew (Hough line angle), brightness and contrast against the
  tenant's `quality` thresholds. Passing documents go to `classify`;
  failing ones become `reupload_required` and trigger a `notify` event that
  lists every failed check.
- **Precheck mode:** an `image/*` POST with `X-Tenant-Id`/`X-Api-Key`
  returns the report synchronously with `reupload_required`, so a portal can
  reject a blurry photo before upload.

## classify

OCR runs once (PaddleOCR, Tesseract fallback; `AP_OCR_ENGINE`) and its output
is stored for extraction. Keyword and page-shape cues from `keywords.yaml`
give a type and confidence. Below the tenant's
`classification_min_confidence` the LLM is asked. Types the tenant does not
accept go to `decide` for review; others go to `extract` with flags for low
confidence or a mismatch with the declared type.

## extract

Reads the tenant's fields for the document type. The caption reader matches
each field's printed labels (English/Urdu) in the OCR lines. If a required
field is missing or any field is below the auto-approve confidence, the LLM
extracts with a JSON schema generated from the field specs, plus the most
similar tenant few-shot examples. The two readings are merged into
per-field confidences. Missing required fields are recorded as null with
confidence 0.

## validate

Evaluates the tenant's typed rules (`min_percentage`, `range`,
`allowed_values`, `age`, `date_window`) and field checks (required, pattern).
Outcome messages state scores and percentages, never personal values.

## cross-check

Runs when every document of the application has settled. Compares the
configured fields across documents: fuzzy token-sort similarity for names,
exact match for identifiers. A B-form stands in for a CNIC.

## decide

Applies the policy in `functions/decide/policy.py`: incomplete (missing or
re-upload documents), rejected (reject rule on a confident reading, or a
reviewer rejection), needs review (anything uncertain), or approved. It opens
review items for the documents involved, updates statuses, audits the
decision and triggers `notify`.

## notify

Renders the tenant's English or Urdu template for the event in its default
language and delivers it once per subject and event. `log` writes to the
function log; other media (`email`, `sms`) are posted to the tenant portal's
`/api/notifications` webhook, because the platform stores no contact details.

## review-api (FastAPI, `dockerfile` template)

Staff credential headers on every route (`X-Tenant-Id`, staff `X-Api-Key`).

| Route | Purpose |
| --- | --- |
| `GET /reviews` | Open items, oldest first |
| `GET /reviews/{document_id}` | Fields, rule outcomes, decision |
| `GET /documents/{document_id}/image` | The uploaded image |
| `GET /documents/{document_id}/audit` | Audit trail |
| `POST /reviews/{document_id}/resolve` | `{outcome, reviewer, corrections}` |

Resolution stores corrections as human-sourced fields, finalises the
document, and publishes `feedback` (when corrected) and `decide`.

## review-ui (Streamlit)

Queue, image beside editable fields, rule outcomes, approve/reject. It sends
only the fields the reviewer changed. It calls the API through the gateway
(`AP_REVIEW_API_URL`).

## feedback

Stores a corrected document's OCR text and verified fields as a tenant
few-shot example, embedded with Ollama (`AP_EMBEDDING_MODEL`).

## onboarding (`POST /function/onboarding`)

Platform admin only (`X-Admin-Key`). Body: `tenant_id`, `display_name`,
`admission_cycle`, `checklist`, `samples[]` (text or base64 image). Returns
the drafted config with `valid` and any schema `errors`, and stores it at
`tenants/<tenant>/onboarding/draft.json`. Drafts are always
`pending_approval`; see [tenant-configuration.md](tenant-configuration.md).
