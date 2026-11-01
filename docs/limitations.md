# Limitations and future work

## Known limitations

- **Accuracy has only been measured on synthetic documents**, rendered by
  the same project whose code reads them. Real scans have stamps,
  handwriting, watermarks, folds and board layouts the generator does not
  imitate. Treat the figures in [evaluation.md](evaluation.md) as a
  regression baseline, not a forecast.
- **Urdu OCR was not measured.** Only Tesseract's English model was
  available; Urdu-captioned documents scored 0% with it. PaddleOCR and
  Tesseract `urd` are integrated but unmeasured.
- **LLM paths are unmeasured.** Classification fallback, LLM extraction,
  learning from corrections and onboarding drafting are unit-tested with a
  scripted fake, never against a real Ollama model.
- **No load test has been run.** Scaling behaviour, cold-start latency and
  cost are to be measured on a real OpenFaaS deployment.
- **Scale-to-zero needs OpenFaaS Pro or KEDA**; CE ignores those labels.
- **The quality check is heuristic.** It flags many phone photos as skewed
  or blurry (precision 0.54 against the generator's labels), and its
  thresholds are calibrated to synthetic images.
- **No retention purge job.** `retention_days` is configured but not
  enforced.
- **Staff authentication is a shared key per tenant.** Reviewer identity in
  the audit log is self-reported; production needs single sign-on.
- **Only images are accepted** (PNG, JPEG, TIFF). Multi-page PDFs must be
  split and rasterised before upload.
- **Rules are a closed set** of five types. Requirements such as weighted
  merit formulas or quota allocation are out of scope.
- **The end-to-end flow has not run on OpenFaaS itself**; it runs in-process
  with the real step code. The faasd and k3s steps are documented, not
  verified.

## Future work

1. Measure PaddleOCR and Tesseract `urd` on the synthetic set, then on a
   small consented sample of real documents with ground truth.
2. Run the LLM-assisted and before/after-corrections evaluations with a
   local 7B model, and compare a few models for accuracy and latency.
3. Deploy on k3s with OpenFaaS and KEDA, run the deadline-night k6 profile,
   and complete the cost comparison.
4. Calibrate quality thresholds against OCR success instead of generator
   labels, and add document-boundary detection for phone photos.
5. Add a retention job and a subject-access export by application ID.
6. Replace shared staff keys with OIDC single sign-on and per-reviewer audit.
7. Accept PDFs (split and rasterise in intake).
8. Add merit-score computation as a separate, tenant-configured step.
