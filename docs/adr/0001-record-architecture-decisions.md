# 0001. Record architecture decisions

- Status: accepted
- Date: 2026-11-01

## Context

The platform combines serverless functions, multi-tenant configuration, OCR,
and local LLMs. Many choices (tooling, storage layout, event transport, model
choice) are not obvious from the code, and the project is also report
material, so the reasoning behind decisions has to survive beyond chat logs
and commit messages.

## Decision

Record every architecturally significant decision as a short Markdown file in
`docs/adr/`, named `NNNN-kebab-title.md`, using the structure in
`docs/adr/template.md` (context, decision, consequences). ADRs are numbered
sequentially and never renumbered. A changed decision gets a new ADR that
supersedes the old one; the old one is marked superseded, not deleted.

## Consequences

- Reviewers can see why something is built a certain way without archaeology.
- Writing an ADR adds a small cost to each significant change.
- The ADR set doubles as source material for the project report.
