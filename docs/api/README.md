# OpenAPI Documentation

This directory contains auto-generated OpenAPI specifications for the Ontology API.

## Files

- **`openapi.yaml`** - OpenAPI 3.1.0 specification in YAML format (with examples)
- **`openapi.json`** - OpenAPI 3.1.0 specification in JSON format (with examples)
- **`EXAMPLES_SUMMARY.md`** - Detailed documentation of all response examples

## Generation Workflow

The OpenAPI specification is generated in two stages:

### Stage 1: Base Spec Generation

The base specification is auto-generated from the FastAPI application:

```bash
just openapi-base
# or
python scripts/gen-openapi-spec.py
```

**What it does:**
- Creates FastAPI app instance
- Extracts auto-generated OpenAPI spec
- Enhances with metadata (contact info, servers, security schemes)
- Saves to `docs/api/openapi.{json,yaml}`

### Stage 2: Example Addition

Realistic response examples are added based on sample data:

```bash
just openapi-examples
# or
uv run scripts/add-openapi-examples.py
```

**What it does:**
- Loads sample data from `src/ontology/database/data/`
- Generates realistic examples with stable UUIDs
- Adds examples to 16+ key endpoints
- Updates both JSON and YAML files

**Data sources:**
- `sample_taxonomies.yaml` - Taxonomy and topic examples
- `sample_catalog.yaml` - Catalog, repository, and purpose examples
- `sample_document_classifications.yaml` - Classification examples

### Complete Build

Run both stages in sequence:

```bash
just openapi
```

## Using the Examples

The examples are designed for frontend development and testing:

### Mock Service Worker (MSW)

```typescript
import { http, HttpResponse } from 'msw';
import openapi from './openapi.json';

export const handlers = [
  http.get('/api/taxonomies', () => {
    const example = openapi.paths['/taxonomies'].get.responses['200']
      .content['application/json'].example;
    return HttpResponse.json(example);
  }),
];
```

### React Query

```typescript
import { useQuery } from '@tanstack/react-query';

// Response structure matches OpenAPI examples
const { data } = useQuery({
  queryKey: ['taxonomies'],
  queryFn: () => fetch('/api/taxonomies').then(r => r.json())
});

// TypeScript types can be generated from OpenAPI schemas
// using tools like openapi-typescript
```

### Storybook

```typescript
import type { Meta, StoryObj } from '@storybook/react';
import { TaxonomyList } from './TaxonomyList';
import openapi from '../openapi.json';

const meta: Meta<typeof TaxonomyList> = {
  component: TaxonomyList,
};

export default meta;

export const Default: StoryObj<typeof TaxonomyList> = {
  args: {
    data: openapi.paths['/taxonomies'].get.responses['200']
      .content['application/json'].example
  },
};
```

## Validation

Validate the spec is valid OpenAPI 3.1.0:

```bash
just validate-openapi
```

## Updating Examples

When you update sample data in `src/ontology/database/data/`, regenerate examples:

```bash
just openapi  # Regenerates base spec + adds examples
```

## Example Coverage

Currently, 16 endpoints have realistic response examples:

- **Health/Status**: `/`, `/health`
- **Taxonomies**: `/taxonomies`, `/taxonomies/{id}`
- **Topics**: `/topics`, `/topics/{id}`, `/topics/search`
- **Classification**: `/classification/classify`, `/classifier/suggestions`
- **Catalogs**: `/catalogs`
- **Repositories**: `/repositories`
- **Purposes**: `/purposes`
- **Resources**: `/resources`
- **Read Model**: `/read-model/topics/{counts,recent,summary}`

See `EXAMPLES_SUMMARY.md` for detailed documentation of each example.

## CI/CD Integration

In your CI pipeline, regenerate the spec to ensure it stays in sync:

```yaml
# .github/workflows/docs.yml
- name: Generate OpenAPI spec
  run: just openapi

- name: Validate OpenAPI spec
  run: just validate-openapi
```

## TypeScript Type Generation

Generate TypeScript types from the OpenAPI spec:

```bash
# Install openapi-typescript
npm install -D openapi-typescript

# Generate types
npx openapi-typescript docs/api/openapi.yaml -o src/types/api.ts
```

Then use the types in your React app:

```typescript
import type { components } from './types/api';

type TaxonomyResponse = components['schemas']['TaxonomyResponse'];
type TopicListResponse = components['schemas']['TopicListResponse'];
```
