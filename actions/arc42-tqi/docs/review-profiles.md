# Architecture review profiles

Version 0.2.0 makes `arc42` the default. It scores documentation structure
and typed decision evidence, with default weights 50/50. Volatility, Git mining,
and audit-readiness checks do not affect its score or gate. Claims and separate
audit prompts remain auxiliary exports. Existing four-dimension assessments can
be reproduced with `review-profile: extended` (scoring version 1.0). The arc42
profile records scoring version 2.0; generated reports use schema 1.2 (claims remain 1.0): do not compare scores across these profiles
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
| `c4-level` | `context`; `container` includes context; `component` includes context and containers. Code-level diagrams are never required. |
| `deployment-view` | `required` adds a deployment evidence check; `not-required` explicitly removes that check |

Defaults: arc42, standard, component, required. The review baseline is strategic. Rigor changes severity,
not TQI arithmetic or a claim of semantic understanding. With `min-tqi: 0` and
`fail-on-severity: none`, even strict review remains non-blocking. A high score
can coexist with unresolved review expectations: inspect both score and gate.
The strategic baseline is a team review policy, not an official arc42 classification
or a claim that the documentation proves strategic alignment. Section 4 must still
explain the solution strategy. Tactical compromises and transition plans belong to
individual decisions; an ADR can document both.

## Migration from v0.2.x

Remove `architecture-type` from Action inputs, `--architecture-type` from CLI
arguments, and `review.architecture_type` from repository configuration. Remove
any workflow-dispatch selector and its fallback. Move the old purpose-specific
`review.evidence` mappings (`tactical_scope`, `current_state`, `target_state`,
`migration_plan`, `rollback`) into the relevant ADR narrative; those configuration
keys are no longer accepted. Keep `strategic_intent` for the section 4 evidence. The removed configuration key
is rejected instead of silently changing its meaning. No workflow classification
is needed in the new model. Existing published v0.2.x tags keep their old behavior.

The numeric TQI formula remains scoring 2.0. The required review now checks
strategic direction instead of a selected purpose checklist. ADR exception gaps
use the configured rigor and can change severity-gate results. Re-run and review
gates when upgrading. Report schema 1.2 adds `baseline` and `decision_assessments`;
old saved reports remain renderable without rescoring.

## Examine decisions against the strategy

arc42 [section 4](https://docs.arc42.org/section-4/) explains the solution strategy;
[section 9](https://docs.arc42.org/section-9/) records significant decisions,
alternatives, rationale, status, and consequences; [section 11](https://docs.arc42.org/section-11/)
records risks and technical debt. A justified compromise is not automatically a
quality defect. Review its documented rationale and consequences instead.

The offline checker recognizes explicit Markdown or AsciiDoc ADR headings below.
Write normal prose under them; no YAML classification field is required. These
are this tool's evidence conventions, not mandatory arc42 headings. Spanish
headings are supported as shown. Other prose remains for human interpretation;
absence of recognized headings does not prove absence of compromises.

| Heading | Spanish equivalent | Purpose |
| --- | --- | --- |
| Strategic alignment | Alineación estratégica | Explain the relationship to the section 4 strategy, with a reference |
| Tactical exception | Excepción táctica | Declare the compromise and explain the business or external constraint |
| Review condition | Condición de revisión | State when or under what condition the compromise must be reconsidered |
| Transition plan | Plan de transición | Explain the stages toward the intended solution |
| Exit criteria | Criterios de salida | State what establishes completion of the intermediate state |
| Rollback and recovery | Reversión y recuperación | Explain recovery if the transition fails, or justify why rollback is inapplicable |

For a tactical exception, review alignment, exception rationale, consequences,
and a review condition. For a transition plan, review alignment, the plan,
consequences, exit criteria, and recovery. Consequences use the existing ADR
contract. Missing or placeholder text raises an evidence finding; the presence
of prose only establishes availability, never the soundness of its reasoning.
The checker does not validate strategy links, deadlines, ownership, or feasibility.
Review these manually, including any linked section 11 risks or debt.

Accepted and proposed decisions are reviewed; decisions with unspecified lifecycle
also remain review candidates. Deprecated and superseded decisions remain visible
as historical evidence and create no new exception findings. Existing lifecycle
validation still applies. An ADR without declarations is reported as intent not
established, never automatically classified as strategic.

```markdown
## Strategic alignment
The order service remains the target data owner; see section 4, Solution Strategy.

## Tactical exception
The supplier deadline requires a temporary shared-database adapter. The service
API cannot be delivered by that date. The decision's alternatives and consequences
explain the trade-off and its coupling risk (tracked in section 11).

## Review condition
The service owner reopens this decision when the supplier API becomes available.

## Transition plan
Introduce the API, migrate clients, and remove shared-database access.

## Exit criteria
All clients use the API and shared-database credentials have been revoked.

## Rollback and recovery
Restore the previous client routing if reconciliation detects missing orders.
```

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
    strategic_intent:
      - {file: docs/architecture.md, line: 38, end_line: 48}
```

Supported evidence keys are `context`, `container`, `component`, `deployment`,
and `strategic_intent`. Each list supports up to 100 references; each range
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
Explicit ADR heading recognition is not semantic RAG classification.

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
