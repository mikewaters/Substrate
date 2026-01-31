# Todo list
### Document test data approaches
Ask the agent to tell me the various wonderful ways the test suite is using sqlite

### Support an Abstract Taxonomy, so the polyhierarchy data structure can be reused in new tables and domains
### Make topic aliases into first-class citizens
These should point to tpics? Or not? I am not enforcing this anywhere; if a new topic is saved that matches an existing topic's alias, this is allowed/

### Try Dependency Injection
### Support "parenting" of new topics
FEAT-007
### Create use case tests
A new type of test case, the use case test, should be written **before** the agent starts coding. Unit tests can come to cover detailed implementation testing, but maybe its better to define the test cases themselves (like the function names) in advance at least.
### Review FastAPI AdvancedAlchemy integration
1. Ensure we are using their deps
https://docs.advanced-alchemy.litestar.dev/latest/usage/frameworks/fastapi.html
2. Ensure we are using their config
https://docs.advanced-alchemy.litestar.dev/latest/usage/database_seeding.html
`from advanced_alchemy.config import AsyncSessionConfig, SQLAlchemyAsyncConfig`

### Support a postgres database in addition to SQLite

## Domain
- Remove UUIDs from the domain. ex: Topic.taxonomy_id is stupid, we want the identifier only

## Database
- Use the alchemy cli tool instead of alembic: https://docs.advanced-alchemy.litestar.dev/latest/usage/cli.html
- **Change the ID columns from an UUID to an URI**
- write tests for MismatchedTopicTaxonomyError

## Schema
- The `identifier` in Resource isnt a typical colon-sep, it should be an URI

## Test coverage
- tests for search that support arbitrary fields - these are skipped in two places
- tests for the database utilities and configuration
