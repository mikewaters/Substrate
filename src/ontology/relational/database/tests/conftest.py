"""Test fixtures specific to database tests.

This module extends the shared fixtures from ontology/tests/conftest.py
with database-specific fixtures. The shared fixtures now use Advanced-Alchemy
for session management.

Note:
    Most tests should use the async db_session fixture from the shared
    conftest.py. These fixtures are for legacy compatibility or specific
    database-layer testing needs.
"""


# The shared async fixtures in ontology/tests/conftest.py provide:
# - db_session: Async database session using Advanced-Alchemy

# This conftest is kept for potential database-specific test extensions.
# If no additional fixtures are needed, this file can be removed.
