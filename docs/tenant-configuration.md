# Tenant configuration guide

A tenant is one university. Everything that makes its admission process
different lives in `tenants/<tenant_id>.yaml`: which documents are required,
which fields to read, the rules, thresholds and messages. Changing
requirements means editing this file and redeploying, never editing code.
The schema is `common.tenant_config.models.TenantConfig`.

## Minimal example

```yaml
tenant_id: uni-x                 # slug; must equal the file name
display_name: University X
admission_cycle: "2027"
auth:
  api_key_secret: uni-x-api-key           # OpenFaaS secret: sha256 of the portal key
  staff_api_key_secret: uni-x-staff-key   # OpenFaaS secret: sha256 of the staff key

documents:
  - type: cnic
    alternatives: [b_form]       # a B-form is accepted instead (needs its own entry)
    fields:
      - {name: cnic_number, pattern: '^\d{5}-\d{7}-\d$', pii: true, labels: [Identity Number, شناختی نمبر]}
      - {name: full_name, pii: true, labels: [Name, نام]}
      - {name: date_of_birth, type: date, pii: true, labels: [Date of Birth, تاریخ پیدائش]}
  - type: b_form
    required: false
    fields:
      - {name: full_name, pii: true, labels: [Name, نام]}
  - type: fsc_result
    fields:
      - {name: full_name, pii: true, labels: [Name, نام]}
      - {name: obtained_marks, type: integer, labels: [Marks Obtained, حاصل کردہ نمبر]}
      - {name: total_marks, type: integer, labels: [Total Marks, کل نمبر]}

rules:
  - id: fsc-min-60
    description: FSc marks at least 60%
    document: fsc_result
    type: min_percentage
    obtained_field: obtained_marks
    total_field: total_marks
    min_percent: 60
    severity: reject

cross_checks:
  - {field: full_name, documents: [cnic, fsc_result], method: fuzzy, min_similarity: 0.88}

notifications:
  default_language: en           # en | ur
  channel: log                   # log, or a medium the portal delivers (email, sms)
  portal_url: https://admissions.university-x.example
  templates:                     # every event needs en and ur
    received: {en: "...", ur: "..."}
    reupload_required: {en: "...", ur: "..."}
    needs_review: {en: "...", ur: "..."}
    approved: {en: "...", ur: "..."}
    rejected: {en: "...", ur: "..."}
```

## Documents and fields

- `type` is one of `cnic`, `b_form`, `matric_result`, `fsc_result`,
  `domicile`, `entry_test` or `fee_challan`.
- `fields[].type` is `string` (default), `integer`, `number` or `date`.
  Dates are stored as ISO `YYYY-MM-DD` whatever their printed format.
- `labels` must list **every caption printed** next to the value, in English
  and Urdu. The caption reader finds fields by these labels, and the LLM
  prompt uses them as hints. A missing caption is the most common cause of a
  field not being found.
- `pattern` is a regular expression the normalised value must match. A
  mismatch lowers confidence and adds a `pattern:<field>` review reason.
- `pii: true` marks values that are masked in logs. Mark names, identity
  numbers, dates of birth and roll numbers.

## Rules

| `type` | Parameters | Example use |
| --- | --- | --- |
| `min_percentage` | `obtained_field`, `total_field`, `min_percent` | FSc ≥ 60% |
| `range` | `field`, `min` and/or `max` | entry test ≥ 132 / 400, session ≥ 2024 |
| `allowed_values` | `field`, `values`, `case_sensitive` | Punjab domicile districts, recognised boards |
| `age` | `field`, `reference_date`, `min_years` / `max_years` | at most 24 on 1 September |
| `date_window` | `field`, `not_before` / `not_after` | fee paid during the admission window |

`severity: reject` rejects the application only when the value was read
confidently; otherwise it goes to review. `severity: review` (the default)
always goes to review. A rule declared for a document also applies to its
alternatives when they carry the field.

## Thresholds

| Key | Meaning | Default |
| --- | --- | --- |
| `quality.min_width` / `min_height` | Minimum pixels | 800 / 600 |
| `quality.min_blur_score` | Contrast-normalised sharpness | 60 |
| `quality.max_skew_degrees` | Maximum rotation | 5 |
| `quality.min_contrast` | 1st–99th percentile spread | 40 |
| `decision.classification_min_confidence` | Below this, ask the LLM | 0.7 |
| `decision.auto_approve_min_confidence` | Weakest field needed to auto-approve | 0.9 |
| `decision.few_shot_examples` | Past corrections shown to the LLM | 3 |
| `retention_days` | Intended retention period (see security notes) | 365 |

A stricter tenant (higher auto-approve, lower skew) sends more documents to
review. A more lenient one automates more. The three shipped tenants show
the range.

## Validating a change

```bash
make test   # loads every file in tenants/ and checks all cross-references
```

Loading fails with a single message listing every problem, for example
`rules.0: rule fsc-min-60: field marks not declared for fsc_result`.

## Onboarding a new university

1. A platform administrator calls the `onboarding` function with the
   university's plain-language checklist and a few sample documents
   ([functions.md](functions.md#onboarding-post-functiononboarding)).
2. The function returns a draft with `status: pending_approval` and any
   schema errors, and stores it at `tenants/<id>/onboarding/draft.json`.
3. An administrator reviews the draft with the university, fixes any errors,
   converts it to `tenants/<id>.yaml`, and sets `status: active` only after
   both sides agree. Drafts never process documents: the pipeline refuses
   pending configs.
4. Create the tenant's `<id>-api-key` and `<id>-staff-key` secrets, run
   `make test`, open a pull request, and redeploy.

Requirement changes in the middle of a cycle follow the same pull-request
route, which leaves an auditable history of what was required and when.
