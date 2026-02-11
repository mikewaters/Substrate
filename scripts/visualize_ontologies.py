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
from typing import Annotated

from pathlib import Path
from sqlalchemy.orm import sessionmaker

from ontologizer.relational.database import Base
from ontologizer.information.services import (
    TopicTaxonomyService,
    TaxonomyService,
)
from ontologizer.loader.loader import load_yaml_dataset
from rich.console import Console
import typer
from tempfile import NamedTemporaryFile
from ontologizer.relational.database import get_engine

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


@app.command()
def get(
    taxonomy: Annotated[
        str | None,
        typer.Argument(help="Taxonomy to retrieve (format: 'tx:entity')"),
    ] = None,
    topic: Annotated[
        str | None,
        typer.Argument(
            help="Optional topic to filter by (format: 'namespace:entity')",
        ),
    ] = None,
    delete: Annotated[
        bool | None,
        typer.Option(
            "--delete",
            "-d",
            help="Delete the database file after visualization",
        ),
    ] = True,
):
    with NamedTemporaryFile(suffix="db", delete_on_close=False) as fp:
        console.print(f"Using database: {fp.name}")

        # Note: Using Advanced-Alchemy config now
        # The temp database path is set via environment if needed

        engine = get_engine()
        # For sync operations, use the sync_engine
        sync_engine = engine.sync_engine
        Base.metadata.create_all(sync_engine)

        connection = sync_engine.connect()
        transaction = connection.begin()

        SessionFactory = sessionmaker(bind=connection)
        session = SessionFactory()

        load_yaml_dataset(str(DATA_PATH), session)

        taxonomy_service = TaxonomyService(session=session)
        topic_service = TopicTaxonomyService(session=session)

        tree = topic_service.get_tree("tech:ai")

        # session.commit()
        if taxonomy:
            # import pdb; pdb.set_trace()
            taxonomy_instance = taxonomy_service.get_by_ident(taxonomy)
            console.print(taxonomy_instance)

            # for topic in topic_service.list_topics_by_taxonomy_identifier(taxonomy):
            #     console.print(topic)

        session.close()
        transaction.rollback()
        connection.close()

        Base.metadata.drop_all(engine)
        engine.dispose()


if __name__ == "__main__":
    app()
