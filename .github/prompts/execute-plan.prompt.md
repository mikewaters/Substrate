---
mode: 'agent'
description: 'Create a new implementation plan file for new features, refactoring existing code or upgrading packages, design, architecture or infrastructure.'
tools: ['changes', 'codebase', 'editFiles', 'extensions', 'fetch', 'openSimpleBrowser', 'problems', 'runTasks', 'search', 'searchResults', 'terminalLastCommand', 'terminalSelection', 'testFailure', 'usages', 'vscodeAPI']
---
# Copilot Command: Execute Plan

**Goal:** Implement a specific story from a feature implementation plan with test-driven development and quality gates.

## Usage

```bash
/execute-plan FEAT-XXX
```

Where:
- First argument: Feature ID (e.g., FEAT-123)

## Process Overview

This command implements a single story from the implementation plan, ensuring:
- All tasks are completed in order
- Tests are written and passing
- Acceptance criteria are verified
- Code quality standards are met

## Detailed Execution Steps

### Step 1: Load Context

Read the following files to understand the story:

```
@docs/features/$1/IMPLEMENTATION_PLAN.md
@docs/features/$1/TRACEABILITY.md
@docs/features/$1/PRD.md
```

Where `$1` is the feature ID (first argument).

### Step 2: Extract Story Details

Locate the story with ID matching `$2` (second argument) in the IMPLEMENTATION_PLAN.md and extract:

1. **Story Title and Goal**: The story's name and objective
2. **All Tasks**: Tasks in format `S#.#.#` (e.g., S1.1.1, S1.1.2)
3. **Acceptance Criteria**: The "Acceptance Criteria" section for this story
4. **Related Requirements**: Cross-reference with TRACEABILITY.md to find:
   - Which PRD requirements this story implements
   - Which entities/endpoints are affected
   - Test coverage expectations

### Step 3: Verify Prerequisites

Before starting, check:
- [ ] Is this Story 1.1? If so, proceed.
- [ ] If not Story 1.1, verify prerequisite stories are complete by checking `docs/features/$1/PROGRESS.md`
- [ ] If prerequisites missing, STOP and inform user which stories must be completed first

### Step 4: Create Todo List

Use TodoWrite to create a comprehensive todo list:

```
1. [Story Goal] - Read this story's description
2. S#.#.1: [First task description]
3. S#.#.2: [Second task description]
...
N-2. Run all tests and verify 90%+ coverage
N-1. Run code quality checks (just check)
N. Verify all acceptance criteria
```

Mark the first item as `in_progress`.

### Step 5: Execute Tasks Sequentially

For each task in the story:

#### 5a. Before Writing Code
- Read relevant existing code first using Read tool
- Understand current structure and patterns
- Check AGENTS.md and CLAUDE.md for project-specific guidelines

#### 5b. Implementation
- Follow the task description exactly
- Use appropriate tools based on task type (see guidelines below)
- Write code following project standards:
  - Use type hints everywhere (including `self` in methods)
  - Use Pydantic for all data models and validation
  - Use proper logging (no `print()` statements)
  - Ensure files end with newline

#### 5c. Write Tests (TDD Approach)
- **CRITICAL**: Write tests as you implement (or before)
- Unit tests for business logic
- Integration tests for multi-component workflows
- Use pytest with proper fixtures
- Target 90%+ coverage for new code
- Place tests in appropriate directory:
  - Unit tests: `[module]/tests/unit/`
  - Integration tests: `[module]/tests/integration/`

#### 5d. Run Tests Immediately
```bash
just test
```
- **If tests fail**: STOP, fix the issue, don't proceed
- **If tests pass**: Mark task as complete, move to next

#### 5e. Update Todo List
- Mark completed task as `completed`
- Mark next task as `in_progress`

### Step 6: Story-Specific Implementation Guidelines

#### Database/Schema Tasks (e.g., Story 1.1)
1. **Configuration** (if applicable):
   - Use Pydantic Settings for configuration
   - Support environment variables
   - Validate configuration on startup

2. **DDL First**:
   - Write PostgreSQL DDL with all constraints
   - Include proper indexes
   - Add CHECK constraints for enums
   - Use UUIDs for primary keys

3. **SQLAlchemy Models**:
   - Use SQLAlchemy 2.x syntax
   - Define relationships with proper cascade rules
   - Add `__repr__` for debugging
   - Use declarative base

4. **Alembic Migrations**:
   - Initialize Alembic if needed: `alembic init migrations`
   - Configure `alembic.ini` and `env.py`
   - Generate migration: `alembic revision --autogenerate -m "description"`
   - Review and edit migration file
   - Test migration: `alembic upgrade head` then `alembic downgrade -1`

5. **Test Utilities**:
   - Create database fixtures in `conftest.py`
   - Implement setup/teardown helpers
   - Use pytest fixtures for database session

6. **Testing**:
   - Test with real PostgreSQL (use docker if needed)
   - Test migrations up and down
   - Test constraints are enforced
   - Test indexes exist

#### Service Layer Tasks (e.g., Stories 1.2-1.6, 1.9)
1. **Pydantic Schemas First**:
   - Create `schemas.py` with:
     - `[Entity]Create` schema (for creation)
     - `[Entity]Update` schema (for updates)
     - `[Entity]Response` schema (for API responses)
   - Use proper validation and field descriptions
   - Use `Optional` for optional fields

2. **Service Implementation**:
   - Create service class in `services/[entity]_service.py`
   - Accept `Session` in `__init__`
   - Implement methods: `create`, `get`, `update`, `delete`, `list`
   - Add business logic validation
   - Raise clear exceptions (e.g., `ValueError`, `NotFoundError`)

3. **Unit Tests**:
   - Mock database with `unittest.mock` or `pytest-mock`
   - Test each service method in isolation
   - Test validation logic
   - Test error cases
   - Target 90%+ coverage

4. **Integration Tests**:
   - Use real database session
   - Test end-to-end workflows
   - Test transaction rollback on errors
   - Test cascade deletes

#### API Tasks (Story 1.7)
1. **FastAPI Structure**:
   - Create router in `api/[entity].py`
   - Use dependency injection for database session
   - Use Pydantic schemas for request/response
   - Add proper HTTP status codes

2. **Authentication**:
   - Implement API key middleware
   - Use FastAPI `Depends` for auth
   - Return 401 for unauthorized requests

3. **Error Handling**:
   - Use FastAPI `HTTPException`
   - Follow problem+json format
   - Include error details in response
   - Log errors appropriately

4. **Testing**:
   - Use FastAPI `TestClient`
   - Test all endpoints (happy path + errors)
   - Test authentication
   - Test pagination if applicable
   - Verify OpenAPI spec generation

#### CLI Tasks (Story 1.8)
1. **Typer Setup**:
   - Create CLI app in `cli/main.py`
   - Use Typer groups for organization
   - Add command functions in `cli/[entity]_commands.py`

2. **Rich Output**:
   - Use Rich tables for list commands
   - Use Rich panels for details
   - Use Rich progress bars for long operations
   - Add colors for status (green=success, red=error)

3. **Confirmation Prompts**:
   - Use `typer.confirm()` for destructive operations
   - Provide `--force` flag to skip confirmation
   - Show what will be deleted/changed

4. **Testing**:
   - Use `CliRunner` from Typer
   - Test command execution
   - Test output format
   - Test error messages

### Step 7: Run Code Quality Checks

After all implementation tasks are complete:

```bash
just check
```

This runs:
- `ruff format` - Format code
- `ruff check . --fix` - Lint and auto-fix
- `basedpyright` - Type checking
- Custom stub checks

**If any fail**: Fix issues before proceeding. Do not mark story complete.

### Step 8: Verify Test Coverage

Run tests with coverage report:

```bash
just test
```

Check that:
- All tests pass ✓
- Coverage ≥90% for new code ✓
- No test files skipped ✓

**If coverage <90%**: Add more tests before proceeding.

### Step 9: Verify Acceptance Criteria

For each acceptance criterion listed in the story:

1. **Identify Verification Method**:
   - Automated test? → Run the test
   - Manual check? → Perform the check
   - Performance test? → Run benchmark

2. **Document Verification**:
   - Note which test verifies the criterion
   - For manual checks, document the result
   - For performance, record the metric

3. **Mark Status**:
   - ✓ Verified by [test name/manual procedure]
   - ✗ Failed - [reason and action needed]

**All criteria must be verified** before marking story complete.

### Step 10: Update Progress Tracking

Update the feature's PROGRESS.md file:

```markdown
## Phase 1 - MVP Backend
- [x] Story 1.1: Database Foundation (2025-10-13) ✓
- [ ] Story 1.2: Taxonomy Service Layer
...
```

Mark the completed story with:
- [x] checkbox
- Story ID and title
- Completion date
- ✓ checkmark

### Step 11: Create Story Completion Summary

Provide a comprehensive summary:

```markdown
## Story [ID]: [Title] - COMPLETE ✓

### Implementation Summary
[Brief description of what was implemented]

### Tasks Completed
- [x] S#.#.1: [Task description]
- [x] S#.#.2: [Task description]
...

### Files Created/Modified
- `path/to/file.py` - [description]
- `path/to/test.py` - [description]
...

### Test Coverage
- Unit tests: X% coverage
- Integration tests: Y scenarios covered
- Performance tests: Z cases (if applicable)
- All tests passing ✓

### Acceptance Criteria Verification
- [x] Criterion 1 - Verified by [test_name or manual procedure]
- [x] Criterion 2 - Verified by [test_name or manual procedure]
...

### Code Quality
- [x] Code formatted (ruff format)
- [x] Linting passed (ruff check)
- [x] Type checking passed (basedpyright)
- [x] No stub violations

### Deviations from Plan
[List any changes from the original plan, with justification]
OR
No deviations - implemented as planned ✓

### Challenges Encountered
[Any issues faced and how they were resolved]
OR
No significant challenges ✓

### Dependencies Added
[List any new dependencies added via `uv add`]
OR
No new dependencies ✓

### Recommendations for Next Story
- Next story: Story [ID]: [Title]
- Prerequisites: [All prerequisites met / Note any concerns]
- Estimated effort: [Your estimate based on this story's experience]

### Commit Recommendation
Suggest running `/commit` with message:
"feat(FEAT-XXX): Complete Story X.X - [Title]"
```

## Important Constraints

### MUST DO
- ✓ Read existing code before modifying
- ✓ Write tests alongside implementation (TDD)
- ✓ Run tests after each task
- ✓ Achieve 90%+ test coverage
- ✓ Run `just check` before completion
- ✓ Verify ALL acceptance criteria
- ✓ Update PROGRESS.md

### MUST NOT DO
- ✗ Skip tests
- ✗ Proceed if tests fail
- ✗ Proceed if `just check` fails
- ✗ Mark story complete with unverified acceptance criteria
- ✗ Manually edit pyproject.toml (use `uv add`)
- ✗ Use `print()` statements (use loggers)
- ✗ Skip type hints

### Dependency Management
When adding dependencies:
```bash
cd src/ontology/domains/taxonomy  # or appropriate directory
uv add package-name              # for runtime dependency
uv add --dev package-name        # for dev dependency
```

**Never** manually edit `pyproject.toml` dependencies section.

### Error Handling Protocol
1. **Tests Fail**:
   - STOP implementation
   - Analyze failure
   - Fix the issue
   - Re-run tests
   - Only proceed when green

2. **Code Quality Fails**:
   - STOP implementation
   - Run specific check: `ruff check` or `basedpyright`
   - Fix issues
   - Re-run `just check`
   - Only proceed when clean

3. **Coverage Below 90%**:
   - STOP implementation
   - Identify uncovered code
   - Add tests for uncovered paths
   - Re-run with coverage
   - Only proceed when ≥90%

4. **Acceptance Criteria Not Met**:
   - STOP before marking complete
   - Re-examine implementation
   - Fix to meet criteria
   - Re-verify
   - Only proceed when all criteria met

## Example Execution

### Input
```bash
/execute-plan FEAT-001 1.1
```

### Process
1. Read IMPLEMENTATION_PLAN.md and find Story 1.1
2. Extract 7 tasks (S1.1.1 through S1.1.7)
3. Create todo list with 10 items (7 tasks + 3 verification steps)
4. Execute S1.1.1: Set up Pydantic settings
   - Create `src/ontology/config/settings.py`
   - Write tests in `src/ontology/config/tests/test_settings.py`
   - Run `just test` → PASS ✓
5. Execute S1.1.2: Create PostgreSQL schema DDL
   - Write DDL in `docs/schema.sql`
   - Create models in `src/ontology/domains/taxonomy/models.py`
   - Run tests → PASS ✓
6. [Continue for remaining tasks...]
7. Run `just check` → PASS ✓
8. Verify 5 acceptance criteria → ALL VERIFIED ✓
9. Update PROGRESS.md
10. Generate completion summary

### Output
```markdown
## Story 1.1: Database Foundation - COMPLETE ✓

### Implementation Summary
Set up PostgreSQL database with schema, SQLAlchemy models, Alembic migrations,
and database connection management. All constraints and indexes implemented.

### Tasks Completed
- [x] S1.1.1: Set up database configuration with Pydantic settings
- [x] S1.1.2: Create PostgreSQL schema DDL with constraints and indexes
- [x] S1.1.3: Implement SQLAlchemy 2.x models
- [x] S1.1.4: Set up database connection and session management
- [x] S1.1.5: Configure Alembic for migrations
- [x] S1.1.6: Create initial migration
- [x] S1.1.7: Write database setup/teardown utilities for testing

### Files Created/Modified
- `src/ontology/config/settings.py` - Database configuration
- `src/ontology/database/connection.py` - Connection management
- `src/ontology/database/session.py` - Session management
- `src/ontology/domains/taxonomy/models.py` - SQLAlchemy models
- `docs/schema.sql` - PostgreSQL DDL
- `alembic.ini` - Alembic configuration
- `src/ontology/database/migrations/versions/001_initial.py` - Initial migration
- Tests in `src/ontology/database/tests/`

### Test Coverage
- Unit tests: 95% coverage
- Integration tests: Database connection, migrations, constraints
- All tests passing ✓

### Acceptance Criteria Verification
- [x] Database schema created with all constraints - Verified by test_constraints
- [x] SQLAlchemy models properly configured - Verified by test_models
- [x] Can create/rollback migrations - Verified by test_migrations
- [x] Connection pooling configured - Verified by test_connection_pool
- [x] Test utilities available - Verified by test_fixtures

### Code Quality
- [x] Code formatted (ruff format)
- [x] Linting passed (ruff check)
- [x] Type checking passed (basedpyright)
- [x] No stub violations

### Deviations from Plan
No deviations - implemented as planned ✓

### Challenges Encountered
No significant challenges ✓

### Dependencies Added
- sqlalchemy>=2.0.0
- alembic>=1.13.0
- psycopg2-binary>=2.9.0

### Recommendations for Next Story
- Next story: Story 1.2: Taxonomy Service Layer
- Prerequisites: All met (Story 1.1 complete)
- Estimated effort: 4-6 hours (similar complexity)

### Commit Recommendation
Suggest running `/commit` with message:
"feat(FEAT-001): Complete Story 1.1 - Database Foundation"
```

## Notes

- This command focuses on **one story at a time** for manageable increments
- **Quality gates are enforced** - tests and checks must pass
- **Test-driven development** is expected throughout
- **Documentation** happens through completion summary
- **Traceability** is maintained via PROGRESS.md updates

## Arguments Reference

- `$1` = Feature ID (e.g., FEAT-001)
- `$2` = Story ID (e.g., 1.1, 1.2, 2.3)

## Related Commands

- `/create-plan [FEAT-ID]` - Create the implementation plan first
- `/commit` - Commit completed story changes
