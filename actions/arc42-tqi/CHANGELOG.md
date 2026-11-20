# Changelog

## 0.2.2

- Shorten Action metadata to meet the GitHub Marketplace description limit.
- Validate Marketplace metadata in CI to prevent publication regressions.
- Includes the concise human summaries from v0.2.1; scoring, gates, inputs, and outputs are unchanged.

## 0.2.1

Start with `human-summary.html` for the concise assessment. Existing detailed
reports and machine artifacts remain available. Scoring, gates, and configuration
remain compatible with v0.2.0; the new summary output paths are additive.

- Add bounded human-summary HTML/Markdown with three grouped priorities and a plain-language deployment status; use it in GitHub summaries and PR comments.
- Start detailed reports with the concise summary; show at most three review source examples and retain complete evidence in JSON.
- Explain rejected evidence links with specific reasons. Scoring and gate behavior are unchanged.

## 0.2.0

Compatibility: the default scoring profile changes to arc42 (scoring 2.0).
Scores are not directly comparable with 0.1.0. Set `review-profile: extended`
to retain the legacy four-dimension rubric. Generated report schema is 1.1;
claims remain schema 1.0. Review existing configuration overrides before upgrading.

- Default arc42 scoring profile excludes volatility, Git history, and audit-readiness penalties; retain `extended` for legacy scoring.
- Configurable rigor, architecture purpose, C4 depth, and deployment evidence review with source excerpts and unknown states.
- Detailed finding implications, review tasks, and completion criteria; all findings appear in the workflow summary.

- Add offline human-readable HTML and Markdown reports explaining recorded TQI
  contributions, quality gates, documentation risks, prioritized next steps,
  complete findings, and assessment limitations. The renderer preserves saved scores.
- Report schema 1.1 adds explicit review scope and evidence; the renderer also supports historical schema 1.0 bundles.
- Add human-report output paths and a renderer for existing artifact bundles.

## 0.1.0

Initial beta release of deterministic arc42 documentation scoring, ADR traceability,
architecture claims, Git history signals, and bounded audit prompts.

- Supports Linux Docker runners with no required external service or credentials.
- Includes optional semantic enrichment and PR comments, disabled by default.
- Uses report/claims schema version 1.0 and scoring version 1.0.
- Documentation maturity does not certify implementation conformance.
