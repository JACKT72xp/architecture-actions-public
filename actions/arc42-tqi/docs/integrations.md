# Optional integrations

## Provider-neutral semantic adapter

Set `llm-provider: http-json`, `llm-model`, and an HTTPS `llm-endpoint`. The endpoint
must be a service you explicitly authorize to receive architecture evidence. An
optional bearer token comes from the Action secret input or CLI environment
`ARC42_TQI_LLM_API_KEY`. This is an adapter protocol, not a direct vendor API;
deploy or supply a bridge for the chosen BYO model provider.

Request: HTTP POST JSON with `model`, `instruction`, and
`evidence: {report, claims}`. The request has a 1 MiB cap and a 30-second timeout.
Redirects are rejected rather than forwarding the bearer token elsewhere.

Response:

```json
{"observations": [{"claim_ids": ["orders-queue"], "source_refs": [], "message": "Verify production account scope.", "kind": "ambiguity"}]}
```

The response must contain at most 100 observations, each with a nonempty message
of at most 4,000 characters; total response size is limited to 1 MiB. Kinds are `contradiction`, `ambiguity`, `claim_refinement` or `other`.
Source references use the generated provenance format and must match known file/hash
pairs; claim IDs must exist. Legacy string observations are converted to `other`
with empty references. No tools or model-generated code are executed. Raw request/response bodies and tokens are never logged.
Returned tokens matching the supplied credential are redacted defensively.
Responses enrich only `semantic_enrichment`; all deterministic fields and gate
decisions are computed before the call and cannot be overwritten by the response.

## PR summary

Comments are opt-in and use GitHub's REST issue-comment API. The bot marker is
`<!-- arc42-tqi-action -->`; existing comments authored by `github-actions[bot]`
with that marker are updated. At most ten pages of comments are inspected.
Fork pull requests and non-`pull_request` events are skipped. Missing tokens,
permission failures, or network failures do not fail the quality evaluation.
Use the workflow-provided GitHub token, not a personal token with broad scopes.


The Step Summary and local `summary.md` are written before the PR API is attempted.
Comment status is reported on stderr; a rejected API request preserves the score,
artifacts and gate exit code. Repository context mismatches and exhausted comment
pagination stop posting. CLI comments use `--comment-pr` or
`ARC42_TQI_COMMENT_PR=true`; `false` leaves comments disabled. Set
`ARC42_TQI_GITHUB_TOKEN` only for requested comments.
