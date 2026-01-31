#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "ontology",
#   "pyyaml"
# ]
# ///
"""Generate enhanced OpenAPI specification for the Ontology API.

This script creates a comprehensive OpenAPI spec by:
1. Starting the FastAPI app
2. Extracting the auto-generated OpenAPI spec
3. Enhancing it with additional metadata
4. Saving it to multiple formats (JSON, YAML)
"""

import json
import yaml
from pathlib import Path
from typing import Any

from ontology.api.app import create_app


def enhance_openapi_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Enhance the auto-generated OpenAPI spec with additional metadata."""

    # Add contact and license information
    spec["info"].update(
        {
            "contact": {
                "name": "LifeOS Development Team",
                "url": "https://github.com/LifeOS/Substrate",
                "email": "mike@mikewaters.net",
            },
            "license": {
                "name": "MIT",  # Update with your actual license
                "url": "https://opensource.org/licenses/MIT",
            },
            "x-api-id": "ontology-api",
            "x-audience": "internal",
        }
    )

    # Add server information
    spec["servers"] = [
        {"url": "http://localhost:8000", "description": "Development server"},
        {
            "url": "https://api.lifeos.dev",  # Update with your production URL
            "description": "Production server",
        },
    ]

    # Add security schemes if needed
    spec["components"] = spec.get("components", {})
    spec["components"]["securitySchemes"] = {
        "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"},
        "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
    }

    return spec


def main():
    """Generate OpenAPI specifications."""

    # Create FastAPI app
    app = create_app()

    # Get the OpenAPI spec
    openapi_spec = app.openapi()

    # Enhance the spec
    enhanced_spec = enhance_openapi_spec(openapi_spec)

    # Create output directory
    output_dir = Path("docs/api")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save JSON format
    json_path = output_dir / "openapi.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(enhanced_spec, f, indent=2, sort_keys=True)

    # Save YAML format
    yaml_path = output_dir / "openapi.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(enhanced_spec, f, default_flow_style=False, sort_keys=True)

    print("OpenAPI spec generated:")
    print(f"JSON: {json_path}")
    print(f"YAML: {yaml_path}")


if __name__ == "__main__":
    main()
