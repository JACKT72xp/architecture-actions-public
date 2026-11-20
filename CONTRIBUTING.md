# Contributing

Help us make architectural evidence clearer and learning easier. Explain the
question you are trying to answer, provide a small example, and show how your
change affects the result. Be explicit about uncertainty and limitations.

Each Action lives under `actions/<name>/` and owns its manifest, implementation,
configuration, documentation and tests. Put executable GitHub workflows under the
root `.github/workflows/` directory. Distribution workflow templates belong under
`distribution/<name>/`; they become executable only when exported to the dedicated
Marketplace repository. All infrastructure changes also require a PR here.

Main requires pull requests, passing CI and resolved review conversations. Do not
push directly to main. With one maintainer, no independent approval is required;
add an approval requirement when a second maintainer is available. Release PRs
update `pyproject.toml` and `CHANGELOG.md` together. See the
[release process](distribution/arc42-tqi/DISTRIBUTION.md).

For arc42 TQI, follow its [development guidance](actions/arc42-tqi/CONTRIBUTING.md).
Run checks from `actions/arc42-tqi/`. Changes to scoring require updated scoring
specifications, versioning decisions and regression coverage. Keep the default
analyzer offline and never mix optional semantic observations into its score.

The standalone volatility Action is planned. Discuss its inputs, outputs and
architectural purpose before adding an implementation; do not advertise placeholder
manifests as working Actions.

Write new code comments and documentation in English. Never commit credentials,
private architecture documents, generated reports, local environments or caches.
Preserve licensing and credit when adapting existing work.
