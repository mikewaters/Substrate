# OpenAPI Response Examples Summary

This document provides a summary of the response examples added to the Ontology API OpenAPI specification for React app testing.

## Overview

**Total endpoints with examples: 16**

Examples were added based on realistic sample data from the database fixtures located in `src/ontology/database/data/`.

## Endpoints with Examples

### Health & Status Endpoints

#### `GET /`
Root API endpoint returning basic API information.

**Example Response:**
```json
{
  "name": "Ontology API",
  "version": "0.1.0",
  "docs": "/docs"
}
```

#### `GET /health`
Health check endpoint for monitoring.

**Example Response:**
```json
{
  "status": "healthy"
}
```

---

### Taxonomy Endpoints

#### `GET /taxonomies`
List all taxonomies with pagination.

**Example Response:**
```json
{
  "items": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "identifier": "tx:tech",
      "title": "Technology",
      "description": "Topics related to technology domains",
      "skos_uri": null,
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    },
    {
      "id": "123e4567-e89b-12d3-a456-426614174001",
      "identifier": "tx:health",
      "title": "Health & Wellness",
      "description": "Physical and mental health topics",
      "skos_uri": null,
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    }
  ],
  "total": 2,
  "limit": 50,
  "offset": 0
}
```

#### `GET /taxonomies/{taxonomy_id}`
Get a single taxonomy by ID.

**Example Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "identifier": "tx:tech",
  "title": "Technology",
  "description": "Topics related to technology domains",
  "skos_uri": null,
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-01T00:00:00Z"
}
```

---

### Topic Endpoints

#### `GET /topics`
List topics with optional filters and pagination.

**Example Response:**
```json
{
  "items": [
    {
      "id": "223e4567-e89b-12d3-a456-426614174000",
      "taxonomy_id": "123e4567-e89b-12d3-a456-426614174000",
      "taxonomy_identifier": "tx:tech",
      "identifier": "tech:ai",
      "title": "Artificial Intelligence",
      "slug": "artificial-intelligence",
      "description": "AI and machine learning concepts",
      "status": "active",
      "path": "/tech:software/tech:ai",
      "aliases": ["AI", "machine learning"],
      "external_refs": {},
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    },
    {
      "id": "223e4567-e89b-12d3-a456-426614174001",
      "taxonomy_id": "123e4567-e89b-12d3-a456-426614174000",
      "taxonomy_identifier": "tx:tech",
      "identifier": "tech:llm",
      "title": "Large Language Models",
      "slug": "large-language-models",
      "description": "Foundation and transformer models",
      "status": "active",
      "path": "/tech:software/tech:ai/tech:llm",
      "aliases": ["LLMs", "foundation models"],
      "external_refs": {},
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    }
  ],
  "total": 2,
  "limit": 50,
  "offset": 0
}
```

#### `GET /topics/{topic_id}`
Get a single topic by ID.

**Example Response:**
```json
{
  "id": "223e4567-e89b-12d3-a456-426614174000",
  "taxonomy_id": "123e4567-e89b-12d3-a456-426614174000",
  "taxonomy_identifier": "tx:tech",
  "identifier": "tech:ai",
  "title": "Artificial Intelligence",
  "slug": "artificial-intelligence",
  "description": "AI and machine learning concepts",
  "status": "active",
  "path": "/tech:software/tech:ai",
  "aliases": ["AI", "machine learning"],
  "external_refs": {},
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-01T00:00:00Z"
}
```

#### `POST /topics/search`
Search for topics by title or alias.

**Example Response:**
```json
{
  "items": [
    {
      "id": "223e4567-e89b-12d3-a456-426614174000",
      "taxonomy_id": "123e4567-e89b-12d3-a456-426614174000",
      "taxonomy_identifier": "tx:tech",
      "identifier": "tech:ai",
      "title": "Artificial Intelligence",
      "slug": "artificial-intelligence",
      "description": "AI and machine learning concepts",
      "status": "active",
      "path": "/tech:software/tech:ai",
      "aliases": ["AI", "machine learning"],
      "external_refs": {},
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

---

### Classification Endpoints

#### `POST /classification/classify`
Classify document content into taxonomy and topics using LLM.

**Example Response:**
```json
{
  "content_preview": "# Dopamine and Neuroplasticity\n\nDopamine is a crucial neurotransmitter in the brain that plays a significant role in several\nfunctions, including reward, motivation, memory...",
  "suggested_taxonomy": {
    "taxonomy_id": "123e4567-e89b-12d3-a456-426614174001",
    "taxonomy_identifier": "tx:health",
    "taxonomy_title": "Health & Wellness",
    "taxonomy_description": "Physical and mental health topics",
    "confidence": 0.95,
    "reasoning": "Document clearly focuses on neuroscience and brain health, discussing neurotransmitters, brain function, and neurological conditions"
  },
  "alternative_taxonomies": [
    {
      "taxonomy_id": "123e4567-e89b-12d3-a456-426614174000",
      "taxonomy_identifier": "tx:tech",
      "taxonomy_title": "Technology",
      "taxonomy_description": "Topics related to technology domains",
      "confidence": 0.25,
      "reasoning": "Some mention of biological processes that could relate to computational neuroscience"
    }
  ],
  "suggested_topics": [
    {
      "topic_id": "323e4567-e89b-12d3-a456-426614174000",
      "topic_identifier": "health:neuroscience",
      "topic_title": "Neuroscience",
      "topic_description": "Study of the nervous system and brain",
      "confidence": 0.92,
      "rank": 1,
      "reasoning": "Core focus on neurotransmitter function and brain mechanisms"
    },
    {
      "topic_id": "323e4567-e89b-12d3-a456-426614174001",
      "topic_identifier": "health:mental",
      "topic_title": "Mental Health",
      "topic_description": "Psychological and emotional well-being",
      "confidence": 0.78,
      "rank": 2,
      "reasoning": "Discusses learning, memory, and attention which relate to mental health"
    }
  ],
  "model_name": "claude-sonnet-4-20250514",
  "model_version": "20250514",
  "prompt_version": "1.0.0",
  "classification_id": "423e4567-e89b-12d3-a456-426614174000",
  "created_at": "2025-01-03T12:34:56Z",
  "document_id": "523e4567-e89b-12d3-a456-426614174000",
  "document_type": "Note"
}
```

#### `POST /classifier/suggestions`
Generate topic suggestions for input text using token-based classifier.

**Example Response:**
```json
{
  "input_text": "Using Claude for building AI applications with transformers",
  "model_name": "token_classifier",
  "model_version": "1.0.0",
  "suggestions": [
    {
      "topic_id": "223e4567-e89b-12d3-a456-426614174001",
      "taxonomy_id": "123e4567-e89b-12d3-a456-426614174000",
      "title": "Large Language Models",
      "slug": "large-language-models",
      "confidence": 0.89,
      "rank": 1,
      "metadata": {}
    },
    {
      "topic_id": "223e4567-e89b-12d3-a456-426614174000",
      "taxonomy_id": "123e4567-e89b-12d3-a456-426614174000",
      "title": "Artificial Intelligence",
      "slug": "artificial-intelligence",
      "confidence": 0.76,
      "rank": 2,
      "metadata": {}
    }
  ]
}
```

---

### Catalog Endpoints

#### `GET /catalogs`
List catalogs with pagination.

**Example Response:**
```json
{
  "items": [
    {
      "id": "623e4567-e89b-12d3-a456-426614174000",
      "identifier": "cat:tech-resources",
      "title": "Technology Resources",
      "description": "Collection of technical documentation, tutorials, and tools",
      "themes": ["tech:software", "tech:ai", "tech:cloud"],
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    },
    {
      "id": "623e4567-e89b-12d3-a456-426614174001",
      "identifier": "cat:learning",
      "title": "Learning Materials",
      "description": "Educational content across various domains",
      "themes": ["know:capture", "know:organize", "life:productivity"],
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    }
  ],
  "total": 2,
  "limit": 50,
  "offset": 0
}
```

---

### Repository Endpoints

#### `GET /repositories`
List repositories with pagination.

**Example Response:**
```json
{
  "items": [
    {
      "id": "723e4567-e89b-12d3-a456-426614174000",
      "identifier": "repo:github",
      "title": "GitHub",
      "service_name": "github",
      "description": "Source code and documentation on GitHub",
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    },
    {
      "id": "723e4567-e89b-12d3-a456-426614174001",
      "identifier": "repo:notion",
      "title": "Notion Workspace",
      "service_name": "notion",
      "description": "Team knowledge base in Notion",
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    }
  ],
  "total": 2,
  "limit": 50,
  "offset": 0
}
```

---

### Purpose Endpoints

#### `GET /purposes`
List purposes with pagination.

**Example Response:**
```json
{
  "items": [
    {
      "id": "823e4567-e89b-12d3-a456-426614174000",
      "identifier": "purpose:learn",
      "title": "Learning",
      "description": "Resources for learning new skills and knowledge",
      "role": "educational",
      "meaning": "To acquire knowledge or skill",
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

---

### Resource Endpoints

#### `GET /resources`
List resources with optional filters and pagination.

**Example Response:**
```json
{
  "items": [
    {
      "id": "923e4567-e89b-12d3-a456-426614174000",
      "catalog_id": "623e4567-e89b-12d3-a456-426614174000",
      "catalog": "cat:tech-resources",
      "identifier": "res:python-docs",
      "title": "Python Documentation",
      "description": "Official Python language documentation",
      "resource_type": "Bookmark",
      "location": "https://docs.python.org/3/",
      "repository": null,
      "repository_id": null,
      "content_location": null,
      "format": "HTML",
      "media_type": "text/html",
      "theme": "tech:software",
      "subject": "Python programming language",
      "creator": null,
      "has_purpose": null,
      "has_use": [],
      "related_resources": [],
      "related_topics": ["tech:software"],
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

---

### Read Model Endpoints

#### `GET /read-model/topics/counts`
Get topic counts grouped by taxonomy.

**Example Response:**
```json
{
  "total": 53,
  "items": [
    {
      "taxonomy_id": "123e4567-e89b-12d3-a456-426614174000",
      "count": 31
    },
    {
      "taxonomy_id": "123e4567-e89b-12d3-a456-426614174001",
      "count": 22
    }
  ]
}
```

#### `GET /read-model/topics/recent`
Get recently created topics.

**Example Response:**
```json
{
  "taxonomy_id": null,
  "items": [
    {
      "id": "223e4567-e89b-12d3-a456-426614174005",
      "taxonomy_id": "123e4567-e89b-12d3-a456-426614174000",
      "title": "Edge Computing",
      "slug": "edge-computing",
      "path": "/tech:cloud/tech:iot/tech:edge",
      "status": "active",
      "created_at": "2025-01-03T10:30:00Z"
    },
    {
      "id": "223e4567-e89b-12d3-a456-426614174001",
      "taxonomy_id": "123e4567-e89b-12d3-a456-426614174000",
      "title": "Large Language Models",
      "slug": "large-language-models",
      "path": "/tech:software/tech:ai/tech:llm",
      "status": "active",
      "created_at": "2025-01-02T14:20:00Z"
    }
  ]
}
```

#### `GET /read-model/topics/summary`
Get aggregate topic counts by status.

**Example Response:**
```json
{
  "taxonomy_id": null,
  "total": 53,
  "by_status": {
    "active": 48,
    "draft": 3,
    "deprecated": 2,
    "merged": 0
  }
}
```

---

## Usage in React Apps

These examples can be used directly in your React testing by:

1. **Mock Service Worker (MSW)**: Import the OpenAPI spec and use the examples as mock responses
2. **Storybook**: Use examples to populate component stories with realistic data
3. **Unit Tests**: Use examples as fixtures in Jest/Vitest tests
4. **Integration Tests**: Compare API responses against these examples for validation

### Example with MSW

```typescript
import { rest } from 'msw';
import openapi from './openapi.yaml';

export const handlers = [
  rest.get('/api/taxonomies', (req, res, ctx) => {
    // Use the example from OpenAPI spec
    const example = openapi.paths['/taxonomies'].get.responses['200'].content['application/json'].example;
    return res(ctx.json(example));
  }),
];
```

### Example with React Query

```typescript
import { useQuery } from '@tanstack/react-query';

// The response will match the OpenAPI example structure
const { data } = useQuery({
  queryKey: ['taxonomies'],
  queryFn: () => fetch('/api/taxonomies').then(r => r.json())
});

// TypeScript types can be generated from OpenAPI schemas
type TaxonomyListResponse = {
  items: Array<{
    id: string;
    identifier: string;
    title: string;
    description: string | null;
    // ... other fields
  }>;
  total: number;
  limit: number;
  offset: number;
};
```

## Data Sources

All examples are based on realistic sample data from:
- `src/ontology/database/data/sample_taxonomies.yaml`
- `src/ontology/database/data/sample_catalog.yaml`
- `src/ontology/database/data/sample_document_classifications.yaml`

## Notes

- All UUIDs in examples are for illustration purposes
- Timestamps use ISO 8601 format
- Null values are represented as `null` in JSON (not `"null"` string)
- Arrays can be empty `[]` when no items exist
- Pagination follows offset-based pattern with `limit`, `offset`, and `total`
