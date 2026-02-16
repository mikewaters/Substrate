# Substrate CLI

This package contains the project-level CLI entrypoints:

- `substrate` (`tool.cli.user:main`): agent-first help and instruction surface.
- `substrate-admin` (`tool.cli.operator:main`): human-operator workflows.

v0 behavior:

- `substrate` supports `--help` and `--help-json`.
- `substrate-admin` delegates:
  - `eval ...` to `catalog.cli.eval`
  - `search ...` to `catalog.cli.search`
- Both commands support global verbosity control via
  `--log-level` (alias `--debug-level`).
- Default verbosity differs by command:
  - `substrate`: `CRITICAL` (quiet/default-hidden logging)
  - `substrate-admin`: `INFO`
