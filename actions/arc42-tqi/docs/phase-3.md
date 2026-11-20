# Phase 3: final reports, modular prompts and integrations

Status: implementation and local validation complete on 2026-11-20.

Phase 2 remains closed. Phase 3 implements the final CLI/Action interface; this
implementation checkpoint preceded publication. It has not been tagged or registered
in GitHub Marketplace. Source publication is documented in the repository README.

## Implemented

- Final `tqi-report.json` with the unchanged Phase 1 schema, including complete
  semantic-enrichment and three-module prompt-manifest envelopes.
- Equivalent JSON/YAML claims, Markdown summary, and code/cloud/diagram audit
  prompts. All artifacts are emitted before a quality-gate failure.
- Deterministic target selection with whole claims, configurable character/count
  budgets, exact omitted array ranges and explicit report/inventory pointers.
  Prompts describe missing evidence and never equate TQI with conformance.
- Optional HTTP JSON enrichment, with structured observations, compatibility for
  legacy string observations, payload/response bounds, reference validation,
  secret redaction and failure envelopes. Deterministic scoring is unchanged.
- GitHub Action outputs, Step Summary and opt-in PR-comment upsert. Permission
  failures preserve artifacts and gate status; fork/non-PR events do not post.
  Repository-context mismatches and exhausted pagination stop posting.
- Random temporary artifact files with atomic per-file replacement, path checks
  and mode 0644 for subsequent runner steps. The artifact set is not a transactional
  directory replacement; an interrupted write can leave an incomplete set.
- Final-interface CI assertions and a reusable offline image smoke script.

The offline `analyze_repository` library interface still returns the core report
and complete claims. The CLI adds export and integration envelopes. It no longer
writes `tqi-core-report.json`; older output files are not automatically deleted.

A contract correction changes Git hotspot `last_change` and
`last_associated_change` from timestamps to the commit IDs required by the frozen
schema. HEAD-relative staleness and all scoring formulas remain unchanged.

## Validation

```sh
.venv312/bin/python -m pytest -q
.venv312/bin/python -m ruff check src tests scripts
.venv312/bin/python -m mypy src
.venv312/bin/python -m pip wheel --no-deps --no-build-isolation . --wheel-dir dist

docker build --platform linux/arm64 -t arc42-tqi:phase3-arm64 .
.venv312/bin/python scripts/smoke_image.py --image arc42-tqi:phase3-arm64 --platform linux/arm64

docker build --platform linux/amd64 -t arc42-tqi:phase3-amd64 .
.venv312/bin/python scripts/smoke_image.py --image arc42-tqi:phase3-amd64 --platform linux/amd64
```

Use any installed Python 3.12+ development environment if `.venv312` is absent.
The image smoke script copies fixtures to disposable directories and runs with
networking disabled. It does not modify fixture sources or contact GitHub.

Local checks on 2026-11-20:

- 77 tests pass with no skips, including complete report/claims schemas,
  reproducibility, all exit codes, real Git history, prompt budgets and omissions,
  injection-safe fences, non-scoring enrichment, rejected responses, secret
  redaction, disabled networking paths, PR permission fallback and artifact paths.
- Ruff and strict mypy pass; the distributable wheel builds successfully.
- Linux/arm64 and Linux/amd64 images build successfully with hash-locked,
  pure-Python dependencies. The amd64 image runs under local emulation.
- Both offline image smoke runs pass: mature input scores 100/L4 and exits 0;
  poor input scores 3.46/L1 and exits 1; unsafe output exits 2. Complete schemas,
  final Action output files, all three prompts, readable permissions and
  byte-identical repeated artifacts are verified.
- CI asserts final Action outputs. The release workflow uses the same smoke script
  for both architectures before tagging; the workflow itself has not been run.

Live semantic services and PR writes are tested through mocks, not production
requests. GitHub-hosted CI, GHCR publication and public unauthenticated pulls still
require running the workflows in an actual repository. The original workspace had no Git repository or remote at this checkpoint.
Source was subsequently packaged under `actions/arc42-tqi/` in
`JACKT72xp/architecture-actions-public`. Release operations remain separate.

## Adoption

See [README](../README.md), [contracts](contracts.md), and
[integrations](integrations.md). Ship `tqi-report.json` and `claims.json` alongside
prompts when omitted evidence is referenced. The embedded-character budget covers
the selected JSON bundle, not instructions or the manifest. Claims for other audit
targets are excluded by scope; relevant claims omitted by budget have exact ranges.

Before publication, follow the [release checklist](releasing.md), verify the
GitHub-hosted Action smoke job and both image architectures, and validate the
immutable public GHCR digest. No release has been created by this work.
