# Why

The repository contains completed duplicate implementation plans, an old setup recipe that prescribes blanket global writes and bypass permissions, inconsistent browser configuration examples, and a catalog-driven hook that treats optional skills as missing dependencies. These conflict with the adopted conditional workflow.

# What Changes

- Remove two superseded Superpowers implementation plans; retain the original OpenSpec change and Git history.
- Replace the macOS setup recipe with a short, approval-aware adoption guide.
- Replace inconsistent Playwright config mutation snippets with a scoped reference to maintained upstream setup.
- Remove the static skills catalog. Keep the installed `install-skills` entry point as explicit, task-scoped guidance and its old hook as a silent compatibility shim.
- Update the bootstrap prompt to current task-contract and validation guidance.

# Impact

- Execution/target environment: local standards repository. No infrastructure or runtime permission changes.
- Blast radius: readers of setup docs and sessions loading the existing Claude installer symlink.
- Security risk reduced: remove instructions to enable bypass mode or treat reading a document as approval.
- Compatibility: keep the installer and legacy hook paths; do not alter user settings, plugins, or package installations.
- Rollback: restore the affected tracked files from Git history or Trash; preserve unrelated uncommitted work.
- Out of scope: automatic uninstall, deleting machine-local config, archiving active OpenSpec changes, deployment, and credentials.
