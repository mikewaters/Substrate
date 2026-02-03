# Agent Instructions

# Product development lifecycle
## Architecture Decisions

When making decisions that meet ANY of these criteria, create an ADR in `adrs/`:
- Choosing between multiple valid technical approaches
- Adopting or rejecting a library/framework
- Establishing patterns that future code should follow
- Decisions someone might later ask "why did we do it this way?"

Use the next sequential number. Keep ADRs concise.
For an example of the output structure, see `adrs/README.md`.

## Development Task management
- This project uses `bd` commands instead of markdown TODOs or other methods of task tracking.
- Only use `bd` when breaking down coding tasks (always use `bd` for coding tasks!), **not** for general reasoning.
- Always create task descriptions in beads, even if they are short.
- When creating tasks using `bd`, always identify any tasks that are parallelizeable using subagents. If two tasks will not touch the same code files, they can probablybe parallelized.
- Always follow the beads SESSION CLOSE PROTOCOL , found in `bd prime` agent instructions.

## Proposals and specifications
Feature, implementation, and architecture proposals are located in `features/`

## Project documentation
- Code and architecture documentation for the entire project resides in `docs/`.
- Individual code modules should contain a `README.md` explaining their usage, as a supplement for docstrings.
- All python classes, methods, functions, and modules must have rigorous but concise docstrings.

---

# Design Instructions

## Breaking changes and backward-compatibility
- This is a pre-alpha product; if you are making a breaking change, THAT IS OK. You only need to adapt to this breaking change within this project.
- NEVER implement migrations or legacy fallbacks, even when instructed to. We should have a single version of schema, database, and business logic until told otherwise.

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

** Test file location**
- unit and integration tests have their own dedicated modeuls in `tests/`
- test files should not mirror the application module structure exactly; group related tests together in test modules in alignment with *product features*, in a way that makes sense to you. For example, if you are testing multiple modules that all relate to "user profiles", you might create a single test module `tests/user_profiles/test_user_profiles.py` that contains tests for all those modules.

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
- Use the `agentlayer.logging` library for logging
- Use dataclasses for internal objects
- Use Pydantic models for input/output objects, to take advantage of serialization and validation

---
