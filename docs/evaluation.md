# Evaluation

All figures come from the synthetic dataset. Nothing here describes real
applicants. Each table names the command that produced it. Anything that
could not be run in the development environment is marked **to be
measured**, with the command that will produce it.

## Environment and dataset

| Item | Value |
| --- | --- |
| Machine | Apple Silicon (arm64), macOS 13.3.1, Python 3.11.9 |
| OCR available | Tesseract 5.5.0 with the **English model only** (`eng`) |
| Not available | PaddleOCR, Tesseract Urdu model (`urd`), Ollama, OpenFaaS, k6 |
| Dataset | `make synthetic SEED=42 APPLICATIONS=10` → 150 documents, 30 applications, 3 tenants |
| Mix | 62 English, 54 Urdu, 34 mixed-caption documents; 40 clean, 66 mild, 24 phone-photo, 20 severe |

The evaluation scores extraction with each document's true type, so
extraction errors are not confounded with classification errors. Fields
count as correct when they match exactly after case and whitespace
normalisation.

## 1. Pipeline logic on ground-truth text

`python -m synthetic.evaluation.accuracy --ocr ground-truth`

OCR is replaced by the exact printed text, which isolates classification,
caption extraction and normalisation from OCR errors.

| Measure | Result |
| --- | --- |
| Classification accuracy | 150 / 150 (100%) |
| Field accuracy, all tenants and document types | 800 / 800 (100%) |

Every tenant/document-type cell is 100%. This shows the logic is consistent
with the generator. It says nothing about real-world accuracy, since the
same code base produced both.

## 2. With Tesseract OCR (English model)

`python -m synthetic.evaluation.accuracy --ocr tesseract [--language ..] [--profile ..]`

| Subset | Documents | Classification | Field accuracy |
| --- | --- | --- | --- |
| English captions, clean scans | 19 | 100% | 96.8% |
| English captions, all profiles | 62 | 90.3% | 78.8% |
| Urdu captions, all profiles | 54 | 55.6% | 0.0% |
| All documents | 150 | 76.7% | 40.1% |

Mean Tesseract time was 0.62 s per page on this machine.

Field accuracy by tenant and document type, all documents:

| Tenant | CNIC | B-form | Matric | FSc | Domicile | Entry test | Fee challan |
| --- | --- | --- | --- | --- | --- | --- | --- |
| uni-a | 34% | 25% | 54% | 46% | — | 53% | 37% |
| uni-b | 40% | — | 40% | 17% | 38% | 18% | 30% |
| uni-c | 25% | 58% | 56% | 39% | — | — | 67% |

**Reading the results.**

- *Urdu captions:* the 0% on Urdu-captioned documents is expected. The
  English model cannot read the captions, so no field can be anchored.
  Installing `tesseract-ocr-urd` (as the function images do) or using
  PaddleOCR's Urdu model is required. The Urdu figures are **to be
  measured**.
- *Same-row values:* the first Tesseract run scored 17% overall. Error
  analysis showed that OCR returns a caption and its value as separate lines
  on the same row in card and table layouts. The caption reader was fixed to
  pair them (commit `fix(extract): read values printed beside captions on the
  same row`), which raised overall accuracy to 40.1% and clean-English
  accuracy to 96.8%.
- *Degradation:* on English documents, accuracy falls from 96.8% (clean) to
  78.8% across all profiles. Severe blur in particular should be caught by
  the quality check before extraction.
- *LLM fallback:* these runs used no LLM. Missing fields would normally be
  sent to it, which is **to be measured**.

## 3. Quality check

Same runs. The quality check's re-upload decision is compared with the
generator's `expected_reupload` label, which is itself a heuristic (blur
radius ≥ 2.5, |skew| ≥ 7°, contrast factor ≤ 0.35 or noise σ ≥ 25).

| | Expected re-upload | Expected OK |
| --- | --- | --- |
| **Re-upload requested** | 21 | 18 |
| **Accepted** | 7 | 104 |

Precision 0.54, recall 0.75, with the tenants' own thresholds. Of the 18
false positives, 10 are phone photos, 6 mildly degraded and 2 "severe"
images below the label's cut-offs. The checks that fired were skew (8), blur
(7), brightness (3) and contrast (1). The perspective warp of a phone photo
reads as skew, and its softening lowers the blur score. Whether those images are readable enough for OCR is not captured by
the heuristic label. Calibrating thresholds against OCR success rather than
the generator's label is future work.

## 4. OCR engine comparison

`python -m synthetic.evaluation.ocr_compare --engine tesseract --engine paddle`

Character and word error rates against the printed text, whitespace
collapsed:

| Engine | Subset | Documents | CER | WER | s/page |
| --- | --- | --- | --- | --- | --- |
| Tesseract (eng) | all | 150 | 0.30 | 0.39 | 0.68 |
| Tesseract (eng) | English captions | 62 | 0.15 | 0.22 | 0.86 |
| Tesseract (eng) | Urdu captions | 54 | 0.48 | 0.59 | 0.45 |
| Tesseract (eng) | clean | 40 | 0.16 | 0.25 | 0.44 |
| Tesseract (eng) | phone photo | 24 | 0.27 | 0.39 | 0.54 |
| Tesseract (eng) | severe | 20 | 0.75 | 0.79 | 1.36 |
| PaddleOCR | all subsets | — | **to be measured** | | |

The CER on clean English pages (0.16) is higher than the field accuracy
suggests. Engines order table cells differently from the printed caption
order, so reading order inflates CER even when every value is read correctly.

## 5. Before and after staff corrections

`python -m synthetic.evaluation.accuracy --ocr paddle --llm ollama --corrections 0.5`

**To be measured.** This needs Ollama. Half of the applications provide
corrections (stored as tenant few-shot examples) and the other half are
scored before and after. Without an LLM, examples cannot influence
extraction, and the script reports no "after" figure rather than a
misleading one.

## 6. End-to-end behaviour

`make test`, which includes `functions/tests/test_end_to_end.py`.

Nine rendered applications across the three tenants run through every step,
with OCR replaced by ground-truth text. The test checks, and currently
passes, that:

- every application reaches an outcome or waits for a re-upload;
- every document is classified as labelled;
- no application with a planted name mismatch is auto-approved;
- re-uploading every file or replaying every decision event changes no
  stored result, opens no extra review items and sends no extra messages.

The PostgreSQL, pgvector and S3 code paths pass `make test-integration`
against the compose stack (PostgreSQL 16 with pgvector 0.8.0, SeaweedFS 3.80).

## 7. Load, latency and cost

| Measurement | Script | Status |
| --- | --- | --- |
| Deadline-night burst (2 → 80 uploads/s) | `load-tests/deadline_night.js` | **to be measured** |
| Cold versus warm latency | `load-tests/cold_warm.py` | **to be measured** |
| Serverless versus always-on cost | [cost-methodology.md](evaluation/cost-methodology.md) | **to be measured** |

These need a deployed OpenFaaS gateway with autoscaling, which was not
available. The scripts and the method are ready, and
[load-tests/README.md](../load-tests/README.md) explains how to run them.
