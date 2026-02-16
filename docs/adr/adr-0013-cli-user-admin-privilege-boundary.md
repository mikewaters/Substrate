# ADR-0013: Split Substrate CLI into User and Admin Commands

**Status:** Accepted
**Date:** 2026-02-16

## Context

Substrate needs a project-level CLI that can orchestrate workflows across
libraries in `src/`, starting with `catalog`.

Some operations are read-only or low-risk (for example search), while others
are destructive or high-impact (for example ingestion, index rebuild/reset).
The CLI surface should make this boundary explicit and hard to misuse in day to
day workflows.

## Decision

- Provide two CLI binaries:
  - `substrate` mapped to `tool.cli.user:main`
  - `substrate-admin` mapped to `tool.cli.operator:main`
- Use `tool/cli/` as the canonical CLI package location for these entrypoints.
- Restrict destructive or privileged operations to `substrate-admin`.
- In phase 0, treat evaluation/search-metrics workflows as operator-gated and
  expose them via `substrate-admin` by delegating to existing `catalog.cli`
  commands.
- Eval/search-metrics workflows remain admin-only long-term.
- Treat UX goals as distinct by command:
  - `substrate` is agent-first, with detailed `--help` designed for reliable
    agent operation.
  - `substrate-admin` is human-operator-first, with concise operational
    guidance and safety framing.
- v0 operational scope is admin-only; `substrate` ships with agentic help
  surfaces and no runtime subcommands in v0.
- Destructive operations are interactive-mode only and must fail when no TTY is
  present.
- Adopt a shared CLI exit code taxonomy:
  - `0` success
  - `2` usage/argument error
  - `3` configuration/precondition error
  - `4` dependency/runtime environment error
  - `5` command execution failed
  - `6` quality threshold regression
  - `130` interrupted
- Use the project-level CLI layer to delegate into library modules, beginning
  with `catalog`.

## Consequences

- Safer default UX: common usage paths do not expose destructive commands.
- Clearer command ownership and review expectations for new CLI features.
- Documentation standards diverge intentionally: richer and more structured for
  `substrate`, more concise and operator-oriented for `substrate-admin`.
- v0 release sequencing is simplified to admin evaluation/metrics first, at the
  cost of no end-user runtime commands in the initial `substrate` release.
- Slightly higher implementation overhead remains because command groups are
  split across two entrypoints and must stay coherent.
