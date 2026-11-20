# Contributing

Help us make architectural evidence clearer and learning easier. Explain the
question you are trying to answer, provide a small example, and show how your
change affects the result. Be explicit about uncertainty and limitations.

Each Action lives under `actions/<name>/` and owns its manifest, implementation,
configuration, documentation and tests. Put executable GitHub workflows under the
root `.github/workflows/` directory. Keep release tags and image names scoped to
the Action so one release does not imply that every tool changed.

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
