# Runbook

This runbook collects the most common commands for working in this repository.
Use `uv` for Python execution and dependency management.

## Setup

- Install dependencies (project):
  ```bash
  uv sync
  ```
- Add dependency:
  ```bash
  uv add package-name
  ```
- Add dev dependency:
  ```bash
  uv add --dev package-name
  ```

## Testing

- Differential test suite (preferred):
  ```bash
  make agent-test
  ```
- Differential tests for a subset:
  ```bash
  make agent-test TESTPATH=tests/pmd/unit
  ```
- Single test (explicit):
  ```bash
  uv run pytest tests/path/to/test_file.py::TestClass::test_function -v
  ```
- Module tests:
  ```bash
  uv run pytest --pyargs dotted.path.to.module
  ```

## Quality Gates

- Lint/format/type check:
  ```bash
  just check
  ```
- Full test suite:
  ```bash
  just test
  ```

## Documentation Artifacts

- Generate catalog store JSON Schema (docs only):
  ```bash
  uv run --with . scripts/gen-catalog-jsonschema.py
  ```
  Output: `src/catalog/docs/catalog-store-schema.json`

- Generate OpenAPI base spec:
  ```bash
  uv run --with . scripts/gen-openapi-spec.py
  ```
  Outputs:
  - `docs/api/openapi.json`
  - `docs/api/openapi.yaml`

- Add OpenAPI examples:
  ```bash
  uv run --with . scripts/add-openapi-examples.py
  ```

- Full OpenAPI build:
  ```bash
  just openapi
  ```

## Beads Task Management

- Create a task:
  ```bash
  bd create --title="Your task" --type=task --priority=2
  ```
- Start work:
  ```bash
  bd update <id> --status=in_progress
  ```
- Close a task:
  ```bash
  bd close <id>
  ```
- Sync beads state:
  ```bash
  bd sync
  ```

## Release Workflow

- Run checks and tests:
  ```bash
  just check
  just test
  ```
- Push changes:
  ```bash
  git pull --rebase
  bd sync
  git push
  git status
  ```
