#!/usr/bin/env python3
"""Generate comprehensive API documentation."""

import subprocess
import shutil
from pathlib import Path


def generate_docs():
    """Generate all API documentation artifacts."""

    docs_dir = Path("docs/api")
    docs_dir.mkdir(parents=True, exist_ok=True)

    print("Generating OpenAPI specification...")
    subprocess.run(["just", "openapi"], check=True)

    # Generate static HTML documentation using redoc-cli if available
    print("Generating static HTML documentation...")
    subprocess.run([
        "npx", "--yes", "@redocly/cli", "build-docs", "docs/api/openapi.yaml",
        #"npx", "--yes", "redoc-cli", "build", "docs/api/openapi.yaml",
        "--output", "docs/api/index.html",
        "--title", "Ontology API Documentation"
    ], check=True)

    # Generate Postman collection if openapi-to-postman is available
    print("Generating Postman collection...")
    subprocess.run([
        "npx", "--yes", "openapi-to-postmanv2",
        "-s", "docs/api/openapi.yaml",
        "-o", "docs/api/postman-collection.json"
    ], check=True)
    print("Postman collection generated")

    print("API documentation generation complete!")


if __name__ == "__main__":
    generate_docs()
