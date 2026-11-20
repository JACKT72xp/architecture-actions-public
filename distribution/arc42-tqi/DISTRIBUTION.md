# Marketplace distribution

All code, documentation, workflow, and release-policy changes start as pull
requests to [architecture-actions-public](https://github.com/JACKT72xp/architecture-actions-public).
This repository is generated. Do not make independent changes here.

## Canonical structure

```text
architecture-actions-public/
├── actions/arc42-tqi/          # Analyzer, tests, pyproject.toml, CHANGELOG.md
└── distribution/arc42-tqi/     # Exporter, workflows, contribution routing, this guide
             │ reviewed commit exported into
             ▼
arc42-tqi-action/              # Public Marketplace repository
├── action.yml
├── Dockerfile
├── src/
├── .github/workflows/
└── UPSTREAM.json
```

The export combines both directories. README/example links are adapted for the
root Action and historical packaging documents are labelled. `UPSTREAM.json`
records the source commit and hashes of every generated file, including workflows.
CI independently regenerates the expected export from that source commit and
rejects differences or additional tracked files. This is a one-way export, not a
native GitHub fork relationship. The distribution requires no upstream checkout
when consumers run the Action.

## Contributions and versions

1. Open a PR in the main repository. Analyzer changes go in `actions/arc42-tqi/`;
   distribution infrastructure changes go in `distribution/arc42-tqi/`.
2. Pass required CI and resolve review conversations before merging. Main requires
   PRs and passing checks, including for administrators. With one maintainer, the
   required approval count is zero; add required independent approvals when another
   maintainer is available. Contributors cannot merge without repository permissions.
3. Prepare a release PR changing `actions/arc42-tqi/pyproject.toml` and its
   `CHANGELOG.md`. The package metadata supplies the CLI and integration version;
   do not maintain separate version literals. Use patch versions for compatible
   fixes, minor versions for features, and major versions for incompatible stable
   interfaces. During 0.x, document any incompatible minor-release changes.
4. Review schema and scoring compatibility separately. Record score changes and
   update `schema_version`/`scoring_version` when their contracts change; those
   versions are not the package version.
5. After the release PR merges and upstream CI passes, synchronize that full
   commit SHA into this repository. The sync PR is generated distribution output,
   not a second place to propose product changes.

## Synchronize

Run **Sync reviewed upstream source** on the distribution's default branch with
a full source SHA. It verifies membership in upstream `main`, uses that commit's
canonical exporter, opens a sync PR, and dispatches distribution CI on its branch.
Review the generated diff and passing CI before merging. Nothing auto-merges.

Normal code-only syncs use `GITHUB_TOKEN`. Enable Actions PR creation in this
repository's Actions settings. Since workflow-token PRs do not automatically
trigger push/PR CI, the workflow explicitly dispatches validation.

If the export changes `.github/workflows/`, use a fine-grained token stored as
`DISTRIBUTION_SYNC_TOKEN`, scoped only to this distribution repository with Contents,
Pull requests, Actions and Workflows write permissions, or synchronize locally
using your existing maintainer credentials. No new token is needed for local
synchronization. Keep the token out of source control. The workflow fails with
instructions when workflow updates need credentials; it never silently omits them.

Local synchronization (run from the main repository after pulling its latest main):

```sh
SOURCE_SHA=$(git rev-parse HEAD)
git merge-base --is-ancestor "$SOURCE_SHA" origin/main
python3 distribution/arc42-tqi/.github/scripts/sync_upstream.py \
  --source . --ref "$SOURCE_SHA" --destination ../arc42-tqi-action
python3 distribution/arc42-tqi/.github/scripts/sync_upstream.py \
  --source . --ref "$SOURCE_SHA" --destination ../arc42-tqi-action --check
```

Then create a sync branch in the distribution repository, commit the export,
push that branch and open a PR. Never force-push or rewrite an existing release
version. Previously exported files removed upstream are removed during sync.

## First publication and subsequent releases

1. Merge the setup PR upstream and ensure its source commit is publicly available.
2. Export that merged commit into the distribution repository and push the initial
   main branch. Subsequent exports use PRs. Configure branch protection with required
   distribution validation, prevent force pushes/deletion, and enable private
   vulnerability reporting in both repositories.
3. Run **Prepare Marketplace release** on distribution main with a version matching
   `pyproject.toml` and a nonempty, unique `CHANGELOG.md` entry, for example `v0.1.0`.
4. The release workflow gates tagging on provenance, tests, lint, types, wheel build,
   dependency audit, real Action outputs and Linux AMD64/ARM64 smoke tests. It creates
   a new tag and a draft release with reviewed changelog text and source provenance.
5. Review the draft. Accept GitHub's Marketplace Developer Agreement, check the
   unique Action name, select **Publish this Action to the GitHub Marketplace**,
   choose a category, then publish. These UI/legal steps remain with the owner.
6. Verify the listing and run the documented Action from another repository.

The old monorepo GHCR publication workflow is retired. Marketplace releases live
only here. No automatic moving `v0`/`v1` tags are created. Version tags are never
reused; rollback means selecting a previous SHA or publishing a new fixed version.

This Docker Action builds its root Dockerfile on a Linux runner. Builds need
network access to base-image/package repositories; normal analysis is offline.
Consumers need no GHCR login, LLM credentials, or source-monorepo checkout:

```yaml
- uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803
- uses: JACKT72xp/arc42-tqi-action@FULL_DISTRIBUTION_COMMIT_SHA
  with:
    docs-path: docs
    adr-path: docs/adr
```

[GitHub Marketplace publication requirements](https://docs.github.com/en/actions/how-tos/create-and-publish-actions/publish-in-github-marketplace).
