# Architecture review profiles

Version 0.2.0 makes `arc42` the default. It scores documentation structure
and typed decision evidence, with default weights 50/50. Volatility, Git mining,
and audit-readiness checks do not affect its score or gate. Claims and separate
audit prompts remain auxiliary exports. Existing four-dimension assessments can
be reproduced with `review-profile: extended` (scoring version 1.0). The arc42
profile records scoring version 2.0; generated reports use schema 1.1 (claims remain 1.0): do not compare scores across these profiles
as if the architecture had improved. Re-run the source repository; never relabel
an old bundle's score.

## Configure the Action

```yaml
- uses: JACKT72xp/architecture-actions-public/actions/arc42-tqi@COMMIT_SHA
  with:
    docs-path: docs
    adr-path: docs/adr
    config-path: .arc42-tqi.yml
    review-profile: arc42
    review-rigor: strict
    architecture-type: transition
    c4-level: component
    deployment-view: required
    min-tqi: '70'
    fail-on-severity: high
```

Use a reviewed full source commit SHA containing this change. The v0.1.0 distribution does not provide these inputs; use v0.2.0 or later. After upstream merge, export
and release the distribution through its normal PR/release process.

Action inputs override repository `review` settings; empty inputs preserve them.
Profile defaults are applied before repository overrides. The `arc42` profile
rejects positive volatility/drift weights or enabled Git history to prevent
accidentally reintroducing excluded checks. Structure/decision weights,
`critical_sections`, `min_section_words`, `min_tqi`, and `fail_on_severity` remain
configurable using the existing configuration contract.

| Setting | Values and effect |
| --- | --- |
| `review-rigor` | `advisory`: missing/invalid review references are low severity; `standard`: medium; `strict`: high |
| `architecture-type` | `strategic`: direction and target state; `tactical`: bounded delivery scope; `transition`: current/target state, migration stages, rollback/recovery |
| `c4-level` | `context`; `container` includes context; `component` includes context and containers. Code-level diagrams are never required. |
| `deployment-view` | `required` adds a deployment evidence check; `not-required` explicitly removes that check |

Defaults: arc42, standard, tactical, component, required. Rigor changes severity,
not TQI arithmetic or a claim of semantic understanding. With `min-tqi: 0` and
`fail-on-severity: none`, even strict review remains non-blocking. A high score
can coexist with unresolved review expectations: inspect both score and gate.
The architecture-type definitions are project review policies, not official
arc42 maturity categories. Type is declared by the operator, never inferred from
a few keywords.

## Reference evidence instead of adding machine-only prose

Keep normal architecture prose and diagrams. Map exact ranges in scanned text
files to the expectations in `.arc42-tqi.yml`; do not duplicate prose into claims
just to satisfy a review check. Example paths/ranges below must be replaced with
real source locations:

```yaml
version: 1
review:
  profile: arc42
  rigor: standard
  architecture_type: tactical
  c4_level: component
  deployment_view: required
  evidence:
    context:
      - {file: docs/architecture.md, line: 20, end_line: 35}
    container:
      - {file: docs/architecture.md, line: 50, end_line: 70}
    component:
      - {file: docs/architecture.md, line: 75, end_line: 95}
    deployment:
      - {file: docs/architecture.md, line: 110, end_line: 130}
    tactical_scope:
      - {file: docs/architecture.md, line: 38, end_line: 48}
```

Additional evidence keys: `strategic_intent`, `current_state`, `target_state`,
`migration_plan`, `rollback`. Each list supports up to 100 references; each range
supports at most 200 lines. Files must already be in the scanned text inventory;
paths are repository-relative and line numbers are one-based. Reference a diagram's
explanation or inline source in the scanned document. Arbitrary external files,
image pixels, and network content are not read through this mapping.

Valid ranges are `evidence_available`, with a source excerpt (up to 4,096 characters, explicitly marked when truncated), source hash, and
`declared` evidence level. Missing, invalid, empty, or placeholder-bearing ranges
are `unknown`. The report preserves rejected references and reasons. These checks
establish availability only: they do not prove that a referenced paragraph is a
C4 view, validate diagram topology, or approve its architecture. The overall
review remains `review_required` even when all references are available.

Start with `human-summary.html` or `human-summary.md`: score, gate outcome, three
grouped priorities, and a plain-language deployment status. GitHub summaries and PR
comments use this bounded view. Groups are ordered by blockers, severity, and count;
remaining groups are explicitly counted.

The detailed human report includes every finding, its implication, remediation, task,
and completion criteria. Review evidence shows at most three example locations with
rejected references first. All excerpts, hashes, and references remain in the JSON.

## Relationship to RAG architecture intelligence

The RAG progress notes describe a complementary evidence system. This Action does
not currently connect to that RAG, its graph, or its MCP tools. The existing
optional semantic adapter remains advisory and cannot change scores or gates.
Do not interpret configuring `architecture-type` as automatic RAG classification.

A future integration should preserve this boundary:

| Evidence | Permitted interpretation |
| --- | --- |
| Declared arc42/ADR text | Design intent with repository, commit, file, line range, and content hash |
| Depicted diagram relation | Diagram content with diagram source, extraction method, and validated endpoints |
| Observed Git change | A change observation with commit/window and coverage; not implementation behavior |
| Observed code or deployed state | Separately captured implementation evidence with revision or timestamp and scope |

RAG-proposed facts and architecture types should include source ranges, extraction
method, evidence level, confidence/calibration information, and validation status.
Treat model output as untrusted proposals. Validate repository/commit alignment,
source bounds and hashes, cited names, and relation endpoints before presenting
facts; name presence alone does not establish a relation. Retain conflicting
assertions instead of collapsing declared, depicted, and observed edges.

For strategic/tactical/transition classification, show the cited justification
and allow human correction. Missing evidence or thin history must remain unknown
with a reason. Coverage and extraction precision must be reported separately
from architecture quality. Gate 1 review and measured precision are prerequisites
for any proposal to use RAG indicators for ranking or blocking; this implementation
does neither. Volatility belongs to that separate intelligence workflow, not to
the default arc42 quality score.

The next integration requires a versioned, sanitized sample payload and an agreed
read-only interface. No private RAG endpoint, credentials, or architecture corpus
is embedded in this public Action.

## Reference conventions

The [C4 model](https://c4model.com/diagrams) defines context, container, component,
and code views and allows selecting useful levels. Requiring depth through
components here is a configurable team policy. The
[arc42 deployment view](https://docs.arc42.org/section-7/) describes infrastructure
and deployment; [section 11](https://docs.arc42.org/section-11/) covers risks and
technical debt. Retaining section 11 does not require a volatility score.
