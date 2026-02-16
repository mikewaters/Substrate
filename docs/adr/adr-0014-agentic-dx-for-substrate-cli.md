# ADR-0014: Agentic DX Standard for `substrate` CLI

**Status:** Accepted
**Date:** 2026-02-16

## Context

Substrate is introducing two CLI entrypoints with different audiences:

- `substrate` for user-safe workflows
- `substrate-admin` for operator-gated workflows

The `substrate` command is intended to be used heavily by coding agents.
Default CLI help output is optimized for humans, but agent reliability requires
stronger guarantees:

- stable and parseable instruction structure,
- explicit safety and side-effect semantics,
- deterministic argument/output contracts,
- and predictable error behavior.

Without a formal standard, command behavior drifts over time and agents become
less reliable across versions.

## Decision

Adopt an explicit agentic DX standard for `substrate` (not `substrate-admin`).
The standard is normative and implementation-facing.

### 1. Audience split is intentional

- `substrate`: agent-first documentation and command UX.
- `substrate-admin`: human-operator-first UX.

### 2. `--help` is a primary instruction interface for agents

Every `substrate` command help page must follow a fixed section contract:

1. `NAME`
2. `SUMMARY`
3. `WHEN TO USE`
4. `WHEN NOT TO USE`
5. `SAFETY`
6. `PRECONDITIONS`
7. `USAGE`
8. `ARGUMENTS`
9. `OPTIONS`
10. `OUTPUT`
11. `EXIT CODES`
12. `EXAMPLES`
13. `SEE ALSO`

Each section must include required semantic content (for example side-effect
class, idempotency, constraints, and error/exit behavior), as defined in
`docs/features/substrate_cli.md`.

### 3. Safety semantics are explicit and machine-actionable

`substrate` command docs/help must classify side effects using a constrained
taxonomy:

- `read-only`
- `non-destructive-write`
- `destructive`

Idempotency (`idempotent` vs `not-idempotent`) must be stated for each command.
If confirmation is required, help output must say so explicitly.

### 4. Contract stability over convenience

For `substrate`:

- section names/order in `--help` are stable contract elements,
- breaking section/schema changes are treated as breaking changes for agents,
- output schema changes in structured modes must be documented.
- strict section-name/order compatibility is mandatory.

### 5. Validation is required

The project should enforce this with tests:

- snapshot tests for `--help` section presence and order,
- tests for safety metadata presence,
- tests for structured output field presence for commands that support
  `--output json`.

### 6. Evolution policy

- Additive help improvements are encouraged.
- Renames/removals/reordering of contract sections require explicit review as
  breaking agent-facing changes.
- `--help-json` is required in v0 for `substrate` as the machine-oriented help
  mode, and does not replace human-readable `--help`.

## Consequences

- Agent command selection and execution should become more reliable.
- Review quality improves because safety and side effects are explicit.
- CLI maintainers incur additional documentation and test discipline overhead.
- Some UX choices that are fine for humans alone are disallowed for `substrate`
  if they weaken agent reliability.
