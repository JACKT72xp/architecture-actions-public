# Evidence contracts

Schemas use JSON Schema draft 2020-12. Consumers should check `schema_version`
before ingesting. Phase 1 schemas remain in `design/phase-1/`; current schemas
are in `schemas/`.

## Report

The CLI writes `tqi-report.json`: score, maturity, per-dimension metrics,
effective configuration, quality gate, findings, sections, typed ADRs, reciprocal
traceability edges, Git signals, source SHA-256 inventory, and tool/repository
metadata. Git facts are null when unavailable. Paths are repository-relative;
there is no wall-clock timestamp. Conformance remains `not_evaluated`.

The final report validates against the unchanged Phase 1 report schema, including
`semantic_enrichment` and the three-entry `prompt_manifest`. The library entry point
`analyze_repository` remains offline and returns the core report and claims; the CLI
adds integration envelopes and artifacts. Git hotspot `last_change` and
`last_associated_change` are commit IDs; staleness is measured relative to HEAD time.

Findings include stable IDs, dimension, severity, file, section, rule ID, message,
evidence, remediation, related claim IDs and metric references. Repository-level
findings can have an empty file and null section.

## Claims

`claims.yaml` and `claims.json` contain equivalent complete contracts, including
metadata, applicability, diagram inventory, and all six categories even when empty.
Claims require a unique ID and nonempty `evidence_targets` chosen from `code`,
`cloud`, and `diagrams`. Missing semantic fields are retained for remediation;
incorrect types, unknown fields and author-supplied provenance reject the block.

Completeness requires meaningful values for these fields:

| Category | Fields |
| --- | --- |
| components | name, responsibility, boundaries (list); declared_volatility lists known axes |
| dependencies | source, target, protocol, synchrony, rationale, allowed (boolean) |
| flows | source, target, protocol, synchrony, rationale, interface |
| cloud_resources | provider, service, role, component_id, environment, region, configuration, security |
| volatility_zones | component_id, axis, propagation_risk, encapsulation, impact, mitigation, owner |
| constraints_and_adrs | constraint, adr_id, status, alternatives, consequences, quality_attributes |

Cloud configuration/security are flat scalar mappings. Providers are `aws`, `gcp`,
`azure`, or `other`; synchrony is `sync` or `async`. Component references use claim
IDs. Constraint status must match a valid referenced ADR lifecycle record.
Alternatives contain `name` and `rejection_reason`; consequences contain `positive`
and `negative` lists. Only accepted ADRs generate automatic constraints.

Verification is one typed predicate, not a prose assertion:

````markdown
```arc42-claims
components:
  - id: orders-api
    name: Orders API
    responsibility: Validate submitted orders.
    boundaries: [Public submission interface]
    declared_volatility: []
    evidence_targets: [code]
    verification:
      target: src/orders
      property: imports
      operator: not_contains
      expected: src/worker
      method: dependency_graph
```
````

Methods are `ast`, `dependency_graph`, `iac`, `cloud_inventory`, `diagram_graph`,
and `manual`. Operators are `exists`, `not_exists`, `equals`, `not_equals`,
`contains`, `not_contains`, `subset_of`, `disjoint_from`, and `matches`.
Existence predicates require null expected values; set predicates require nonempty
lists; `matches` requires a valid regular expression. Missing verification loses
atomic-verifiability credit.

The parser generates `provenance: {method, sources}`. Each source contains `file`,
`line`, `end_line`, `section` and `sha256`; section can be null. Methods are
`explicit`, `controlled_language`, or `adr`. Explicit sources span the claims block;
ADR sources identify the originating document. Authors cannot override provenance.

The limited controlled-language grammar is exactly:

```text
`Orders API` must not depend on `Worker` via `Python import` (sync) because deployments are independent.
```

`not` is optional and synchrony may be `async`. Names resolve to explicit component
IDs; unresolved names produce integrity findings. This grammar generates a typed
dependency predicate. Automatically extracted ADR constraints lack verification
unless replaced by an explicit constraint. Arbitrary prose and diagram images do
not become proven assertions.

See the [mature fixture](../tests/fixtures/mature/docs/architecture.md) and
[typed models](../src/arc42_tqi/contracts.py) for complete examples. Duplicate IDs,
YAML aliases, duplicate keys and invalid blocks produce findings and scoring
deficits. Retain schemas, configuration, findings and source evidence together.

## Modular prompts

Exactly three modules target code, cloud and diagrams. Claims participate according
to `evidence_targets`, in stable category/ID order. Each module embeds complete
selected claims, compact scoring/revision context, bounded findings and, for diagram
audits, diagram entries that fit. A claim that exceeds the budget is omitted whole.

`prompt_manifest` records the repository-relative module path, selected IDs, exact
omitted array ranges in `claims.json`, report pointers, and `embedded_chars`.
The character budget applies to the first fenced JSON evidence bundle (including
its trailing newline), not audit instructions or the second fenced manifest.
Omitted ranges include only relevant claims; other audit targets are out of scope.
All report context and diagram inventory remain available through explicit pointers.

Supply referenced artifacts alongside a module to audit omitted material. Without
them, auditors must report incomplete coverage and unverifiable claims. Neither
TQI nor a complete-looking prompt proves implementation conformance. Dynamic fences
protect rendering; auditors are instructed to treat all embedded material as
untrusted data, not executable instructions.

## Semantic observations

The optional adapter emits a complete envelope for disabled, complete, unavailable
or skipped status. Each observation contains `claim_ids`, `source_refs`, `message`
and `kind`; kinds are contradiction, ambiguity, claim_refinement or other. Unknown
claim IDs or source file/hash pairs reject the response. Observations cannot modify
metrics, findings or gates. See [integrations](integrations.md).
