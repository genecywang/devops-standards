# Design

Keep current workflow policy in global templates and OpenSpec; keep setup documents focused on adoption and external documentation. Remove duplicate completed plans rather than migrate their obsolete commands into another active instructions folder. The original bootstrap OpenSpec artifacts remain because the bootstrap script still validates that change.

The Claude installer is currently symlinked from the user skill directory. Deleting it would break discovery. Replace its broad proactive/catalog workflow with explicit installation requests, current source verification, and review of exact destinations. Remove the catalog dependency. Preserve `check-skills.sh` as an executable no-op until any externally configured hook can be removed in a separately authorized settings change; this avoids warnings or missing-command errors.

Retain separate repo-local and consumer config examples: they have distinct documented roles even when their content is similar. Keep review prompts as useful invocation entry points, rather than deleting them merely because they are short.

Validation: strict OpenSpec validation, skill metadata validation, shell syntax and silent hook execution, local Markdown link/reference checks, and diff review. No infrastructure tests or external installation are needed. Actual runtime settings and all credentials remain untouched.
