#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "ontology",
#   "pyyaml"
# ]
# ///
"""Add realistic response examples to OpenAPI specification.

This script enhances the auto-generated OpenAPI spec by adding response
examples based on actual sample data from the test fixtures. This makes
the spec more useful for frontend development and testing.

Usage:
    uv run scripts/add-openapi-examples.py

The script:
1. Loads sample data from src/ontology/database/data/
2. Reads the generated OpenAPI spec
3. Adds realistic examples to key endpoints
4. Saves both JSON and YAML formats

Examples are based on actual test data to ensure they accurately
represent real API responses.
"""

import json
import yaml
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime, timezone, UTC
import uuid as uuid_module


# Helper functions for realistic data generation
def stable_uuid(seed: str) -> str:
    """Generate a stable UUID from a string seed for deterministic examples."""
    # Use hash to create deterministic UUID
    hash_val = hash(seed) & 0xFFFFFFFFFFFFFFFF
    return str(uuid_module.UUID(int=hash_val))


def load_sample_taxonomies() -> list[dict[str, Any]]:
    """Load taxonomy sample data."""
    data_path = Path("src/ontology/loader/data/sample_taxonomies.yaml")
    if not data_path.exists():
        return []

    with open(data_path) as f:
        data = yaml.safe_load(f)

    return data.get("taxonomies", [])


def load_sample_catalog() -> dict[str, list[dict[str, Any]]]:
    """Load catalog sample data."""
    data_path = Path("src/ontology/loader/data/sample_catalog.yaml")
    if not data_path.exists():
        return {}

    with open(data_path) as f:
        data = yaml.safe_load(f)

    return data


def load_sample_classifications() -> list[dict[str, Any]]:
    """Load document classification sample data."""
    data_path = Path("src/ontology/loader/data/sample_document_classifications.yaml")
    if not data_path.exists():
        return []

    with open(data_path) as f:
        data = yaml.safe_load(f)

    return data.get("document_classifications", [])


def create_examples() -> dict[str, Any]:
    """Create response examples from sample data."""

    # Load sample data
    taxonomies = load_sample_taxonomies()
    catalog_data = load_sample_catalog()
    classifications = load_sample_classifications()

    # Extract data
    catalogs = catalog_data.get("catalogs", [])
    repositories = catalog_data.get("repositories", [])
    purposes = catalog_data.get("purposes", [])

    # ISO timestamp for examples
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    examples = {
        # Root endpoint
        "/": {
            "get": {
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "example": {
                                    "name": "Ontology API",
                                    "version": "0.1.0",
                                    "docs": "/docs",
                                }
                            }
                        }
                    }
                }
            }
        },
        # Health endpoint
        "/health": {
            "get": {
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {"example": {"status": "healthy"}}
                        }
                    }
                }
            }
        },
    }

    # Add taxonomy examples if data available
    if taxonomies:
        # Taxonomy list
        taxonomy_list_items = []
        for tax in taxonomies[:2]:  # First 2 for example
            taxonomy_list_items.append(
                {
                    "id": stable_uuid(tax["identifier"]),
                    "identifier": tax["identifier"],
                    "title": tax["title"],
                    "description": tax.get("description"),
                    "skos_uri": None,
                    "created_at": now,
                    "updated_at": now,
                }
            )

        examples["/taxonomies"] = {
            "get": {
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "example": {
                                    "items": taxonomy_list_items,
                                    "total": len(taxonomy_list_items),
                                    "limit": 50,
                                    "offset": 0,
                                }
                            }
                        }
                    }
                }
            }
        }

        # Single taxonomy
        if taxonomy_list_items:
            examples["/taxonomies/{taxonomy_id}"] = {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {"example": taxonomy_list_items[0]}
                            }
                        }
                    }
                }
            }

        # Topic examples from first taxonomy
        if taxonomies and "topics" in taxonomies[0]:
            topics = taxonomies[0]["topics"]
            topic_list_items = []
            for topic in topics[:2]:  # First 2 topics
                topic_list_items.append(
                    {
                        "id": stable_uuid(topic["identifier"]),
                        "taxonomy_id": stable_uuid(taxonomies[0]["identifier"]),
                        "taxonomy_identifier": taxonomies[0]["identifier"],
                        "identifier": topic["identifier"],
                        "title": topic["title"],
                        "slug": topic["title"].lower().replace(" ", "-"),
                        "description": topic.get("description"),
                        "status": topic.get("status", "active"),
                        "path": "/" + topic["identifier"],
                        "aliases": topic.get("aliases", []),
                        "external_refs": {},
                        "created_at": now,
                        "updated_at": now,
                    }
                )

            examples["/topics"] = {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "example": {
                                        "items": topic_list_items,
                                        "total": len(topic_list_items),
                                        "limit": 50,
                                        "offset": 0,
                                    }
                                }
                            }
                        }
                    }
                }
            }

            # Single topic
            if topic_list_items:
                examples["/topics/{topic_id}"] = {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {"example": topic_list_items[0]}
                                }
                            }
                        }
                    }
                }

                # Topic search
                examples["/topics/search"] = {
                    "post": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "example": {
                                            "items": [topic_list_items[0]],
                                            "total": 1,
                                            "limit": 50,
                                            "offset": 0,
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

    # Add classification example if data available
    if classifications and taxonomies:
        doc = classifications[0]
        tax_class = doc.get("taxonomy_classification", {})
        topic_assignments = doc.get("topic_assignments", [])

        # Find the taxonomy
        tax_id = tax_class.get("taxonomy_identifier", "tx:health")
        taxonomy = next(
            (t for t in taxonomies if t["identifier"] == tax_id), taxonomies[0]
        )

        classification_example = {
            "content_preview": doc["content"][:200] + "...",
            "suggested_taxonomy": {
                "taxonomy_id": stable_uuid(taxonomy["identifier"]),
                "taxonomy_identifier": taxonomy["identifier"],
                "taxonomy_title": taxonomy["title"],
                "taxonomy_description": taxonomy.get("description"),
                "confidence": tax_class.get("confidence", 0.95),
                "reasoning": tax_class.get("reasoning", ""),
            },
            "alternative_taxonomies": [],
            "suggested_topics": [],
            "model_name": tax_class.get("model_name", "claude-sonnet-4-20250514"),
            "model_version": tax_class.get("model_version", "20250514"),
            "prompt_version": tax_class.get("prompt_version", "1.0.0"),
            "classification_id": stable_uuid(doc["document_id"] + "-classification"),
            "created_at": now,
            "document_id": stable_uuid(doc["document_id"]),
            "document_type": doc.get("document_type", "Note"),
        }

        # Add topic suggestions
        for i, topic_assign in enumerate(topic_assignments[:2]):
            classification_example["suggested_topics"].append(
                {
                    "topic_id": stable_uuid(topic_assign["topic_identifier"]),
                    "topic_identifier": topic_assign["topic_identifier"],
                    "topic_title": topic_assign["topic_identifier"]
                    .split(":")[-1]
                    .replace("-", " ")
                    .title(),
                    "topic_description": None,
                    "confidence": topic_assign.get("confidence", 0.8),
                    "rank": topic_assign.get("rank", i + 1),
                    "reasoning": topic_assign.get("reasoning", ""),
                }
            )

        examples["/classification/classify"] = {
            "post": {
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {"example": classification_example}
                        }
                    }
                }
            }
        }

    # Add classifier suggestions example
    if taxonomies and "topics" in taxonomies[0]:
        topics = taxonomies[0]["topics"]
        if topics:
            examples["/classifier/suggestions"] = {
                "post": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "example": {
                                        "input_text": "Using Claude for building AI applications with transformers",
                                        "model_name": "token_classifier",
                                        "model_version": "1.0.0",
                                        "suggestions": [
                                            {
                                                "topic_id": stable_uuid(
                                                    topics[0]["identifier"]
                                                ),
                                                "taxonomy_id": stable_uuid(
                                                    taxonomies[0]["identifier"]
                                                ),
                                                "title": topics[0]["title"],
                                                "slug": topics[0]["title"]
                                                .lower()
                                                .replace(" ", "-"),
                                                "confidence": 0.89,
                                                "rank": 1,
                                                "metadata": {},
                                            }
                                        ],
                                    }
                                }
                            }
                        }
                    }
                }
            }

    # Add catalog examples
    if catalogs:
        catalog_list_items = []
        for cat in catalogs[:2]:
            catalog_list_items.append(
                {
                    "id": stable_uuid(cat["identifier"]),
                    "identifier": cat["identifier"],
                    "title": cat["title"],
                    "description": cat.get("description"),
                    "themes": cat.get("themes", []),
                    "created_at": now,
                    "updated_at": now,
                }
            )

        examples["/catalogs"] = {
            "get": {
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "example": {
                                    "items": catalog_list_items,
                                    "total": len(catalog_list_items),
                                    "limit": 50,
                                    "offset": 0,
                                }
                            }
                        }
                    }
                }
            }
        }

    # Add repository examples
    if repositories:
        repo_list_items = []
        for repo in repositories[:2]:
            repo_list_items.append(
                {
                    "id": stable_uuid(repo["identifier"]),
                    "identifier": repo["identifier"],
                    "title": repo["title"],
                    "service_name": repo["service_name"],
                    "description": repo.get("description"),
                    "created_at": now,
                    "updated_at": now,
                }
            )

        examples["/repositories"] = {
            "get": {
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "example": {
                                    "items": repo_list_items,
                                    "total": len(repo_list_items),
                                    "limit": 50,
                                    "offset": 0,
                                }
                            }
                        }
                    }
                }
            }
        }

    # Add purpose examples
    if purposes:
        purpose_list_items = []
        for purp in purposes[:1]:
            purpose_list_items.append(
                {
                    "id": stable_uuid(purp["identifier"]),
                    "identifier": purp["identifier"],
                    "title": purp["title"],
                    "description": purp.get("description"),
                    "role": purp.get("role"),
                    "meaning": purp.get("meaning"),
                    "created_at": now,
                    "updated_at": now,
                }
            )

        examples["/purposes"] = {
            "get": {
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "example": {
                                    "items": purpose_list_items,
                                    "total": len(purpose_list_items),
                                    "limit": 50,
                                    "offset": 0,
                                }
                            }
                        }
                    }
                }
            }
        }

    # Add resources example
    if catalogs:
        examples["/resources"] = {
            "get": {
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "example": {
                                    "items": [
                                        {
                                            "id": stable_uuid("res:example-1"),
                                            "catalog_id": stable_uuid(
                                                catalogs[0]["identifier"]
                                            ),
                                            "catalog": catalogs[0]["identifier"],
                                            "identifier": "res:python-docs",
                                            "title": "Python Documentation",
                                            "description": "Official Python language documentation",
                                            "resource_type": "Bookmark",
                                            "location": "https://docs.python.org/3/",
                                            "repository": None,
                                            "repository_id": None,
                                            "content_location": None,
                                            "format": "HTML",
                                            "media_type": "text/html",
                                            "theme": "tech:software",
                                            "subject": "Python programming language",
                                            "creator": None,
                                            "has_purpose": None,
                                            "has_use": [],
                                            "related_resources": [],
                                            "related_topics": ["tech:software"],
                                            "created_at": now,
                                            "updated_at": now,
                                        }
                                    ],
                                    "total": 1,
                                    "limit": 50,
                                    "offset": 0,
                                }
                            }
                        }
                    }
                }
            }
        }

    # Add read-model examples
    if taxonomies:
        examples["/read-model/topics/counts"] = {
            "get": {
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "example": {
                                    "total": sum(
                                        len(t.get("topics", [])) for t in taxonomies
                                    ),
                                    "items": [
                                        {
                                            "taxonomy_id": stable_uuid(t["identifier"]),
                                            "count": len(t.get("topics", [])),
                                        }
                                        for t in taxonomies[:2]
                                    ],
                                }
                            }
                        }
                    }
                }
            }
        }

        # Recent topics
        if taxonomies and "topics" in taxonomies[0] and taxonomies[0]["topics"]:
            examples["/read-model/topics/recent"] = {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "example": {
                                        "taxonomy_id": None,
                                        "items": [
                                            {
                                                "id": stable_uuid(topic["identifier"]),
                                                "taxonomy_id": stable_uuid(
                                                    taxonomies[0]["identifier"]
                                                ),
                                                "title": topic["title"],
                                                "slug": topic["title"]
                                                .lower()
                                                .replace(" ", "-"),
                                                "path": "/" + topic["identifier"],
                                                "status": topic.get("status", "active"),
                                                "created_at": now,
                                            }
                                            for topic in taxonomies[0]["topics"][:2]
                                        ],
                                    }
                                }
                            }
                        }
                    }
                }
            }

        # Topic summary
        examples["/read-model/topics/summary"] = {
            "get": {
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "example": {
                                    "taxonomy_id": None,
                                    "total": sum(
                                        len(t.get("topics", [])) for t in taxonomies
                                    ),
                                    "by_status": {
                                        "active": sum(
                                            len(
                                                [
                                                    top
                                                    for top in t.get("topics", [])
                                                    if top.get("status", "active")
                                                    == "active"
                                                ]
                                            )
                                            for t in taxonomies
                                        ),
                                        "draft": 0,
                                        "deprecated": 0,
                                        "merged": 0,
                                    },
                                }
                            }
                        }
                    }
                }
            }
        }

    return examples


def apply_examples_to_spec(spec: dict[str, Any], examples: dict[str, Any]) -> None:
    """Apply examples to the OpenAPI spec in-place."""

    for path, methods in examples.items():
        if path not in spec.get("paths", {}):
            continue

        for method, config in methods.items():
            if method not in spec["paths"][path]:
                continue

            # Merge the example into the existing response
            for status_code, response_config in config["responses"].items():
                if status_code not in spec["paths"][path][method]["responses"]:
                    continue

                if "content" in response_config:
                    # Ensure content exists
                    if (
                        "content"
                        not in spec["paths"][path][method]["responses"][status_code]
                    ):
                        spec["paths"][path][method]["responses"][status_code][
                            "content"
                        ] = {}

                    # Add examples to each content type
                    for content_type, content_config in response_config[
                        "content"
                    ].items():
                        if (
                            content_type
                            not in spec["paths"][path][method]["responses"][
                                status_code
                            ]["content"]
                        ):
                            spec["paths"][path][method]["responses"][status_code][
                                "content"
                            ][content_type] = {}

                        # Merge example
                        spec["paths"][path][method]["responses"][status_code][
                            "content"
                        ][content_type].update(content_config)


def main():
    """Add examples to OpenAPI specification."""

    # Paths
    yaml_path = Path("docs/api/openapi.yaml")
    json_path = Path("docs/api/openapi.json")

    # Check if spec exists
    if not yaml_path.exists() and not json_path.exists():
        print("❌ OpenAPI spec not found. Run 'just openapi' first.")
        return 1

    # Load the spec (prefer YAML)
    if yaml_path.exists():
        with open(yaml_path) as f:
            spec = yaml.safe_load(f)
        print(f"📖 Loaded OpenAPI spec from {yaml_path}")
    else:
        with open(json_path) as f:
            spec = json.load(f)
        print(f"📖 Loaded OpenAPI spec from {json_path}")

    # Create examples from sample data
    print("🔍 Loading sample data and creating examples...")
    examples = create_examples()

    # Apply examples to spec
    print(f"✨ Adding {len(examples)} endpoint examples...")
    apply_examples_to_spec(spec, examples)

    # Save YAML
    with open(yaml_path, "w") as f:
        yaml.dump(
            spec,
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=120,
        )
    print(f"💾 Saved YAML: {yaml_path}")

    # Save JSON
    with open(json_path, "w") as f:
        json.dump(spec, f, indent=2)
    print(f"💾 Saved JSON: {json_path}")

    print()
    print("✅ OpenAPI examples added successfully!")
    print()
    print("Summary:")
    print(f"  - Endpoints with examples: {len(examples)}")
    print("  - Source: Sample data from src/ontology/loader/data/")
    print("  - Formats: YAML and JSON")
    print()
    print(
        "💡 Tip: Run 'just openapi' to regenerate the base spec, then run this script again."
    )

    return 0


if __name__ == "__main__":
    exit(main())
