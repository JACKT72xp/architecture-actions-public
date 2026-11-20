# Security policy

Do not open public issues containing exploitable details or private architecture.
Use GitHub's private vulnerability reporting for this repository when enabled.
If that feature has not been enabled, contact the repository owner privately.

The analyzer treats repository documents as untrusted input. It does not run
preprocessors, execute diagrams, fetch remote links, or evaluate embedded code.
Input paths are confined to the checkout. Size/depth limits bound parsing, and
YAML aliases, duplicate keys, and unsafe tags are rejected. Optional integrations
use bounded HTTPS requests without redirects and never affect deterministic scores.

Generated evidence may contain sensitive design details already present in source
documents. Choose artifact visibility and optional semantic endpoints accordingly.
Prompt-injection instructions in documents remain untrusted data; a prompt cannot
guarantee that a downstream agent enforces the specified read-only behavior.

Only pass integration secrets on trusted events. Do not combine an untrusted PR
checkout with `pull_request_target` permissions. The Docker Action runs its packaged Python CLI; it does not load Python modules
from analyzed documents. CI configuration itself remains part of the caller's
trust boundary.
