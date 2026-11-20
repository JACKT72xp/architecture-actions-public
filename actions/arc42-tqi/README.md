# arc42 TQI Action

## Summary

A GitHub Action that helps teams map repository documentation to **arc42** and
find evidence gaps before architecture knowledge becomes difficult to maintain.
It reads Markdown and AsciiDoc, checks recognized sections and ADRs, and produces
a reproducible **Technical Quality Index (TQI)** with human-readable reports.
It runs offline by default; no LLM or AWS account is required.

## What it checks

- **Structure:** coverage of the 12 arc42 sections, unfinished content, and local references.
- **Decisions:** ADR rationale, alternatives, consequences, lifecycle, and links to architecture sections.
- **Review evidence:** declared references for C4 context/container/component views, deployment, and solution strategy.
- **Compromises:** explicitly documented tactical exceptions and transition plans in individual ADRs, including missing justification or follow-up evidence.

The default score weights structure and decision evidence equally (50% each).
Volatility and Git-history scoring are excluded from the default `arc42` profile.
The strategic baseline is a review policy, not a classification inferred from prose.
A tactical decision is not itself a quality defect. Missing review evidence can
affect the configured severity gate without changing the numeric TQI.

**TQI is this project's documentation metric, not an official arc42 score or a
certification of architectural correctness.** The Action validates recognized
evidence; it does not prove that diagrams, prose, or production agree.

## What you receive

| Output | Use |
| --- | --- |
| `human-summary.html` / `.md` | Start here: score, gate, three priorities, deployment and ADR review coverage |
| `human-report.html` / `.md` | Detailed findings, explanations, evidence references, and next steps |
| `tqi-report.json` and `claims.json` / `.yaml` | Structured evidence for automation and downstream analysis |
| `drift-prompts/` | Prompts for separate code, cloud, and diagram audits |

Artifacts can feed an external RAG pipeline. **AWS ingestion, embeddings, semantic
ADR interpretation, and actual drift detection are not built into this Action.**
Drift analysis requires implementation evidence in addition to documented intent.

## Use in GitHub

Replace `COMMIT_SHA` below with a reviewed full source commit SHA. For published
versions, use the [Marketplace distribution](https://github.com/JACKT72xp/arc42-tqi-action/releases).
The Action runs on Linux and builds its bundled Dockerfile.

```yaml
name: Architecture quality
on: [pull_request, workflow_dispatch]
permissions:
  contents: read
jobs:
  architecture:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803
        with:
          persist-credentials: false
      - uses: JACKT72xp/architecture-actions-public/actions/arc42-tqi@COMMIT_SHA
        with:
          docs-path: docs
          adr-path: docs/adr
          review-profile: arc42
          min-tqi: '0'
          fail-on-severity: none
      - uses: actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f
        if: always()
        with:
          name: architecture-evidence
          path: .arc42-tqi/
          include-hidden-files: true
```

Change the documentation paths to match your repository. This example reports
findings without blocking PRs. Download `architecture-evidence` and open
`human-summary.html`. See [review settings and ADR conventions](docs/review-profiles.md),
[all inputs and detailed usage](docs/usage.md), and [scoring rules](docs/scoring.md).

## Foundations and credits

- **[arc42](https://docs.arc42.org/):** the documentation structure; particularly [solution strategy](https://docs.arc42.org/section-4/), [architecture decisions](https://docs.arc42.org/section-9/), and [risks and technical debt](https://docs.arc42.org/section-11/).
- **ADRs:** decision context, rationale, status, and consequences, following the approach credited to Michael Nygard in arc42's decision guidance.
- **[C4 model](https://c4model.com/diagrams):** context, container, component, and supporting deployment views. Required depth is configurable; C4 does not require every level for every system.

The scoring weights, thresholds, and recognized ADR heading conventions are
project-specific rules. This is an independent implementation, not an official
arc42 or C4 product.

## Tools used

**Python 3.12 + Docker** run the analyzer. **markdown-it-py** parses Markdown;
AsciiDoc recognition uses project-specific parsing. **PyYAML** reads configuration
and structured evidence, **Pydantic** validates typed contracts, and **Typer**
provides the CLI. **GitHub Actions**, `actions/checkout`, and
`actions/upload-artifact` execute the workflow and deliver its reports.
Validation uses pytest, JSON Schema, Ruff, mypy, dependency auditing, and container
smoke tests. The project does not embed docToolchain, log4brains, CodeScene, or ArchUnit.

## License

The Action's source code is released under **[Apache License 2.0](LICENSE)**.
The license text is included in this repository. Referenced methods and
third-party dependencies retain their own licenses and attribution requirements.

## Repository layout

Implementation and documentation are maintained in
[architecture-actions-public](https://github.com/JACKT72xp/architecture-actions-public),
under `actions/arc42-tqi/`. Submit issues and PRs there. The Marketplace repository
is a generated distribution; see [contribution guidance](CONTRIBUTING.md).
