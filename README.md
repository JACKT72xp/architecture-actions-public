# Architecture Actions

Built for the love of software architecture and continuous learning.

Architecture improves when we make decisions explicit, examine the evidence, and
stay willing to revise what we believe. This repository turns that habit into
small, reusable GitHub Actions: tools that help teams ask better questions about
their systems and learn from the answers.

A score starts a conversation. It cannot replace judgment, prove that a design is
correct, or certify that the implementation matches the documentation. Use these
actions to make gaps visible, support thoughtful reviews, and keep learning as a
system evolves. Fork them, challenge their assumptions, and share what you learn.

## Actions

| Action | Location | Status |
| --- | --- | --- |
| arc42 Technical Quality Index | [`actions/arc42-tqi`](actions/arc42-tqi/) | Implemented; deterministic documentation scoring, claims and audit prompts |
| Volatility analysis | Reserved for a future independent Action | Planned; no standalone Action is available yet |

The arc42 Action already measures documented volatility as one scoring dimension.
The planned volatility Action will have its own scope, implementation and release;
this repository does not present it as finished.

Each Action owns its manifest, dependencies, tests, examples and documentation.
Shared CI and release workflows live in `.github/workflows/`. Keeping Actions in
subdirectories lets them evolve independently in the same repository.

## Use the arc42 Action in your project

Create `.github/workflows/architecture-quality.yml` in the repository you want to
assess. Use a full, reviewed commit SHA from this repository in place of
`COMMIT_SHA`; keep the `/actions/arc42-tqi` subdirectory in the reference.

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
      - uses: actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f
        if: always()
        with:
          name: architecture-evidence
          path: .arc42-tqi/
          include-hidden-files: true
```

Get the current main-branch commit with:

```sh
git ls-remote https://github.com/JACKT72xp/architecture-actions-public.git refs/heads/main
```

Review that commit and its CI results, then paste the full SHA into the workflow.
This is a Docker Action and requires a Linux runner. The source manifest builds
its Dockerfile; using it does not require a published GHCR image, an LLM key, or
cloud credentials. Documentation paths refer to **your checked-out project**, not
the Action's subdirectory.

Start with the default non-blocking configuration, inspect the results, and agree
on useful standards with your team. When ready, add `min-tqi: '70'` and/or
`fail-on-severity: high`. A failing quality gate still writes the artifacts before
returning exit code 1. Configuration or execution errors return exit code 2.

Artifacts include `tqi-report.json`, equivalent `claims.json`/`claims.yaml`,
`summary.md`, and three bounded prompts for code, cloud and diagram audits.
Supply the referenced JSON artifacts with prompts when evidence is omitted by
budget. The prompts request an audit; they do not run one automatically.

See the [Action README](actions/arc42-tqi/README.md) for all inputs and outputs,
[scoring rules](actions/arc42-tqi/docs/scoring.md),
[claim conventions](actions/arc42-tqi/docs/contracts.md), and
[optional integrations](actions/arc42-tqi/docs/integrations.md).

## Fork it and make it yours

1. Select **Fork** on GitHub and create a copy under your account or organization.
2. Clone your fork and keep this repository as an upstream remote:

   ```sh
   git clone https://github.com/YOUR-OWNER/architecture-actions-public.git
   cd architecture-actions-public
   git remote add upstream https://github.com/JACKT72xp/architecture-actions-public.git
   ```

3. Open the fork's **Actions** tab and enable workflows if GitHub asks. Run CI on
   your changes. Normal analysis needs no secrets; publishing images and releases
   is a separate, manually dispatched workflow.
4. In consuming projects, use your fork's owner, repository name, subdirectory and
   reviewed commit SHA:

   ```yaml
   - uses: YOUR-OWNER/architecture-actions-public/actions/arc42-tqi@YOUR_FULL_COMMIT_SHA
     with:
       docs-path: docs
       adr-path: docs/adr
   ```

5. Keep upstream improvements available with `git fetch upstream`. Review and merge
   the changes you want into your own branch, rerun CI, and update consuming
   projects to the new tested SHA.

If you rename your fork, replace the repository name in consumer references too.
The release workflow derives image coordinates from the fork's actual owner and
repository, so it does not publish to the upstream owner's package namespace.
Retain the Apache-2.0 license and applicable attribution when redistributing.

### Bring the Action into an existing repository

You can also copy the complete `actions/arc42-tqi/` directory into your repository,
preserving its license. Check out your project before using the local Action:

```yaml
- uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803
- uses: ./actions/arc42-tqi
  with:
    docs-path: docs
    adr-path: docs/adr
```

The complete directory is required: copying only `action.yml` leaves out its
Dockerfile and implementation. GitHub workflows must remain under the repository
root's `.github/workflows/`; nested workflow directories are not activated.

## Develop and contribute

```sh
cd actions/arc42-tqi
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests scripts
.venv/bin/python -m mypy src
```

See [contribution guidance](CONTRIBUTING.md) and the
[Phase 3 checkpoint](actions/arc42-tqi/docs/phase-3.md). Contributions should explain
the architectural question, show the evidence behind a change, and make limitations
visible. Reports of confusing results are useful contributions too.

## Releases

Source publication and a versioned release are separate steps. No version tag,
public image or Marketplace listing is implied by this README.

All contributions, including release infrastructure, are reviewed through PRs in
this repository. Analyzer sources live in `actions/arc42-tqi/`; canonical
Marketplace infrastructure lives in `distribution/arc42-tqi/`.

After a release PR updates `pyproject.toml` and `CHANGELOG.md` and passes CI, its
merged commit is exported to [arc42-tqi-action](https://github.com/JACKT72xp/arc42-tqi-action).
The distribution creates version tags such as `v0.1.0` and draft Marketplace
releases after its own checks pass. The previous monorepo GHCR release workflow
is retired. No Marketplace listing is implied until the owner publishes it.

Follow the [distribution guide](distribution/arc42-tqi/DISTRIBUTION.md) for
synchronization, versioning, required PR checks, and Marketplace publication.

Apache-2.0 licensed. Built to be understood, adapted, and improved together.
