# arc42-tqi-action

> **Phase 3 implemented — source available, no versioned release yet.** The CLI writes the final report,
> claims, bounded audit prompts, and GitHub reporting. Optional semantic enrichment
> stays separate from scoring. See [Phase 3 validation](docs/phase-3.md).


An independent, offline-first GitHub Action and Python CLI for deterministic
architecture-documentation quality assessment. Analyze arc42 Markdown/AsciiDoc,
linked ADRs, explicit claims, and diagram references. Export an auditable **Technical
Quality Index (TQI)** and modular prompts for code, cloud, and diagram audits.

No private repositories, vector databases, LLM keys, cloud credentials, or hosted
service are required. This project implements its own parsers and rules; it does
not embed docToolchain, log4brains, CodeScene, or ArchUnit.

## Quick start

Install Python 3.12+ and run from the repository being assessed:

```sh
python -m pip install /path/to/arc42-tqi-action
arc42-tqi --docs-path docs --adr-path docs/adr --min-tqi 70
```

To exercise this checkout, install the project with `python -m pip install -e .`, then run:

```sh
PYTHONPATH=src python -m arc42_tqi.cli \
  --repo-root tests/fixtures/mature --docs-path docs --adr-path docs/adr
```

### GitHub Actions

Replace `COMMIT_SHA` below with an actual full commit SHA from this repository.
The subdirectory is part of the Action reference. No version tag or public image
is assumed. See the [repository guide](../../README.md) for fork instructions.
The Docker Action requires a Linux runner. Release manifests will reference an
immutable, prebuilt GHCR image; the source manifest builds the local Dockerfile.

```yaml
name: Architecture quality
on: [push, pull_request]
permissions:
  contents: read
jobs:
  architecture:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
        with:
          fetch-depth: 0
      - uses: JACKT72xp/architecture-actions-public/actions/arc42-tqi@COMMIT_SHA
        id: tqi
        with:
          docs-path: docs
          adr-path: docs/adr
          min-tqi: '70'
          fail-on-severity: high
      - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
        if: always()
        with:
          name: architecture-evidence
          path: .arc42-tqi/
          include-hidden-files: true
```

Artifacts and step outputs are written **before** a quality gate fails. A missing
docs/ADR directory produces actionable findings rather than a traceback. An invalid
configuration, unsafe input/output path, or write failure exits with status 2.

## Inputs and outputs

| Input | Default | Behavior |
| --- | --- | --- |
| `docs-path` | `docs` | Directory or entry document, relative to checkout |
| `adr-path` | `docs/adr` | ADR directory or file; excluded from architecture section discovery |
| `diagrams-path` | empty | Optional additional diagram inventory |
| `config-path` | empty | Auto-discover `.arc42-tqi.yml`; explicit missing path is an error |
| `output-dir` | `.arc42-tqi` | Dedicated artifact directory inside the checkout |
| `min-tqi` | empty | Override config minimum; default config is 0 |
| `fail-on-severity` | empty | Override `none`, `critical`, `high`, `medium`, or `low` |
| `llm-provider` | `none` | `none` or opt-in `http-json` semantic adapter |
| `llm-model` | empty | Adapter model identifier |
| `llm-endpoint` | empty | Explicit HTTPS adapter endpoint |
| `llm-api-key` | empty | Secret **value**, e.g. `${{ secrets.ARCHITECTURE_LLM_KEY }}` |
| `comment-pr` | `false` | Upsert same-repository PR bot comment |
| `github-token` | `${{ github.token }}` | Used only when comments are enabled |

Outputs: `tqi-score`, `maturity-level`, `report-path`, `claims-path`,
`drift-prompts-dir`, and `findings-count`. Artifact paths are checkout-relative.
`fail-on-severity: high` blocks critical **and** high findings. Defaults collect
evidence without blocking. CLI flags mirror non-secret inputs (`--comment-pr` enables comments). Secret
values use `ARC42_TQI_LLM_API_KEY` and `ARC42_TQI_GITHUB_TOKEN`, never command-line
arguments. Action inputs are mapped to `ARC42_TQI_*` environment variables.

For comments, set `comment-pr: 'true'`, `github-token: ${{ github.token }}`, and job
permission `pull-requests: write`. Comments are skipped for fork PRs and non-PR events;
an unavailable comment API does not fail scoring. Do not use `pull_request_target`
to run an untrusted checkout. The deterministic mode needs only `contents: read`.

## What is measured

| Dimension | Default weight | Evidence |
| --- | ---: | --- |
| Structure | 25% | Twelve canonical sections, critical-section depth, placeholders, local links, headings |
| Decisions | 25% | ADR fields, lifecycle, alternatives/consequences, quality attributes, section links |
| Volatility | 25% | Classified change axes, information-hiding boundaries, impact, mitigation, Git hotspots |
| Drift readiness | 25% | Six claim categories, typed completeness, provenance, atomic checks, referential integrity |

Every metric exposes its numerator, denominator, ratio, weight, and definition.
See [the exact scoring specification](docs/scoring.md). Repository overrides are
deep-merged and strictly validated; unknown keys, invalid types, NaN, negative
weights, and all-zero weight groups are rejected.

| TQI | Level |
| --- | --- |
| 0 ≤ score < 40 | L1 — Initial / Incomplete |
| 40 ≤ score < 70 | L2 — Foundational / Evolving |
| 70 ≤ score < 90 | L3 — Solid / Aligned |
| 90 ≤ score ≤ 100 | L4 — Reference / Audit-ready |

**TQI evaluates documentation evidence, not truth, security, or implemented
conformance. L4 alone does not mean an implementation has been audited.** The score
can be increased by writing shallow but syntactically complete statements; review
the evidence and run the generated audit prompts against real technical sources.

## Document and ADR conventions

Use canonical section titles in EN, ES, or DE, optionally prefixed by their number.
See [supported aliases](src/arc42_tqi/documents.py). Markdown ATX headings and
AsciiDoc `=` headings are supported. Bare numbered headings are deliberately not
classified: an unrelated `## 5. Some Topic` must not be mistaken for arc42.
`include::relative/file.adoc[]` works across Markdown and AsciiDoc with cycle,
depth, byte, and repository-boundary checks. Relative Markdown links are checked;
directory inputs discover documents within that directory tree. Entry-file and
directory inputs follow local documentation links within the repository, excluding
the configured ADR and artifact paths from architecture section discovery.

ADRs use headings for Context, Decision, Alternatives, Consequences, and Quality
Attributes, plus YAML front matter for `id`, `title`, `status`, `arc42_sections`,
`supersedes`, `superseded_by`, and `related`. ID defaults to the numbered filename;
Status also supports a labeled line or a heading. Supported lifecycle values are
`proposed`, `accepted`, `deprecated`, and `superseded`. ADRs linked from an arc42
section inherit that traceability. Only accepted ADRs generate active constraints.
See [the complete ADR fixture](tests/fixtures/mature/docs/adr/0001-queue.md).

## Claims and drift evidence

Place YAML inside fenced `arc42-claims` blocks, or AsciiDoc
`[source,arc42-claims]` blocks. See [the contract guide](docs/contracts.md),
[the mature example](tests/fixtures/mature/docs/architecture.md), and
[JSON Schemas](schemas/). Each claim has a stable ID and parser-owned provenance.
The parser never treats arbitrary prose or a diagram image as a proven assertion.

The output directory contains:

```text
tqi-report.json
claims.yaml
claims.json
summary.md
drift-prompts/
  drift-against-code.md
  drift-against-cloud.md
  drift-against-diagrams.md
```

Each prompt embeds relevant claims and a compact report context, requests read-only
evidence, and defines `conformant`, `drift`, `unverifiable`, and `not_applicable`.
Defaults limit each module to 80 claims, 24,000 embedded JSON characters and 20
findings. Claims are kept whole; omitted claims have exact array ranges in the
report's `prompt_manifest`. Report pointers and diagram inventory references identify
additional evidence to supply. Copy the prompt with `tqi-report.json` and
`claims.json` when it references omitted evidence; a prompt alone is not always a
complete audit bundle. Supply code, cloud inventories/IaC, or diagrams separately.
Prompts do not execute an audit. Diagram references include Mermaid, PlantUML,
Structurizr, Draw.io, SVG, PNG, and JPG.

External RAG or factual-knowledge pipelines can index claim IDs, source locations,
source SHA-256 digests, commit metadata, and finding rule IDs directly. No vendor
API, embedding model, or vector store is part of the deterministic core.

## Optional semantic adapter

The built-in `http-json` adapter is provider-neutral, not a direct vendor SDK.
Supply a bridge to your chosen model service using the documented request/response
contract in [integrations](docs/integrations.md). The endpoint receives the complete
architecture report and claims only when explicitly enabled. Deterministic analysis
never transmits documents. API keys are read from `llm-api-key` or
`ARC42_TQI_LLM_API_KEY`, never included in evidence, and never printed in errors.

Semantic observations are untrusted, non-scoring annotations in
`semantic_enrichment`. Endpoint failure is recorded without failing the quality
gate. The deterministic prompt generator remains available without any model.

## Limits and reproducibility

No remote links, AsciiDoc macros, diagram programs, repo Python, or scripts are
executed. Includes with attributes or substitutions are reported, not silently
expanded. Markdown Setext headings, full CommonMark rendering, arbitrary prose
inference, visual diagram understanding, and semantic equivalence are not provided.
Git history is optional and bounded; shallow or unavailable history is N/A, not a
fabricated failure or a perfect evolutionary score. File-based history cannot
reliably attribute separate sections in one monolithic file; use separate ADR/risk
files and treat hotspots as review signals.

The same sources, configuration, tool/runtime versions, commit, repository
environment, and Git history yield byte-identical artifacts in deterministic mode.
There are no wall-clock timestamps or absolute source paths in reports. Opt-in LLM
observations are inherently non-reproducible but cannot change the TQI or gates.
GitHub-hosted runner OS images are not hermetic; runtime dependencies are pinned and
hash verified. Pin the Action commit and preserve the reported inputs for audits.

## Development and release

```sh
python -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest
.venv/bin/python -m ruff check src tests
.venv/bin/python -m mypy src
```

The target runtime is Python 3.12. Tests cover final schemas, prompt bounds,
reproducibility, integration failures and GitHub reporting; CI checks Action outputs. See [CONTRIBUTING](CONTRIBUTING.md),
[architecture decisions](docs/architecture.md), and [release checklist](docs/releasing.md).
Apache-2.0 licensed. The Action has not been registered in GitHub Marketplace.


## Repository layout

Run development commands from `actions/arc42-tqi/`. Workflows live at the repository
root in `.github/workflows/`; release tags are scoped as `arc42-tqi/vMAJOR.MINOR.PATCH`
and images as `ghcr.io/OWNER/REPOSITORY-arc42-tqi`. Forks derive their own namespace
from GitHub context. The source Action builds its adjacent Dockerfile automatically.
