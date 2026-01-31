#!/usr/bin/env bash

### Wipe out migrations and the database, and start from scratch
# with whatever the current schema is.
#
# You should probably not do this.

rm -rf "./src/ontology/database/migrations/versions.bak"
mv "./src/ontology/database/migrations/versions" "./src/ontology/database/migrations/versions.bak"

rm "./src/ontology/.data/ontology.db.bak"
mv "./src/ontology/.data/ontology.db" "./src/ontology/.data/ontology.db.bak"

rm "./.data/ontology.db.bak"
mv "./.data/ontology.db" "./.data/ontology.db.bak"

just migrate "Initial version (again)"
git add "./src/ontology/database/migrations/versions"
