# Ontology Test Data

This directory contains comprehensive test datasets for all entities in the ontology module.

## Data Files

### sample_taxonomies.yaml
Hierarchical taxonomy and topic data with edges and polyhierarchy examples.

**Entities:**
- 5 Taxonomies (Technology, Health & Wellness, Life Management, Knowledge Management, Work & Collaboration)
- 53 Topics with hierarchical relationships
- 58 Topic edges (parent-child relationships)
- 134 Closure table entries (transitive relationships)

### sample_activities.yaml
Work activity data across all activity types.

**Entities:**
- 20 Activities (Tasks, Research, Study, Experiments, Efforts, Thinking)
- Multiple creators and activity types
- Auto-generated identifiers (act:*)

### sample_catalog.yaml
Resource catalog data with multiple resource types.

**Entities:**
- 4 Catalogs
- 5 Repositories (github, notion, gdrive, arxiv, local)
- 4 Purposes
- 18 Resources (Bookmarks, Documents, Notes, Collections, generic Resources)

### sample_information_extended.yaml
Classifier suggestions and external entity matches.

**Entities:**
- 23 Topic Suggestions (classifier-generated topic links)
- 14 Matches (external system alignments to Wikidata, DBpedia)

## Loading Data

### Using the CLI

Load all datasets from this directory:
```bash
uv run python -m ontology.loader
```

Load from a specific path:
```bash
uv run python -m ontology.loader /path/to/data
```

Load a single file:
```bash
uv run python -m ontology.loader /path/to/sample_taxonomies.yaml
```

### Programmatically

```python
from pathlib import Path
from ontology.loader.loader import load_yaml_dataset
from ontology.relational.database import get_async_session_factory


async def load_data():
    data_dir = Path(__file__).parent / "database" / "data"
    async_session_factory = get_async_session_factory()

    async with async_session_factory() as session:
        summary = await load_yaml_dataset(data_dir, session)
        print(summary)
```

## Dataset Statistics

When loading all files from directory:
```
taxonomies: 5, topics: 54, edges: 59, closures: 136
activities: 20
catalogs: 4, repositories: 5, purposes: 4, resources: 18
topic_suggestions: 23, matches: 14
document_classifications: 6, topic_assignments: 16
```

Note: Topic count includes the added `health:neuroscience` topic needed for document classifications.

## Testing

Run all loader tests:
```bash
uv run pytest src/ontology/loader/tests/ -v
```

All 29 tests verify entity counts, field population, relationships, and data consistency.

## Notes
- IDs are deterministic strings for test repeatability
- `sample_information_extended.yaml` requires `sample_taxonomies.yaml` (topics must exist)
- Files are loaded in dependency order automatically when loading from a directory
