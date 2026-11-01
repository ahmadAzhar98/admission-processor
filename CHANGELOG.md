## v1.0.0 (2026-11-01)

### Documentation

- **docs**: link the documentation set from the readme
- **docs**: add contributing guide with the git workflow
- **docs**: document limitations and future work
- **docs**: add deployment guide
- **docs**: add security and privacy notes
- **tenant**: add tenant configuration guide
- **docs**: document every function's interface and behaviour
- **docs**: add architecture overview with mermaid diagrams

### Build

- end major version zero ahead of the 1.0.0 release

## v0.9.0 (2026-11-01)

### Bug Fixes

- **extract**: read values printed beside captions on the same row

### Tests

- **synthetic**: filter accuracy runs by language and profile
- add cold versus warm latency measurement script
- add k6 deadline-night burst script
- **synthetic**: add paddleocr versus tesseract comparison script
- **synthetic**: add accuracy evaluation script
- **synthetic**: add accuracy metrics for the evaluation scripts
- run every step end to end over synthetic applications
- add an in-process pipeline runner

### Documentation

- **docs**: report measured evaluation results
- **docs**: add serverless versus always-on cost methodology

## v0.8.0 (2026-11-01)

### Features

- **infra**: add grafana dashboard for the pipeline
- **infra**: add prometheus scrape config and pipeline alerts

### Tests

- **common**: cover postgres repositories and s3 against live services

### Documentation

- **infra**: add k3s, faasd and local deployment notes

### Build

- **infra**: add monitoring profile to the compose stack
- **infra**: add kubernetes manifests for stateful dependencies
- add make targets for local services and migrations
- **infra**: add docker compose stack for local services

## v0.7.0 (2026-11-01)

### Features

- **tenant**: add onboarding handler storing drafts for approval
- **tenant**: add llm-assisted tenant config drafting

## v0.6.0 (2026-11-01)

### Features

- **notify**: send tenant templates once per subject and event
- **notify**: add pluggable log and webhook channels
- **common**: add notification log for exactly-once sends
- **ui**: add feedback learner storing corrections as examples
- **ui**: add streamlit staff review page
- **decide**: treat reviewer verdicts as final evidence
- **ui**: add fastapi review queue api
- **ui**: add review resolution service
- **tenant**: add a staff credential separate from the upload key
- **decide**: wire handler and register function in the stack
- **decide**: apply decisions, open reviews and audit outcomes
- **decide**: add decision policy over collected evidence
- **common**: add review queue repository
- **crosscheck**: wire handler and register function in the stack
- **crosscheck**: compare fields once an application is complete
- **crosscheck**: add fuzzy name and exact identifier matching

### Bug Fixes

- **infra**: mount tenant api key secrets for intake and precheck

### Documentation

- **docs**: record the idempotency strategy in adr 0006

### Build

- **infra**: package the streamlit review ui
- **infra**: package the review api with the dockerfile template

## v0.5.0 (2026-11-01)

### Features

- **validate**: run rules in the pipeline and register the function
- **validate**: add tenant rule evaluation engine
- **extract**: wire handler and register function in the stack
- **extract**: extract tenant fields in the pipeline step
- **extract**: merge ocr and llm readings into confidence scores
- **extract**: add schema-driven llm extraction with few-shot examples
- **common**: provide the example repository through the runtime
- **common**: add tenant few-shot example repository
- **extract**: add caption-based extraction from ocr lines
- **tenant**: list every printed caption in field labels
- **extract**: add value normalisers for dates and amounts

## v0.4.0 (2026-11-01)

### Features

- **classify**: wire handler and register function in the stack
- **classify**: classify uploads and route them onward
- **classify**: add llm fallback for low-confidence documents
- **classify**: add keyword and layout document classifier
- **common**: expose ocr and llm clients through the runtime
- **common**: add ollama llm client with structured json output
- **common**: add paddleocr adapter with tesseract fallback
- **common**: add tesseract ocr adapter
- **common**: add ocr engine interface and result model
- **quality**: wire handler with async step and sync precheck modes
- **quality**: assess uploads against tenant thresholds
- **quality**: add opencv blur, skew and contrast measures
- **intake**: register intake in the openfaas stack
- **intake**: wire openfaas handler with tenant authentication
- **intake**: add upload validation and idempotent storage
- **common**: add tenant api key authentication
- **common**: add shared async pipeline step runner
- **common**: add runtime dependency container
- **common**: add event publisher over openfaas async invocations
- **common**: add openfaas http handler adapter

### Bug Fixes

- **tenant**: calibrate quality thresholds to the measured metrics

### Refactoring

- **common**: extract the default tenant authenticator
- **common**: type the in-memory runtime concretely

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
