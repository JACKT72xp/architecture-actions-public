# Release checklist

1. Run unit/integration/security tests, type checks, lint, wheel build, and the
   real Docker Action smoke workflow on GitHub's Linux runner. Run
   `scripts/smoke_image.py` against both Linux/amd64 and Linux/arm64 images;
   see [Phase 3 validation](phase-3.md) for the commands.
2. Verify dependency distribution hashes and all pinned external Action SHAs.
   Test supported Linux/macOS architectures when updating runtime dependencies.
3. Review the scoring version, JSON Schemas, defaults, and compatibility notes.
   Record intentional score changes in the release notes.
4. Enable private vulnerability reporting and add repository ownership/support
   details before advertising public production support.
5. Use the repository/subdirectory reference from the root README and replace
   `COMMIT_SHA` with a tested full commit. Forks must use their own coordinates.
6. After maintainer authorization, dispatch the root release workflow with the
   package version (for example `v0.1.0`). It creates `arc42-tqi/v0.1.0` and pins
   this Action to `ghcr.io/OWNER/REPOSITORY-arc42-tqi@sha256:...`. Then select
   GitHub Marketplace publication, and verify name, branding, license, inputs,
   outputs, documentation, and runner requirements.
7. Recommend immutable commit references to callers. Update any convenience major
   tag only through the maintainer's release process.

Building this project does not publish a repository, push code, create a release,
or register a Marketplace listing automatically.
