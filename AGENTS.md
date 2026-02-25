# Agent Instructions

If you are working on a python project, immediately read `AGENTS_PYTHON.md`.

# Work environment

You may be within a git worktree. Obey the following:

- Always work only inside the current worktree
- Write to .env.local, never .env
- Read .wt.port for dev server port

Note that the application's cache (defined in settings and enviuronment variables) can be stored in different locations,
based on the current "SUBSTRATE_ENVIRONMENT" env var. If this is set, you can find the location of the cache files in
`catalog.core.settings.DEFAULT_CONFIG_ROOTS`.

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

---

## Cursor Cloud specific instructions

### Services overview

| Service | How to run | Port |
|---------|-----------|------|
| Ontology API (FastAPI) | `uv run uvicorn ontologizer.api.app:app --host 0.0.0.0 --port 8000` | 8000 |
| Ontology Browser (React/Vite) | `cd apps/ontology-browser && pnpm dev --host 0.0.0.0 --port 5173` | 5173 |

### Non-obvious caveats

- **`tools/serve.py` references `ontology.api.app:app` but the correct module path is `ontologizer.api.app:app`.** Use uvicorn directly with the correct path as shown above.
- **MLX embedding model (`mlx_embeddings`) only works on Apple Silicon (macOS).** On Linux x86_64, catalog tests that invoke the embedding pipeline (e2e tests, integration ingestion/search tests in `src/catalog/tests/idx/`) will fail with `ImportError: libmlx.so`. Exclude them with `--ignore=src/catalog/tests/e2e --ignore=src/catalog/tests/idx/integration --ignore=src/catalog/tests/idx/unit/pipelines` or `-k "not mlx"`.
- **Sample data seeding:** Run `uv run python -c "import asyncio; from ontologizer.loader.loader import load_yaml_dataset; from ontologizer.relational.database import get_async_session, create_all_tables_async; asyncio.run((lambda: None)() or asyncio.get_event_loop().run_until_complete(create_all_tables_async()) if False else None); exec('async def m():\n await create_all_tables_async()\n async with get_async_session() as s: await load_yaml_dataset(\"src/ontologizer/loader/data\", s)\nasyncio.run(m())')"` or use the loader module directly. The database is SQLite at `.data/ontology.db`.
- **Frontend build scripts:** `esbuild` and `msw` require post-install scripts. The root `package.json` has `pnpm.onlyBuiltDependencies` configured to allow them. Run `pnpm install` from the workspace root (not from `apps/ontology-browser` alone) to ensure they execute.
- **Node.js version:** `.nvmrc` specifies Node 24. Use `nvm use 24` (or install via `nvm install 24`) before frontend commands.
- **Lint/test quick reference:** See `AGENTS_PYTHON.md` for Python commands, `Justfile` for human-facing commands, and `apps/ontology-browser/package.json` scripts for frontend lint/test/build.
