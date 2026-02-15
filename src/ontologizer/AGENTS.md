## Technology Requirements

- Use Pydantic for defining i/o schema and command payloads
- Use `attrs` dataclasses for domain models - do *not* use pydantic for domain models
- Use `advanced-alchemy` for relational database interactions.
- Use PydanticAI for LLM interactions
- Use SQLIte for databases, feel free to suggest extensions
- Use FastAPI for HTTP and websocket APIs
- Pytest for testing
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
