# arc42-tqi-action

> **Beta implementation.** The CLI writes the final report,
> claims, bounded audit prompts, and GitHub reporting. Optional semantic enrichment
> stays separate from scoring. See [Phase 3 validation](docs/phase-3.md).


An independent, offline-first GitHub Action and Python CLI for deterministic
architecture-documentation quality assessment. Analyze arc42 Markdown/AsciiDoc,
linked ADRs, explicit claims, and diagram references. Export an auditable **Technical
Quality Index (TQI)** and modular prompts for code, cloud, and diagram audits.

No private repositories, vector databases, LLM keys, cloud credentials, or hosted
service are required. This project implements its own parsers and rules; it does
not embed docToolchain, log4brains, CodeScene, or ArchUnit.

## Review scope and rigor

The default `arc42` profile scores structure and decision evidence. Volatility,
Git history, and audit readiness are excluded from its score and gate. Configure
`review-rigor`, `architecture-type`, `c4-level`, and `deployment-view` in the Action.
See [review profiles and RAG boundaries](docs/review-profiles.md) for evidence
mapping, examples, and migration from the `extended` legacy rubric. These inputs are available starting with v0.2.0; v0.1.0 behavior is unchanged.

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
The Docker Action requires a Linux runner and builds the bundled Dockerfile.
Marketplace versions are published from the dedicated distribution repository.

```yaml
name: Architecture quality
on: [push, pull_request]
permissions:
  contents: read
jobs:
  architecture:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803
        with:
          fetch-depth: 0
      - uses: JACKT72xp/architecture-actions-public/actions/arc42-tqi@COMMIT_SHA
        id: tqi
        with:
          docs-path: docs
          adr-path: docs/adr
          review-profile: arc42
          review-rigor: standard
          architecture-type: tactical
          c4-level: component
          deployment-view: required
          min-tqi: '70'
          fail-on-severity: high
      - uses: actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f
        if: always()
        with:
          name: architecture-evidence
          path: .arc42-tqi/
          include-hidden-files: true
```

Artifacts and step outputs are written **before** a quality gate fails. A missing
docs/ADR directory produces actionable findings rather than a traceback. An invalid
configuration, unsafe input/output path, or write failure exits with status 2.

## Start with the human report

Download the workflow artifact and open **human-report.html** in a browser. It is
self-contained, works offline, requires no LLM, and can be printed. The equivalent
**human-report.md** is suitable for GitHub and Markdown viewers. Both are generated
even when a quality gate fails, alongside the existing machine-readable evidence.

The report explains the score's weighted contributions, why the gate passed or
failed, priority documentation risks and next steps, all 12 sections, structured
evidence coverage, every metric, and every finding with its source, review implication, concrete task, and completion criteria.
It distinguishes parser recognition gaps from verified architecture defects and
labels optional semantic observations separately. It does not rescore the analysis
or certify implementation conformance. `summary.md` remains a compact CI overview.

To add human reports to an older downloaded bundle, install this checkout with
`python -m pip install -e .`, then run:

```sh
PYTHONPATH=src python scripts/render_human_report.py --artifacts /path/to/downloaded-artifact
```

This reads matching `tqi-report.json` and `claims.json` snapshots and adds only the
two human-report files. It does not modify the saved JSON, claims, or audit prompts.

## Inputs and outputs

| Input | Default | Behavior |
| --- | --- | --- |
| `docs-path` | `docs` | Directory or entry document, relative to checkout |
| `adr-path` | `docs/adr` | ADR directory or file; excluded from architecture section discovery |
| `diagrams-path` | empty | Optional additional diagram inventory |
| `config-path` | empty | Auto-discover `.arc42-tqi.yml`; explicit missing path is an error |
| `output-dir` | `.arc42-tqi` | Dedicated artifact directory inside the checkout |
| `min-tqi` | empty | Override config minimum; default config is 0 |
| `review-profile` | empty → arc42 | `arc42` or legacy `extended` |
| `review-rigor` | empty → standard | `advisory`, `standard`, or `strict` |
| `architecture-type` | empty → tactical | `strategic`, `tactical`, or `transition` |
| `c4-level` | empty → component | `context`, `container`, or `component` |
| `deployment-view` | empty → required | `required` or `not-required` |
| `fail-on-severity` | empty | Override `none`, `critical`, `high`, `medium`, or `low` |
| `llm-provider` | `none` | `none` or opt-in `http-json` semantic adapter |
| `llm-model` | empty | Adapter model identifier |
| `llm-endpoint` | empty | Explicit HTTPS adapter endpoint |
| `llm-api-key` | empty | Secret **value**, e.g. `${{ secrets.ARCHITECTURE_LLM_KEY }}` |
| `comment-pr` | `false` | Upsert same-repository PR bot comment |
| `github-token` | `${{ github.token }}` | Used only when comments are enabled |

Outputs: `tqi-score`, `maturity-level`, `report-path`, `human-report-path`,
`human-report-html-path`, `claims-path`,
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
| Structure | 50% | Twelve canonical sections, critical-section depth, placeholders, local links, headings |
| Decisions | 50% | ADR fields, lifecycle, alternatives/consequences, quality attributes, section links |
| Volatility (extended only) | 0% | Classified change axes, information-hiding boundaries, impact, mitigation, Git hotspots |
| Drift readiness (extended only) | 0% | Six claim categories, typed completeness, provenance, atomic checks, referential integrity |

The explicit `extended` profile uses 25% for each of the four dimensions.

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
human-report.md
human-report.html
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
Apache-2.0 licensed. See the [distribution releases](https://github.com/JACKT72xp/arc42-tqi-action/releases)
for published versions and the Marketplace publication status.


## Repository layout

Run development commands from `actions/arc42-tqi/` in the main repository.
All contributions go through PRs there, including distribution templates under
`distribution/arc42-tqi/`. Marketplace versions (`vMAJOR.MINOR.PATCH`) are published
from `JACKT72xp/arc42-tqi-action` after exporting a reviewed upstream commit.
See the [release checklist](docs/releasing.md).
