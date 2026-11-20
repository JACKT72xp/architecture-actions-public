# Phase 2: deterministic core and packaging

Status: locally validated and closed on 2026-11-20. Phase 3 continuation is recorded in [phase-3.md](phase-3.md).

This checkpoint implements the five native engines, their orchestration, typed
contracts and exact-rational calculator. It is not a finished Marketplace release.
No Git repository, release tag or remote package has been created for this workspace.

## Implemented boundaries

- Python 3.12 minimum, strict Pydantic contracts, Markdown AST parsing through
  markdown-it-py, and bounded native AsciiDoc processing.
- Canonical EN/ES/DE section recognition, mixed-format includes, local links and
  anchors, document metadata, hierarchical headings, and hashed diagram inventory.
- Static section/depth/placeholder/reference/heading/diagram checks.
- Typed ADR alternatives, positive/negative consequences, lifecycle chains and
  independently evidenced section-to-ADR and ADR-to-section edges.
- A bounded, batched Git raw log query: frequency, directed temporal coupling,
  Jaccard similarity, staleness anchored to HEAD, and shallow-clone degradation.
- Explicit claims blocks, controlled dependency sentences, and accepted-ADR
  extraction. Generated provenance cannot be supplied or overridden by input.
- Exact Fraction arithmetic with final round-half-up; independent severity gates.
  Malformed ADR documents and rejected claims blocks contribute explicit deficits,
  rather than silently disappearing from their metric denominators.

The public library entry point is
[analyze_repository](../src/arc42_tqi/analyzer.py). It returns the deterministic
core report and a complete claims contract. Inputs remain confined to the repository.
Network access is not part of core analysis.

## Local execution

Run from this project after installing its dependencies:

    python3.12 -m pip install -e '.[test]'
    arc42-tqi --repo-root tests/fixtures/poor --docs-path docs --adr-path docs/adr

The interim CLI writes:

- .arc42-tqi/tqi-core-report.json
- .arc42-tqi/claims.json
- .arc42-tqi/claims.yaml

The core report intentionally does not masquerade as the final tqi-report.json.
Its scoring, evidence and gate fields match the Phase 1 contract, but the
semantic_enrichment and three-entry prompt_manifest envelopes await Phase 3.
The final report schema is unchanged. The claims contract is already complete.

Exit codes are 0 for a passing gate, 1 for a failing gate, and 2 for invalid
configuration, unsafe paths or execution errors. The source Action manifest
declares the final interface; its GitHub outputs are connected in Phase 3.

## Reproducible distribution

[Dockerfile](../Dockerfile) pins the Python 3.12 slim base by digest.
[requirements-runtime.txt](../requirements-runtime.txt) pins the complete runtime
dependency graph by version and distribution hash. Pydantic v1 uses its portable
wheel; PyYAML builds without LibYAML. No native Python extension is required.
Git is the only external analysis executable; no JVM, Ruby or Node is in the image.

[The release workflow](../.github/workflows/release.yml) is manually dispatched
with a version matching package metadata. It tests, pushes an amd64/arm64 image,
verifies an unauthenticated pull and final capabilities, then creates a release
commit whose Action references the immutable GHCR digest. It does not update the
source branch or overwrite an existing version tag.

The registry namespace comes from the actual GitHub repository. The GHCR package
must be public before its unauthenticated pull check can pass. Phase 2 cannot
pass the final-capabilities release gate, by design. Nothing has been published.

The released digest fixes the executed image. Rebuilding the source Dockerfile
is not claimed to be bit-for-bit reproducible: Debian security packages are
resolved when publishing, and build metadata can differ. The image digest and
hash-locked Python inputs are the consumer reproducibility boundary.

## Validation and remaining work

These commands validated the Phase 2 checkpoint. The current suite now includes
Phase 3 and the CLI writes final artifacts; see [Phase 3](phase-3.md).

Run checks from the project root:

```sh
.venv312/bin/python -m pytest -q
.venv312/bin/python -m ruff check src tests scripts
.venv312/bin/python -m mypy src
.venv312/bin/python -m pip wheel --no-deps --no-build-isolation . --wheel-dir dist
docker build -t arc42-tqi:phase2-validation .
```

Use an installed Python 3.12+ environment if `.venv312` is absent. Container smoke
runs used disposable fixture copies mounted at `/github/workspace`, with
`--network none`; original fixture directories were not used as artifact targets.

Checkpoint results (2026-11-20):

- All 62 tests pass on Python 3.12.12, with no skipped tests or collection errors.
- Ruff passes for source, tests and scripts; strict mypy passes all 15 source files.
- Claims and core-report schema projection validate using local schema references;
  effective configuration is validated through the report's schema reference.
- The migrated mature fixture produces 100/L4 with no findings. Its claims use
  typed verification, parser-owned provenance and reciprocal ADR section links.
- Poor input produces 3.46/L1. Quality-gate failure writes artifacts before exit 1;
  invalid configuration and unsafe output return exit 2.
- Repeated CLI artifacts are byte-identical; YAML/JSON claims are equivalent.
- Rejected ADRs and claim blocks add tested denominator deficits.
- Real temporary Git repositories verify alignment, frequency, directed coupling,
  Jaccard similarity, HEAD-relative staleness, truncated windows, output limits and
  shallow-clone degradation. No repository was initialized in this workspace.
- The project wheel builds successfully.
- Docker builds successfully for local Linux/arm64. Hash-locked dependencies install,
  dependency checks pass, and Pydantic/PyYAML use their pure-Python implementations.
- Offline container runs verify mature/poor gates, unsafe output, and byte-identical
  repeated artifacts. Linux/amd64 and GitHub-hosted CI have not been run locally.
- CI now asserts the Phase 2 core artifacts through the Docker Action. It does not
  assert final GitHub outputs that have not yet been implemented.

The former CLI tests have been migrated to the core interface. Existing legacy
exporter/network-helper tests remain unit checks only; they do not establish final
CLI integration. No tests are skipped to obtain the passing checkpoint.

### Phase 3 handoff

- Assemble final `tqi-report.json` with semantic enrichment and the three-entry
  prompt manifest; validate against the unchanged full report schema.
- Implement bounded modular prompts and self-contained evidence handling.
- Integrate optional semantic enrichment without changing deterministic scoring.
- Wire Action outputs, Step Summary and PR-comment fallback, including permission
  and fork behavior; replace core smoke assertions with final-interface checks.
- Add final-artifact, prompt and GitHub end-to-end tests, including injection-safe
  evidence rendering and reproducibility.
- Finish adoption examples and run the final release-capabilities gate before any
  publication. GHCR publication, multi-platform release validation and Marketplace
  registration have not been performed.

The sub-three-second target applies to analyzer startup, not image pulls, GitHub
provisioning, network enrichment or arbitrarily large repositories. The earlier
approximately 0.14-second small-repository measurement remains a smoke observation,
not a general performance guarantee.
