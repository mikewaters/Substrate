# Agent Instructions

# Product development lifecycle
## Architecture Decisions

When making decisions that meet ANY of these criteria, create an ADR in `docs/adr/`:
- Choosing between multiple valid technical approaches
- Adopting or rejecting a library/framework
- Establishing patterns that future code should follow
- Decisions someone might later ask "why did we do it this way?"

Use the next sequential number. Keep ADRs concise.
For an example of the output structure, see `docs/adr/README.md`.

## Task management
- This project uses `bd` commands instead of markdown TODOs or other methods of task tracking.
- Only use `bd` when breaking down coding tasks (always use `bd` for coding tasks!), **not** for general reasoning.
- Always create task descriptions in beads, even if they are short.
- When creating tasks using `bd`, always identify any tasks that are parallelizeable using subagents. If two tasks will not touch the same code files, they can probablybe parallelized.
- Always follow the beads SESSION CLOSE PROTOCOL , found in `bd prime` agent instructions.

## Proposals and specifications
Feature, implementation, and architecture proposals are located in `docs/features/`

## Project documentation
- Code and architecture documentation for the entire project resides in `docs/`.
- Individual code modules should contain a `README.md` explaining their usage, as a supplement for docstrings.
- All python classes, methods, functions, and modules must have rigorous but concise docstrings.

---

# Design Instructions

## Breaking changes and backward-compatibility
- This is a pre-alpha product; if you are making a breaking change, THAT IS OK. You only need to adapt to this breaking change within this project.
- NEVER implement migrations or legacy fallbacks, even when instructed to. We should have a single version of schema, database, and business logic until told otherwise.

## Deprecation
- If a module, file, or symbol is marked using the term DEPRECATED in its docstring, you do not need to update that code poath when making changes. Feel free to read it if you believe it has useful context.
---

# Python Development
## Build, Test, and Standards
**Using `uv`**
- use `uv` for all commands, and never ever use `pip` or `uv pip`
- Add new dependencies: `uv add package-name` (in the specific project directory)
- Add development dependencies: `uv add --dev package-name`
- Never use the `python` binary directly, always use `uv run python <command>`

**Testing and linting**
- Run a single test: `uv run pytest tests/path/to/test_file.py::TestClass::test_function -v`
- Run the tests for a module: `uv run pytest --pyargs dotted.path.to.module`

**Differential tests (test only what chnaged)**
We are using a test caching tool ("testmon"), and you should trust it - it is monitoring fiule changes and allowing us to run differential tests for agent speed.
If you believe tests are being skipped by testmon incorrectly, feel free to raise that to Mike.

When testing your changes, **always** run the differential tests instead of a full test suite:
- **Run differential tests for the entire suite** - `make agent-test`
- **Run differential tests for a subset** - `make agent-test TESTPATH=tests/pmd/unit`
**Python authoring guidelines**
- Use `# type: ignore` when needed
- Use Python loggers for each module instead of `print()` functions
- NEVER Re-define export from existing modules in some other module; if "pmd.store.something" exports symbol `Thing`, it should *NEVER* be included in another module's `__all__` declaration.

**Python library usage**
- Use the `loguru` library for logging
- Use dataclasses for internal objects
- Use Pydantic models for input/output objects, to take advantage of serialization and validation
---

# Typescript/javascript development

---

# Release
- Run all checks: `just check` (runs lint, format, type check)
- Run all tests: `just test`

# Project structure

## File Organization Guidelines

- Organize code into proper module directories.
- Python libraries reside in `src/` within the project
- Each module must be independently testable, and so should each include a `tests` directory
- `__init__.py files should not contain functions or classes, unless its required; __init__.py should instead export all externally-used symbols that reside within its module. Stop refactoring code into the init file.

## Project Notes
- This is a LinkML-based ontology project using TerminusDB for graph database storage
- Schema definitions in `src/ontology/domains/schema/`
- Main module: `ontology` (located in `src/ontology/`)

## Technology Requirements

- Use Pydantic for defining i/o schema and command payloads
- Use `attrs` dataclasses for domain models - do *not* use pydantic for domain models
- Use `advanced-alchemy` for relational database interactions.
- Use PydanticAI for LLM interactions
- Use SQLIte for databases, feel free to suggest extensions
- Use FastAPI for HTTP and websocket APIs
- Pytest for testing
- Do not EVER use emoji in source code or source code documentation. Our developers are highly allergic to it.

## Testing

- Emphasis on unit tests in each module and submodule
- If a module has sub-modules, it should include integration tests for cross-module functionality
- At the library level, integration tests should exercise cross-module functionality all the way down

## Modularity

- Python code should be modular, enforcing loose boundaries between domains and concerns.
- Python modules must be indpendently usable, testable, and runnable.

## Domain Design

**Application layers:**
1. Layer 1 - input/output, via API or CLI
2. Layer 2 - service layer, commands and queries
3. Layer 3 - repositories, for negotiating database access
4. Layer 4 - database, for abstracting data infrastructure concerns

**Data objects:**
1. Layer 1 - uses Pydantic models for input and output validation and serialization
2. Layer 2 - transforms Pydantic models into domain models (writes/commands, reads/queries) or ORM models (optionally, reads/queries only) and executes business logic using the lower layers
3. Layer 3 - transforms domain models into ORM models and performs data logic using the lower layer
4. layer 4 - receives ORM models and makes database calls

## Module Structure for src/ontology

- **api/** - should only contain external API concerns
- **cli/** - should only contain external CLI concerns
- **database/**
  - **all** sqlalchemy models should be defined here.
  - all database-specific interactions should be defined here; no other modules should know about database infrastructure or technoogy
- **domain/** - contains only LinkML schema and utilities for interacting with linkML
- **graph/** - only graph database-related utilities should go here
- **loader/** - only utilities for serializeing external data should go here
- **models/**
  - all domain models are deifned here, and only the `attrs` dataclasses should be used.
  - this module contains all domain-level invariants and implementation
- **repositories/** - this is responsible for encapsulating database write logic; it should receive only domain objects (`attrs` dataclasses) and emit SQLAlchemy models. It should never use Pydantic models.
- **schema/** - all pydantic models are defined here. remember, pydantic is only used for input and output, it is not used for domain models
- **services/** - business logic is executed here, both for commands and for queries. Commands ingest pydantic models, and make calls to the repository layer using domain (`attrs`) models. Queries ingest pydantic models, and can call either the repository layer or the orm itself.

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
