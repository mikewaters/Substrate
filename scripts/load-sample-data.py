#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "ontology",
#   "sqlalchemy",
#   "typer",
#   "rich"
# ]
# ///
"""
Initialize with sample taxonnomy and topic data
"""

import asyncio
from pathlib import Path

import typer
from ontologizer.information.services import (
    TaxonomyService,
    TopicTaxonomyService,
)
from rich.console import Console

from ontologizer.settings import get_settings
from ontologizer.relational.database import (
    create_all_tables_async,
    drop_all_tables_async,
    get_async_session,
)
from ontologizer.loader.loader import load_yaml_dataset
from ontologizer.relational.services import TopicSuggestionService

app = typer.Typer()
console = Console()

DATA_PATH = (
    Path(__file__).parent.parent
    / "src"
    / "ontology"
    / "database"
    / "data"
    / "sample_taxonomies.yaml"
)


# @app.command()
async def main(
    freshy: bool = True,
):
    if freshy:
        console.print("Dropping `information` tables")

        await drop_all_tables_async()
        await create_all_tables_async()

        console.print(f"Using: {str(DATA_PATH)}")
        console.print(f"Using: {get_settings().database.db_path}")
        async with get_async_session() as session:
            await load_yaml_dataset(str(DATA_PATH), session)

    async with get_async_session() as session:
        taxonomy_service = TaxonomyService(session=session)
        topic_service = TopicTaxonomyService(session=session)
        classifier_service = TopicSuggestionService(session=session)

        for taxonomy in await taxonomy_service.list():
            # breakpoint()
            console.print(f"For taxonomy {taxonomy.identifier}:")
            for topic in await topic_service.list_topics_by_taxonomy_identifier(
                taxonomy.identifier
            ):
                console.print(f"\t{topic.identifier} {topic.title}")
            from ontologizer.schema import TopicSuggestionRequest

            response = await classifier_service.suggest_topics(
                TopicSuggestionRequest(
                    text="LLM APIs",
                    taxonomy_id=taxonomy.id,
                    limit=3,
                )
            )
            console.print(response)


if __name__ == "__main__":
    # app()
    asyncio.run(main())
