## v0.3.0 (2026-11-01)

### Features

- **synthetic**: add seeded dataset generator cli
- **synthetic**: add ground-truth label schema and manifest
- **synthetic**: add phone-photo look and degradation profiles
- **synthetic**: add skew, blur, noise, contrast and jpeg augmentations
- **synthetic**: render documents in card, table and certificate layouts
- **synthetic**: add system font discovery for latin and urdu text
- **synthetic**: add entry test scorecards and fee challans
- **synthetic**: add matric and fsc result cards in board layouts
- **synthetic**: add identity and domicile document content
- **synthetic**: add fictional applicant generator

### Bug Fixes

- **synthetic**: keep fsc sessions within the admission cycle

### Documentation

- **synthetic**: document the generator and add a make target

## v0.2.0 (2026-11-01)

### Features

- **tenant**: add university c high-volume private config
- **tenant**: add university b public merit-based config
- **tenant**: add university a selective private config
- **tenant**: add config file loader and tenant registry
- **tenant**: add root tenant config with cross-reference checks
- **tenant**: add english and urdu notification templates
- **tenant**: add declarative validation rule models
- **tenant**: add field and document requirement specs
- **common**: add postgres repositories
- **common**: add repository interfaces with in-memory versions
- **common**: add sql migration runner
- **common**: add tenant-guarded database access
- **common**: add initial postgres schema
- **common**: add s3-compatible object store
- **common**: add tenant-scoped object storage interface
- **common**: add pipeline event schema
- **common**: add step result schemas with confidence scores
- **common**: add document type, status and identity models
- **common**: add structured json logging
- **common**: add tenant context propagation
- **common**: add pii masking helpers
- **common**: add environment-driven settings
- **common**: add domain error hierarchy

### Documentation

- **tenant**: describe tenant config file structure

### Build

- allow untyped helper calls in tests

## v0.1.0 (2026-11-01)

### Documentation

- add pull request and issue templates
- **docs**: add readme with problem statement and architecture
- **docs**: add adr for choosing the mit license
- **docs**: add adr for serverless multi-tenant architecture
- **docs**: record architecture decisions in adrs

### Build

- list every commit type in the generated changelog
- add format, coverage and clean make targets
- add pyproject tooling config and make targets

### CI

- validate pull request commit messages with commitizen
- run make check on pushes and pull requests

### Chores

- add repository folder skeleton
- add mit license
- add pre-commit hooks and commitizen config
- initialize repository
