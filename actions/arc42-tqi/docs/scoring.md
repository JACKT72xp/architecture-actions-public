# Scoring specification 1.0

TQI is a deterministic index of **documented evidence**. Each metric stores integers
`satisfied` and `applicable`; its ratio is `satisfied / applicable`. A zero denominator
means N/A and contributes neither numerator nor weight. Missing **required**
evidence uses denominator one and numerator zero, never N/A.

For dimension d, using configured metric weights w:

```text
D[d] = 100 × sum(w[m] × satisfied[m] / applicable[m]) / sum(w[m])
                         over applicable metrics only
TQI  = round_half_up(sum(W[d] × D[d]) / sum(W[d]), 2)
```

All four dimension weights default to 25. Calculations use exact rational arithmetic (`Fraction`); only final TQI is
rounded half-up to two decimals. Dimension values are serialized as floats. If all positive-weight metrics in a dimension are N/A,
the dimension scores zero. Zero weights disable a contribution; weight groups must
have a positive total. Maturity is derived from the final rounded TQI: L1 below 40,
L2 below 70, L3 below 90, otherwise L4.

## Structure

| Metric | Weight | Exact numerator / denominator |
| --- | ---: | --- |
| coverage | 25 | Sections with any non-placeholder prose / 12 |
| depth | 20 | Critical sections with ≥40 prose words / configured critical sections |
| placeholders | 20 | Populated sections without placeholder tokens / 12 |
| references | 15 | Valid local references / discovered local references; zero references is N/A |
| headings | 10 | Well-formed headings without level jumps / headings; none scores zero |

Default critical sections: 5, 6, 7, 9, 10, 11. Fenced code, diagrams, claim blocks,
headings, and whole lines containing placeholder tokens do not count as prose depth.
Reference checks cover supported Markdown inline/reference definitions and
AsciiDoc image/link/xref/include syntax. Remote links are neither fetched nor scored.

| diagrams | 10 | Available local/inline diagrams / declared local/inline diagrams; remote references excluded; none is N/A |

## Decisions

All denominators are the count of parsed ADRs, or one if absent, plus one deficit
for each rejected ADR document.

| Metric | Weight | Passing ADR predicate |
| --- | ---: | --- |
| completeness | 25 | Non-placeholder ID, title, context, decision, consequences |
| lifecycle | 20 | Unique ID; valid state; relationships target other existing ADRs; superseded ADR names an accepted successor; supersedes targets retired decisions |
| tradeoffs | 20 | Meaningful typed alternatives with rejection reasons and both positive/negative consequences |
| quality_attributes | 10 | Explicit non-placeholder quality attributes |
| bidirectional_traceability | 25 | At least one edge; every declared or discovered section edge is reciprocal and targets a populated section |

Proposed decisions are legitimate lifecycle records, not automatically stale. There
is no wall-clock-based freshness penalty. Only accepted decisions become active
claims. Dates alone cannot establish that a design decision remains valid.

## Volatility

Axes: `business_rules`, `external_integrations`, `data_schemas`,
`security_compliance`, `infrastructure`. No project is required to have every axis.
The structural denominator is the number of explicit zones plus the number of
sections mentioning volatility without an explicit zone in that section, plus
component change axes without a corresponding zone. The minimum is one when
volatility is required, otherwise zero. This makes undeclared change axes visible instead of
rewarding omission. Classification checks resolve component IDs.

| Metric | Weight | Numerator |
| --- | ---: | --- |
| classification | 25 | Zones with recognized axis and existing component |
| encapsulation | 30 | Zones with a non-placeholder isolation strategy |
| impact_mitigation | 30 | Zones with propagation risk, impact, and mitigation |
| evolution | 15 | Aligned hotspots plus declared directed temporal couplings / all detected evolutionary signals |

Evolution analyzes at most 200 non-merge commits, including initial additions.
A hotspot is a section-bearing file changed in at least five commits. ADRs are
associated through their section links; separately tracked risk documents are
associated by explicit relative Markdown links. An unrelated ADR change does not satisfy a
hotspot, and a file cannot satisfy its own associated-update check. The current
implementation conservatively requires separately tracked decision/risk evidence; a
monolithic document needs human review for section-level risk maintenance.
Directed coupling requires at least three co-changes and a source-relative ratio
of at least 0.5 by default; Jaccard similarity is also exported. Staleness uses HEAD
commit time, never wall-clock time. Explicit `reviewed_against` evidence can align
a hotspot within the configured 30-day staleness window.
Unavailable, shallow, or fewer-than-two-commit history is N/A, as is a window
without evolutionary signals. Truncated windows still contribute measured signals. These limits appear in the report. No LLM infers hidden change
coupling, and file churn is not proof of faulty architecture.

## Drift readiness

| Metric | Weight | Exact numerator / denominator |
| --- | ---: | --- |
| coverage | 20 | Nonempty applicable categories / applicable categories |
| completeness | 25 | Claims with required meaningful, typed fields / claims |
| provenance | 20 | Claims with a readable source and in-range source line / claims |
| atomic_verifiability | 20 | Claims with a valid typed verification predicate / claims plus deficits |
| integrity | 15 | Claims with valid component/ADR lifecycle references / claims plus deficits |

Each missing required category adds one deficit to non-coverage denominators.
Each rejected claims block adds one further deficit to those denominators.
Provenance also verifies end-line bounds and the source SHA-256 digest.

All six categories are required by default. A category can be declared not required
with a documented reason in `applicability`; populated categories remain applicable.
All explicitly non-applicable, empty categories yield N/A metrics. An empty component
`declared_volatility` list declares no known axis and is structurally valid. Do not
invent cloud resources to earn coverage credit: record non-applicability instead.
Verification uses typed target/property/operator/expected/method fields; see the
[contract guide](contracts.md). These predicates measure audit readiness, not truth.

## Findings and gates

Findings do not subtract hidden points. They explain missing evidence or violations
independently of ratios. The minimum-score gate and severity gate are OR conditions
for failure; the severity threshold includes every more severe level. Exit codes:
0 passed, 1 quality gate failed, 2 configuration/input/output failure.
Findings are ordered by severity, source, rule, and stable SHA-256-derived ID.
Semantic annotations never create deterministic findings or influence gates.
