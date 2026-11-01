# 0003. License the project under MIT

- Status: accepted
- Date: 2026-11-01

## Context

The project is built entirely on open-source components and is intended to be
studied, reused and extended by universities and students. Its dependencies
use permissive licenses (Apache-2.0, MIT, BSD) that are compatible with any of
the common choices. The candidates were MIT, Apache-2.0 and GPL-3.0.

## Decision

Use the MIT License.

- MIT is short, widely understood, and imposes only attribution.
- GPL-3.0 would discourage a university IT team from adapting the platform
  inside closed internal systems, which works against adoption.
- Apache-2.0 adds an explicit patent grant, which matters less for a small
  academic project than the simplicity of MIT.

## Consequences

- Anyone may reuse the code, including in proprietary systems, with
  attribution.
- There is no explicit patent grant; contributors who need one should raise it
  and we can revisit with a superseding ADR.
- The license covers code only. All data in the repository is synthetic; the
  license does not and cannot grant rights over any real personal data.
