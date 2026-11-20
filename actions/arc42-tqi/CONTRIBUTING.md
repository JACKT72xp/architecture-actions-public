# Contributing

Keep the deterministic analyzer offline, explicit, and auditable. Changes that
alter scoring must update the scoring specification, scoring version, fixtures,
and tests. Avoid opaque semantic scores and false claims of conformance.

## Local checks

Use Python 3.12+ and a virtual environment. Install `.[test]` from this checkout.
Run `python -m pytest`, `python -m ruff check src tests`, and `python -m mypy src`.
The Docker runtime uses Python 3.12 and pure-Python dependency distributions.
Keep runtime dependencies small. Refresh the hash locks from verified PyPI
metadata when changing dependencies. See [Phase 3 status](docs/phase-3.md) for
the current validation boundary. Final CLI schemas, real Git history, bounded prompts and GitHub reporting are
tested. Network calls are mocked; no live comment or enrichment service is needed.

## Pull requests

Explain the architecture or scoring problem, show representative input/output,
and document compatibility implications. Add focused tests for behavior changes,
especially malformed documents, repository-boundary escapes, and score changes.
Do not include credentials, private architecture documents, or personal data.
Preserve existing documentation languages; write new project documentation in English.

## Contracts and releases

Report and claims schemas are versioned independently of package releases.
Additive fields need schema updates and compatibility tests. Breaking changes
require a schema version change. Scores from different scoring versions or
different effective configurations must not be compared without reconciliation.
Follow [the release checklist](docs/releasing.md) before publishing.
