# Agent Instructions

If you are working on a python project, immediately read `AGENTS_PYTHON.md`.

# Work environment

You may be within a git worktree. Obey the following:

- Always work only inside the current worktree
- Write to .env.local, never .env
- Read .wt.port for dev server port


---

# Product development lifecycle
## Architecture Decisions

When making decisions that meet ANY of these criteria, create an ADR in `docs/adr/`:
- Choosing between multiple valid technical approaches
- Adopting or rejecting a library/framework
- Establishing patterns that future code should follow
- Decisions someone might later ask "why did we do it this way?"

Use the next sequential number. Keep ADRs concise.
For an example of the output structure, see `docs/adr/README.md`.


## Proposals and specifications
Feature, implementation, and architecture proposals are located in `docs/features/`

## Project documentation
- Code and architecture documentation for the entire project resides in `docs/`.
- Individual code modules should contain a `README.md` explaining their usage, as a supplement for docstrings.
- All python classes, methods, functions, and modules must have rigorous but concise docstrings.

---

# Design and Development Guidelines

## Breaking changes and backward-compatibility
- This is a pre-alpha product; if you are making a breaking change, THAT IS OK. You only need to adapt to this breaking change within this project.
- NEVER implement migrations or legacy fallbacks, even when instructed to. We should have a single version of schema, database, and business logic until told otherwise.

## Deprecation
- If a module, file, or symbol is marked using the term DEPRECATED in its docstring, you do not need to update that code poath when making changes. Feel free to read it if you believe it has useful context.

## Modularity
- Source code should be modular, enforcing loose boundaries between domains and concerns.
- Modules must be indpendently usable, testable, and runnable.

## Fitness
- Do not EVER use emoji in source code or source code documentation. Our developers are highly allergic to it.

## Testing
- Unit tests should be organized by library/module/file: `tests/unit/search/test_formatting_somehow.py`
- Integration tests must be organized by use case:
    - `tests/integration/queries/test_vague_queries.py`
    - `tests/integration/ingestion/test_obsidian_vault_with_unicode.py`
    - Create any directories you think you need
- At the library level, integration tests should exercise cross-module functionality all the way down

---

# Project Reference

The Substrate
