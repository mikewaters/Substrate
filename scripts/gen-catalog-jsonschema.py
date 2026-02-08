#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "catalog",
#   "loguru",
#   "rich",
#   "sqlalchemy",
#   "typer",
# ]
# ///
"""Generate a lightweight JSON Schema doc for catalog.store models."""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Optional

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    inspect as sa_inspect,
)
from sqlalchemy.orm import ColumnProperty, DeclarativeBase, RelationshipProperty

try:
    from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
except Exception:  # pragma: no cover - optional dialect types
    ARRAY = None
    JSONB = None
    UUID = None

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MODULE_FILE = ROOT_DIR / "src/catalog/catalog/store/models.py"
DEFAULT_OUTPUT = ROOT_DIR / "src/catalog/docs/catalog-store-schema.json"
DEFAULT_SCHEMA_ID_BASE = "https://example.org/catalog-store/schemas"
DEFAULT_SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"


@dataclass
class SchemaOptions:
    """Configuration for schema generation."""

    relationships: str
    max_depth: int
    output_format: str
    schema_id_base: str


@dataclass
class CoverageReport:
    """Tracks mapping coverage during schema generation."""

    unmapped_types: dict[str, int] = field(default_factory=dict)
    skipped_relationships: int = 0
    skipped_models: list[str] = field(default_factory=list)

    def record_unmapped_type(self, type_name: str) -> None:
        """Record an unmapped SQLAlchemy type name."""
        self.unmapped_types[type_name] = self.unmapped_types.get(type_name, 0) + 1


app = typer.Typer(
    help="Generate JSON Schema documentation from SQLAlchemy models.",
    add_completion=False,
)
console = Console()


def _import_symbol(path: str) -> Any:
    """Import a symbol from a module:path string."""
    module_path, sep, symbol = path.partition(":")
    module = importlib.import_module(module_path)
    if not sep:
        return module
    return getattr(module, symbol)


def _load_module_from_file(path: Path, module_name: str) -> Any:
    """Load a module from a file path."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _create_isolated_base() -> type[DeclarativeBase]:
    """Create an isolated declarative base for doc-only imports."""

    class DocBase(DeclarativeBase):
        """Isolated declarative base for documentation introspection."""

        pass

    return DocBase


def _discover_models_from_module(
    module: Any, base: type[DeclarativeBase]
) -> list[type[DeclarativeBase]]:
    """Discover SQLAlchemy models in a module by subclassing the base."""
    models: list[type[DeclarativeBase]] = []
    for value in vars(module).values():
        if not isinstance(value, type):
            continue
        if value is base:
            continue
        if not issubclass(value, base):
            continue
        if getattr(value, "__abstract__", False):
            continue
        models.append(value)
    return sorted(models, key=lambda cls: cls.__name__)


def _discover_models_from_registry(
    module_prefix: str, base: type[DeclarativeBase]
) -> list[type[DeclarativeBase]]:
    """Discover SQLAlchemy models registered under a module prefix."""
    models: list[type[DeclarativeBase]] = []
    for mapper in base.registry.mappers:
        cls = mapper.class_
        if not cls.__module__.startswith(module_prefix):
            continue
        if getattr(cls, "__abstract__", False):
            continue
        models.append(cls)
    return sorted(models, key=lambda cls: cls.__name__)


def _type_to_schema(sa_type: Any, report: CoverageReport) -> dict[str, Any]:
    """Map a SQLAlchemy type to a JSON Schema fragment."""
    if isinstance(sa_type, SAEnum):
        values: list[str] = []
        if sa_type.enum_class is not None:
            values = [
                str(value.value if hasattr(value, "value") else value)
                for value in sa_type.enum_class
            ]
        else:
            values = [str(value) for value in sa_type.enums]
        return {"type": "string", "enum": sorted(values)}

    if isinstance(sa_type, String):
        schema: dict[str, Any] = {"type": "string"}
        if sa_type.length:
            schema["maxLength"] = sa_type.length
        return schema

    if isinstance(sa_type, Text):
        return {"type": "string"}

    if isinstance(sa_type, Boolean):
        return {"type": "boolean"}

    if isinstance(sa_type, Integer):
        return {"type": "integer"}

    if isinstance(sa_type, DateTime):
        return {"type": "string", "format": "date-time"}

    if isinstance(sa_type, Date):
        return {"type": "string", "format": "date"}

    if isinstance(sa_type, Float):
        return {"type": "number"}

    if isinstance(sa_type, Numeric):
        return {"type": "number"}

    if isinstance(sa_type, JSON):
        return {"type": "object"}

    if JSONB is not None and isinstance(sa_type, JSONB):
        return {"type": "object"}

    if UUID is not None and isinstance(sa_type, UUID):
        return {"type": "string", "format": "uuid"}

    if ARRAY is not None and isinstance(sa_type, ARRAY):
        item_schema = _type_to_schema(sa_type.item_type, report)
        return {"type": "array", "items": item_schema}

    report.record_unmapped_type(type(sa_type).__name__)
    return {"type": "string"}


def _apply_nullable(schema: dict[str, Any], nullable: bool) -> dict[str, Any]:
    """Apply nullability to a schema fragment."""
    if not nullable:
        return schema
    if "$ref" in schema:
        return {"anyOf": [schema, {"type": "null"}]}
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        if "null" not in schema_type:
            schema["type"] = [*schema_type, "null"]
        return schema
    if isinstance(schema_type, str):
        schema["type"] = [schema_type, "null"]
        return schema
    return {"anyOf": [schema, {"type": "null"}]}


def _column_schema(column: Any, report: CoverageReport) -> dict[str, Any]:
    """Build a schema fragment for a column."""
    schema = _type_to_schema(column.type, report)
    if column.comment:
        schema["description"] = str(column.comment)
    return _apply_nullable(schema, column.nullable)


def _relationship_schema(
    relationship: RelationshipProperty,
    options: SchemaOptions,
    report: CoverageReport,
    ref_prefix: str,
    ref_suffix: str,
) -> Optional[dict[str, Any]]:
    """Build a schema fragment for a relationship."""
    related = relationship.mapper.class_
    ref = f"{ref_prefix}{related.__name__}{ref_suffix}"

    if options.relationships == "none":
        report.skipped_relationships += 1
        return None

    if options.relationships == "id-only":
        pk_columns = relationship.mapper.primary_key
        if len(pk_columns) == 1:
            item_schema = _type_to_schema(pk_columns[0].type, report)
        else:
            item_schema = {"type": "object", "description": "Composite primary key"}

        if relationship.uselist:
            return {"type": "array", "items": item_schema}
        return item_schema

    if options.relationships == "nested":
        if relationship.uselist:
            return {"type": "array", "items": {"$ref": ref}}
        return {"$ref": ref}

    report.skipped_relationships += 1
    return None


def _model_schema(
    model: type[DeclarativeBase],
    options: SchemaOptions,
    report: CoverageReport,
    ref_prefix: str,
    ref_suffix: str,
) -> dict[str, Any]:
    """Generate a JSON Schema object for a SQLAlchemy model."""
    mapper = sa_inspect(model)
    properties: dict[str, Any] = {}
    required: list[str] = []

    column_props = [
        prop
        for prop in mapper.attrs
        if isinstance(prop, ColumnProperty) and prop.columns
    ]
    for prop in sorted(column_props, key=lambda p: p.key):
        column = prop.columns[0]
        properties[prop.key] = _column_schema(column, report)
        if not column.nullable and column.default is None and column.server_default is None:
            required.append(prop.key)

    if options.relationships != "none" and options.max_depth > 0:
        relationships = sorted(mapper.relationships, key=lambda r: r.key)
        for relationship in relationships:
            schema = _relationship_schema(
                relationship, options, report, ref_prefix, ref_suffix
            )
            if schema is not None:
                properties[relationship.key] = schema

    schema: dict[str, Any] = {
        "title": model.__name__,
        "type": "object",
        "properties": properties,
    }

    doc = getattr(model, "__doc__", None)
    if doc:
        schema["description"] = " ".join(doc.strip().split())
    if required:
        schema["required"] = sorted(required)
    return schema


def _render_report(report: CoverageReport) -> None:
    """Render the coverage report as a table."""
    table = Table(title="Schema Coverage", show_header=True, header_style="bold")
    table.add_column("Category")
    table.add_column("Details")

    if report.unmapped_types:
        unmapped = ", ".join(
            f"{name} ({count})" for name, count in sorted(report.unmapped_types.items())
        )
    else:
        unmapped = "None"

    table.add_row("Unmapped types", unmapped)
    table.add_row("Skipped relationships", str(report.skipped_relationships))
    if report.skipped_models:
        table.add_row("Skipped models", ", ".join(report.skipped_models))
    else:
        table.add_row("Skipped models", "None")

    console.print()
    console.print(table)


@app.command()
def generate(
    module: Annotated[
        Optional[str],
        typer.Option(
            "--module",
            "-m",
            help="Module path to import and scan for models.",
        ),
    ] = None,
    file: Annotated[
        Optional[Path],
        typer.Option(
            "--file",
            "-f",
            help="File path to the models module (used when name conflicts).",
            dir_okay=False,
            readable=True,
        ),
    ] = None,
    output: Annotated[
        Path,
        typer.Option(
            "--out",
            "-o",
            help="Output file path (combined) or directory (split).",
        ),
    ] = DEFAULT_OUTPUT,
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            help="Schema output format: combined or split.",
        ),
    ] = "combined",
    relationships: Annotated[
        str,
        typer.Option(
            "--relationships",
            help="Relationship mode: none, id-only, or nested.",
        ),
    ] = "nested",
    max_depth: Annotated[
        int,
        typer.Option(
            "--max-depth",
            help="Maximum relationship depth for nested mode.",
        ),
    ] = 1,
    schema_id_base: Annotated[
        str,
        typer.Option(
            "--schema-id-base",
            help="Base URL used for schema $id values.",
        ),
    ] = DEFAULT_SCHEMA_ID_BASE,
) -> None:
    """Generate JSON Schema docs for catalog store models."""
    if module is None and file is None:
        file = DEFAULT_MODULE_FILE
    if module is None and file is None:
        raise typer.BadParameter("Provide --module or --file")

    options = SchemaOptions(
        relationships=relationships,
        max_depth=max_depth,
        output_format=output_format,
        schema_id_base=schema_id_base,
    )

    report = CoverageReport()

    if module:
        from catalog.store.database import Base as StoreBase

        base: type[DeclarativeBase] = StoreBase
        importlib.import_module(module)
        models = _discover_models_from_registry(module, base)
    else:
        if file is None:
            raise typer.BadParameter("Provide --module or --file")
        if not file.exists():
            raise typer.BadParameter(f"File not found: {file}")
        from catalog.store import database as store_database

        base = _create_isolated_base()
        original_base = store_database.Base
        store_database.Base = base
        try:
            module_name = f"schema_gen_{file.stem}"
            loaded_module = _load_module_from_file(file, module_name)
        finally:
            store_database.Base = original_base
        models = _discover_models_from_module(loaded_module, base)

    if not models:
        logger.warning("No models discovered. Nothing to emit.")
        return

    logger.info("Discovered %s models", len(models))

    if options.output_format not in {"combined", "split"}:
        raise typer.BadParameter("--format must be combined or split")

    if options.relationships not in {"none", "id-only", "nested"}:
        raise typer.BadParameter("--relationships must be none, id-only, or nested")

    defs: dict[str, Any] = {}
    if options.output_format == "combined":
        ref_prefix = "#/$defs/"
        ref_suffix = ""
    else:
        ref_prefix = ""
        ref_suffix = ".schema.json"

    for model in models:
        defs[model.__name__] = _model_schema(
            model, options, report, ref_prefix, ref_suffix
        )

    if options.output_format == "combined":
        schema = {
            "$schema": DEFAULT_SCHEMA_DRAFT,
            "$id": f"{options.schema_id_base}/catalog-store.json",
            "title": "Catalog Store Models",
            "$defs": {name: defs[name] for name in sorted(defs)},
        }
        output_path = output
        if output_path.is_dir():
            output_path = output_path / "catalog-store-schema.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(schema, indent=2, sort_keys=True))
        logger.info("Wrote combined schema to %s", output_path)
    else:
        output.mkdir(parents=True, exist_ok=True)
        for name in sorted(defs):
            schema = {
                "$schema": DEFAULT_SCHEMA_DRAFT,
                "$id": f"{options.schema_id_base}/{name}.schema.json",
                "title": name,
                **defs[name],
            }
            output_path = output / f"{name}.schema.json"
            output_path.write_text(json.dumps(schema, indent=2, sort_keys=True))
        logger.info("Wrote %s schema files to %s", len(defs), output)

    _render_report(report)


if __name__ == "__main__":
    app()
