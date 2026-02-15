# Python Development

## Build Procedures
**Using `uv`**
- use `uv` for all commands, and never ever use `pip` or `uv pip`
- Add new dependencies: `uv add package-name` (in the specific project directory)
- Add development dependencies: `uv add --dev package-name`
- Never use the `python` binary directly, always use `uv run python <command>`

## Testing Practices

**Test creation**
You will be creating tests for each use case, as well as testing edge cases and invariants.
When defining a new test case, ensure it is documented in the module's test case inventory. A module's test case inventory can  be found at `<module>/tests/TEST_CASES.md`.

## Testing Procedures
**Runningf Testing and linting**
- Run a single test: `uv run pytest tests/path/to/test_file.py::TestClass::test_function -v`
- Run the tests for a module: `uv run pytest --pyargs dotted.path.to.module`

**Differential tests (test only what chnaged)**
We are using a test caching tool ("testmon"), and you should trust it - it is monitoring fiule changes and allowing us to run differential tests for agent speed.
If you believe tests are being skipped by testmon incorrectly, feel free to raise that to Mike.

When testing your changes, **always** run the differential tests instead of a full test suite:
- **Run differential tests for the entire suite** - `make agent-test`
- **Run differential tests for a subset** - `make agent-test TESTPATH=tests/pmd/unit`


## Development Practices

**Python authoring guidelines**
- Use `# type: ignore` when needed
- Use Python loggers for each module instead of `print()` functions
- NEVER Re-define export from existing modules in some other module; if "module.store.something" exports symbol `Thing`, it should *NEVER* be included in another module's `__all__` declaration.

**Python library usage**
- Use the `loguru` library for logging
- Use dataclasses for internal objects
- Use Pydantic models for input/output objects, to take advantage of serialization and validation

**File Organization Guidelines**

- Organize code into proper module directories.
- Python libraries reside in `src/` within the project
- Each module must be independently testable, and so should each include a `tests` directory
- `__init__.py files should not contain functions or classes, unless its required; __init__.py should instead export all externally-used symbols that reside within its module. Stop refactoring code into the init file.

---


