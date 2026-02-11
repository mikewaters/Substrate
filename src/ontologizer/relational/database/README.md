# Ontology.Database
This module implements the ORM Layer (Layer 4); it receives ORM models and makes database calls.

**All** sqlalchemy models should be defined here.

All database-specific interactions should be defined here; no other modules should know about database technology

Technology used: [Advanced-Alchemy](https://docs.advanced-alchemy.litestar.dev/latest/reference/index.html)
