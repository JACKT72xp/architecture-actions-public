# Release checklist

All changes start with a PR to `architecture-actions-public`. The canonical
version is `actions/arc42-tqi/pyproject.toml`; the CLI and integration User-Agent
read installed package metadata. Add reviewed notes under a matching version in
`CHANGELOG.md`. Review scoring and schema versions independently.

1. Pass analyzer tests, lint, types, wheel build, dependency audit, real Docker
   Action smoke tests, and distribution export checks in the upstream PR.
2. Merge through the protected main branch. Export that merged commit's Action
   and `distribution/arc42-tqi/` configuration into the Marketplace repository.
3. Review the generated distribution PR and its CI. Never patch generated files
   independently; correct them in an upstream PR and export again.
4. Run **Prepare Marketplace release** in `arc42-tqi-action` with the matching
   version, such as `v0.1.0`. It validates both architectures, creates a fresh tag,
   and prepares a draft release from the reviewed changelog and provenance.
5. Review and publish the Marketplace release through GitHub's release editor.
   Confirm the unique Action name, agreement, category, public visibility and
   cross-repository usage. Retain the Apache-2.0 license.

See the [complete distribution guide](https://github.com/JACKT72xp/architecture-actions-public/blob/main/distribution/arc42-tqi/DISTRIBUTION.md).
The former monorepo GHCR release workflow is retired; do not create competing
release tags here. Version tags in the distribution are never overwritten.
