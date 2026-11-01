# synthetic

Seeded generator for synthetic admission documents and their ground-truth
labels. Every name, number and document is fictional; never add real
personal data here.

```bash
make synthetic                       # 20 applications per tenant, seed 42
make synthetic SEED=7 APPLICATIONS=100
python -m synthetic.generate --tenant uni-b --applications 5 --out /tmp/ds
```

Output (git-ignored) in `synthetic/output/`:

```
manifest.jsonl                         one GroundTruth JSON per line
<tenant>/<application>/<document>.png  rendered, degraded image
<tenant>/<application>/<document>.json label for that image
```

## What is generated

- **Applicants**: random given/family-name combinations, CNIC-format numbers
  (gender check digit), Punjab and a few non-Punjab districts.
- **Documents**: CNIC, B-form, Matric and FSc result cards (table, card and
  certificate layouts, several boards), domicile, entry-test scorecards (out
  of 100 or 400), and fee challans. Captions are English, Urdu or mixed.
- **Per tenant**: each application has the documents the tenant's config
  requires, with a B-form standing in for the CNIC in about 10% of cases.
- **Planted inconsistencies**: about 10% of applications have a misspelt name
  on one document, labelled in `injected_mismatch`.
- **Degradation** profiles: clean (30%), mild skew/noise/JPEG/contrast (45%),
  phone photo with perspective and shadow (15%), and severe blur (10%).
  `expected_reupload` marks images the quality check should reject.

## Reproducibility

Each application uses an RNG seeded by `(seed, tenant, index)`, and each
image its own RNG, so labels are identical across runs and machines. Pixels
also depend on the fonts found on the host (see `fonts.py`); set
`AP_SYNTHETIC_FONT` and `AP_SYNTHETIC_URDU_FONT` to pin them.
