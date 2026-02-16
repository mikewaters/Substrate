# Requirements - substrate CLI

This document defines preliminary requirements for the Substrate project CLI
surface discussed on 2026-02-16.

---

## Goals

- Provide a project-level CLI that can orchestrate workflows across libraries in
  `src/`, starting with `catalog`.
- Split user-safe and privileged operations into separate commands.
- Establish explicit DX modes: agent-first UX for `substrate`, human-operator UX
  for `substrate-admin`.
- Keep commands scriptable and CI-friendly with stable flags, exit codes, and
  machine-readable output.
- Reuse existing Substrate configuration patterns (`SUBSTRATE_*`,
  `DEFAULT_CONFIG_ROOTS`).

---

## Non-Goals

- Not a REPL or interactive shell.
- Not a replacement for direct library APIs in application code.
- Not implementing authorization/identity in v0; command split is the gating
  mechanism.

---

## CLI topology and entrypoints

Two product commands are required:

- `substrate` -> `tool.cli.user:main`
- `substrate-admin` -> `tool.cli.operator:main`

The CLI implementation should live under `tool/cli/` as the project-level
integration layer that delegates into library modules (beginning with
`catalog`).

Confirmed (2026-02-16): `tool/cli/` is the canonical CLI package location for
this work. `app/cli/` is not the target for substrate product CLI routing.

---

## Audience and DX modes (hard requirement)

- `substrate` is agent-first and optimized for agentic DX.
  - `--help` is treated as a primary instruction surface for coding agents.
  - Help text should be explicit and operational: purpose, when to use, when
    not to use, prerequisites, side effects, parameter semantics, output shape,
    and exit behavior.
  - Help format should be stable and highly parseable across releases (predictable section ordering and wording conventions).
- `substrate-admin` is human-operator-first.
  - `--help` should optimize for human readability and operational safety.
  - Admin help should include clear warnings for state-changing operations and
    operator-oriented examples.

Working definition for this spec: "agentic DX" means command surfaces and
documentation designed to maximize reliable execution by non-deterministic
agents, not just human discoverability.

---

## Agentic DX principles (research-informed)

- Command descriptions should be detailed enough for robust tool selection by
  an agent, including explicit "use" and "do not use" guidance.
- Inputs should be schema-like and unambiguous (typed args, constrained values,
  clear defaults), with concrete examples for complex calls.
- Side effects should be explicitly declared in docs/help, including read-only
  vs additive vs destructive behavior, plus idempotency expectations.
- Workflows should remain simple and composable; avoid unnecessary abstraction
  layers that obscure what actually executes.
- Safety model should assume metadata can be misleading; command gating and
  confirmations remain authoritative over prose descriptions.

---

## Privilege model (hard requirement)

- Operator-gated workflows MUST only be exposed under `substrate-admin`.
- Operator-gated includes destructive operations and operational workflows we
  intentionally reserve for admin usage (including eval/metrics in v0).
- Eval and search metrics workflows are permanently operator-gated for this
  product line and MUST remain under `substrate-admin`.
- User-safe operations MUST be exposed under `substrate`.
- `substrate` may include limited document add flows only when they are
  explicitly non-destructive (append-only, no delete/overwrite/reset behavior).
- Any operation that can delete, overwrite, rebuild, or bulk-mutate persisted
  state belongs to `substrate-admin`.
- Destructive operations are supported in interactive mode only.
  - If no interactive TTY is available, destructive commands MUST fail before
    execution.

---

## Preliminary v0 command surface

This is the initial command inventory to guide implementation planning.

### `substrate` (user-safe)

- No operational subcommands in v0.
- v0 scope for `substrate` is the agentic UX contract surface (`--help` and
  `--help-json`) only.
- User-safe runtime commands (for example search or document add) are deferred
  to a later release.

### `substrate-admin` (privileged/destructive)

- `eval golden ...` (v0)
  - Delegate to existing `catalog.cli.eval` command surface.
- `search methods ...` / search metrics workflows (v0)
  - Delegate to existing `catalog.cli.search` commands used to compare retrieval methods.
- Additional admin commands (for example ingest/index) are deferred until
  explicitly approved for scope.

Implementation note (v0): prefer thin imports/delegation from `catalog.cli`
instead of duplicating command logic in `tool/cli`.

---

## Command behavior requirements

- Consistent global options across both binaries where practical (`--output`,
  `--verbose`, etc.).
- Both entrypoints support global log verbosity control via
  `--log-level` (alias: `--debug-level`) with accepted values
  `DEBUG|INFO|WARNING|ERROR|CRITICAL`.
- Default log levels:
  - `substrate`: `CRITICAL` (default-hidden logging posture)
  - `substrate-admin`: `INFO`
- Human-readable output by default.
- Structured output for automation where appropriate (`--output json` at
  minimum for search/eval style commands).
- Stable non-zero exit behavior for command errors.
- `substrate` MUST support `--help-json` in v0 for machine-oriented help
  consumption.
- `substrate --help` requirements (agentic DX):
  - Include explicit "when to use / when not to use" guidance.
  - Include side-effect classification (read-only, non-destructive write, destructive).
  - Include precise argument semantics and constraints.
  - Include command examples covering common success paths and common failure paths.
  - Include output and exit-code contract notes.
- `substrate-admin --help` requirements (operator DX):
  - Concise human-readable operational guidance.
  - Safety warnings and confirmation expectations for mutating commands.

---

## Exit codes (approved contract)

Global exit code contract for substrate CLI commands:

- `0`: success
- `2`: usage/argument error
- `3`: configuration or precondition error
- `4`: dependency/runtime environment error
- `5`: command execution failed
- `6`: quality threshold regression
- `130`: interrupted (SIGINT)

Notes:

- Not all commands are required to use every non-zero code.
- Command help MUST document which subset of codes a command can emit.

---

## `substrate --help` contract (agent-first, v0)

This contract applies to every `substrate` command and subcommand help page.

### Section order (required)

Each help page MUST present these sections in this exact order:

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

### Required semantics by section

- `NAME`
  - Fully qualified command path (for example `substrate search query`).
- `SUMMARY`
  - One sentence describing the command's primary outcome.
- `WHEN TO USE`
  - Concrete trigger conditions and intended workflows.
- `WHEN NOT TO USE`
  - Explicit anti-patterns and safer alternative commands.
- `SAFETY`
  - Side-effect class: `read-only`, `non-destructive-write`, or `destructive`.
  - Idempotency statement (`idempotent` or `not-idempotent`).
  - Any confirmation requirements.
- `PRECONDITIONS`
  - Required environment, files, services, or state assumptions.
- `USAGE`
  - Canonical invocation syntax with placeholders.
- `ARGUMENTS`
  - Positional inputs with type, required/optional, constraints, and default (if any).
- `OPTIONS`
  - Flags with type, accepted values, defaults, and behavioral impact.
- `OUTPUT`
  - Output channels (`stdout`/`stderr`) and structured output schema notes for
    machine-readable modes.
- `EXIT CODES`
  - Enumerated code table (at minimum `0` and non-zero error classes used by the command).
- `EXAMPLES`
  - At least:
    - one minimal success example
    - one realistic example with multiple options
    - one failure example with expected error condition
- `SEE ALSO`
  - Related commands and the reason to switch to each.

### Canonical template

```text
NAME
  substrate <group> <command>

SUMMARY
  <one sentence primary outcome>

WHEN TO USE
  - <condition 1>
  - <condition 2>

WHEN NOT TO USE
  - <anti-pattern 1> -> use: substrate <other command>

SAFETY
  side_effect_class: <read-only|non-destructive-write|destructive>
  idempotency: <idempotent|not-idempotent>
  confirmation_required: <yes|no>

PRECONDITIONS
  - <required env/service/state>

USAGE
  substrate <group> <command> <args> [options]

ARGUMENTS
  <arg_name>  <type>  <required|optional>  <constraints>  <default or none>

OPTIONS
  --<flag>  <type>  <accepted values>  <default>  <effect>

OUTPUT
  stdout: <human output summary>
  stderr: <error output summary>
  --output json schema:
    <top-level fields and meanings>

EXIT CODES
  0: success
  <n>: <error class>

EXAMPLES
  # minimal success
  substrate <group> <command> ...

  # realistic
  substrate <group> <command> ... --output json

  # failure mode
  substrate <group> <command> ... --bad-flag
  # expected: <error summary>

SEE ALSO
  substrate <related command>  - <why/when to switch>
```

### Contract validation expectations

- Help output should be snapshot-tested for section presence and order.
- Changes to section names/order should be treated as breaking changes for
  agent workflows.
- This strictness requirement is mandatory (not advisory).

### `--help-json` contract (v0)

`substrate --help-json` (and command-level equivalents) MUST emit a stable JSON
object containing at least:

- `name`
- `summary`
- `when_to_use`
- `when_not_to_use`
- `safety`
- `preconditions`
- `usage`
- `arguments`
- `options`
- `output`
- `exit_codes`
- `examples`
- `see_also`

Field naming and semantic meaning should map 1:1 with the human `--help`
contract sections.

---

## Configuration requirements

- CLI MUST use project settings/env conventions used by `catalog` today.
- Runtime config roots remain driven by `DEFAULT_CONFIG_ROOTS` and
  `SUBSTRATE_ENVIRONMENT`.
- Any command-specific overrides (for example `--config`, `--env`) are deferred
  until command surface is finalized.

---

## Decisions locked (2026-02-16)

- CLI canonical package location: `tool/cli/`.
- `substrate` supports `--help-json` in v0.
- v0 command scope: admin-only operational commands; `substrate` has no runtime
  subcommands in v0.
- Eval/search metrics are permanently admin-only.
- Exit code contract is approved as documented above.
- Destructive commands are interactive-only.
- `substrate --help` section order/names are strict contract elements.
