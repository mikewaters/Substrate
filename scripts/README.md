# Scripts Directory

## Project Utilities

- These scripts are expected to use local packages
- These scripts can rely on the project virtual environment
- These scripts are expected to run within a tool like python or uv

## Available Scripts

### API Documentation

#### `gen-openapi-spec.py`
Generates the base OpenAPI specification from the FastAPI application.

**Usage:**
```bash
python scripts/gen-openapi-spec.py
# or
just openapi-base
```

**Outputs:**
- `docs/api/openapi.json` - JSON format
- `docs/api/openapi.yaml` - YAML format

#### `add-openapi-examples.py`
Adds realistic response examples to the OpenAPI specification based on sample data.

**Usage:**
```bash
uv run scripts/add-openapi-examples.py
# or
just openapi-examples
```

**Features:**
- Loads sample data from `src/ontology/database/data/`
- Generates realistic examples with stable UUIDs
- Adds examples to 16+ key endpoints
- Updates both JSON and YAML formats

**Data Sources:**
- `sample_taxonomies.yaml` - Taxonomy and topic data
- `sample_catalog.yaml` - Catalog, repository, and purpose data
- `sample_document_classifications.yaml` - Classification examples

**Complete Build:**
```bash
just openapi  # Runs both scripts in sequence
```

### Data Loading

#### `load-datasets.py`
Interactive TUI for loading dataset fixtures into the database.

**Usage:**
```bash
uv run scripts/load-datasets.py
```
