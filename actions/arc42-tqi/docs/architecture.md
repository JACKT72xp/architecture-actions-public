# Implementation architecture

The pipeline is `validated config → document graph → ADRs → claims → Git signals →
rule metrics → scoring → quality gates → optional enrichment → artifacts/summary`.
All file-reading modules receive an explicit repository root. Network code lives
only in the optional integrations module, after deterministic scoring.

## ADR-001: Deterministic ratios, not semantic grades

Status: accepted. Context: TQI must be comparable, auditable, and usable offline.
Decision: measure explicit evidence predicates with visible numerator/denominator
ratios; keep LLM output separate. Alternative: holistic model grading was rejected
because provider/model changes make scores unstable. Consequence: syntactically
complete but shallow documentation can score highly; implementation audits remain
necessary. Quality attributes: reproducibility, explainability, portability.

## ADR-002: Explicit claims and bounded parsing

Status: accepted. Context: arbitrary prose and diagrams cannot reliably produce
atomic machine-checkable assertions without inference. Decision: prefer typed
`arc42-claims` blocks, plus a narrow controlled-language dependency grammar and
accepted ADR extraction. Full documentation renderers and diagram execution were
rejected because of dependency weight and untrusted-code risks. Consequence:
unsupported syntax is reported, and visual evidence needs a downstream auditor.
Quality attributes: safety, maintainability, extensibility.

## ADR-003: Docker Action with a digest-pinned runtime

Status: accepted. Context: the Action needs the same Python 3.12 runtime and native
Git executable across consumers. Decision: build a Docker image with a digest-pinned
Python base and hash-locked pure-Python dependencies. Releases reference an immutable
GHCR digest. This supersedes the earlier composite-Action draft. Consequence: the
Action requires Linux; source builds resolve Debian security packages at build time
and are not claimed to be byte-identical. The released digest fixes the consumer
runtime. Quality attributes: reproducibility, portability, supply-chain transparency.

## Fitness functions

- L1 and L4 fixtures constrain intended score ranges.
- Tests validate numerator bounds, N/A treatment, weight overrides, maturity edges,
  gate precedence, and absence of LLM score influence.
- Schema checks enforce report/claims compatibility and YAML/JSON equivalence.
- Security tests reject traversal, symlinks, alias expansion, malformed claims,
  and unsafe artifact targets.
- End-to-end tests require byte-identical deterministic artifacts and complete
  self-contained evidence in all three prompts.
- Git tests distinguish related decision updates from unrelated churn.

## Reference patterns

docToolchain informs the section/include graph; static linters inform offline
layer-zero findings; log4brains informs ADR entities and relationships; CodeScene
informs bounded evolution/hotspot signals; ArchUnit informs explicit verifiable
assertions. Parnas information hiding and Löwy volatility-oriented decomposition
inform classified change axes and encapsulation/mitigation fields. These are design
influences, not affiliations, runtime dependencies, or claims of feature equivalence.
