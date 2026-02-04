"""catalog.ingest.pipelines - Dataset ingestion pipeline.

Provides DatasetIngestPipeline for ingesting documents from sources
into the catalog, persisting them to the database and updating
derived indexes (FTS, vector).

Pipeline flow (via LlamaIndex IngestionPipeline):
1. Source-specific pre-persist transforms (e.g. FrontmatterTransform)
2. PersistenceTransform (upsert to documents table + documents_fts)
3. Source-specific post-persist transforms (e.g. LinkResolution, parsing)
4. SentenceSplitter (chunk for embedding)
5. embed_model (generate embeddings)

Change detection uses PersistenceTransform's SHA-256 content hash
against the database. LlamaIndex's docstore provides a supplementary
cache layer when loaded from disk.
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from pydantic import BaseModel, Field

from agentlayer.logging import get_logger, configure_logging
from llama_index.core.ingestion import DocstoreStrategy, IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core import Document

from catalog.embedding import get_embed_model
from catalog.ingest.cache import clear_cache, load_pipeline, persist_pipeline
from catalog.ingest.job import DatasetJob
from catalog.ingest.schemas import IngestResult, DatasetIngestConfig
from catalog.integrations.obsidian import IngestObsidianConfig
from catalog.ingest.sources import BaseSource, create_source
from catalog.store.database import get_session
from catalog.store.dataset import DatasetInfo, DatasetService, normalize_dataset_name
from catalog.store.fts import create_fts_table
from catalog.store.fts_chunk import create_chunks_fts_table
from catalog.store.session_context import use_session
from catalog.transform.llama import (
    ChunkPersistenceTransform,
    PersistenceTransform,
)

if TYPE_CHECKING:
    from llama_index.core.embeddings import BaseEmbedding

__all__ = [
    "DatasetIngestPipeline",
]

logger = get_logger(__name__)


class IngestedDataset(BaseModel):
    dataset: DatasetInfo
    nodes: list[Document]
class DatasetIngestPipeline(BaseModel):
    """Dataset ingestion pipeline.
    Interface:
        - documents

    Entry points:
        - ingest_dataset
        - ingest_from_config
    """
    ingest_config: DatasetIngestConfig
    embed_model: Optional[BaseEmbedding] = Field(default_factory=get_embed_model)
    chunk_size: Optional[int] = Field(default=768)
    chunk_overlap: Optional[int] = Field(default=96)

    def create_dataset(self):
        """Create a new dataset in the catalog and populate it with documents."""
        started_at = datetime.now(tz=timezone.utc)

        logger.info(
            f"Starting ingestion: {self.ingest_config.source_path}"
        )

        result = IngestResult(
            dataset_id=0,
            dataset_name="",
            started_at=started_at,
        )

        with get_session() as session:
            with use_session(session):
                engine = session.get_bind()
                if engine is not None:
                    create_fts_table(engine)  # type: ignore
                    create_chunks_fts_table(engine)  # type: ignore

                dataset = DatasetService.create_or_update(
                    session,
                    self.ingest_config.dataset_name,
                    source_type=self.source.type_name,
                    source_path=str(self.source.path),
                )

                persist = PersistenceTransform(
                    dataset_id=dataset.id,
                    force=self.ingest_config.force,
                )
                chunk_persist = ChunkPersistenceTransform(
                    dataset_name=dataset.name,
                )
                if self.ingest_config.force:
                    logger.info(f"Force mode: clearing cache for dataset '{dataset.name}'")
                    clear_cache(self.cache_key(dataset.name))

                # Grab any source-specific transformations to apply pre- or post-persistence
                source_transforms = self.source.get_transforms(dataset_id=dataset.id)
                transformations = [
                    *source_transforms[0],
                    persist,
                    *source_transforms[1],
                    # chunk_persist,
                ]

                ingest_pipeline = IngestionPipeline(
                    transformations=transformations,
                    docstore=self.docstore,
                    docstore_strategy=DocstoreStrategy.UPSERTS_AND_DELETE,
                )
                load_pipeline(self.cache_key(dataset.name), ingest_pipeline)

                logger.info(f"Running {len(self.source.documents)} documents through pipeline")
                nodes = ingest_pipeline.run(documents=self.source.documents)

                persist_pipeline(self.cache_key(dataset.name), ingest_pipeline)

                result.documents_created = persist.stats.created
                result.documents_updated = persist.stats.updated
                result.documents_skipped = persist.stats.skipped
                result.documents_failed = persist.stats.failed
                result.errors = list(persist.stats.errors)
                result.chunks_created = chunk_persist.stats.created
                result.documents_read = len(self.source.documents)
                result.dataset_id = dataset.id
                result.dataset_name = dataset.name

                return result, dataset, nodes

    def cache_key(self, dataset_name) -> str:
        return f"{dataset_name}"

    @cached_property
    def docstore(self) -> SimpleDocumentStore:
        """Create the document store from the ingest configuration."""
        return SimpleDocumentStore()

    @cached_property
    def source(self) -> BaseSource:
        """Create the source from the ingest configuration."""
        return create_source(self.ingest_config)

    def ingest(self) -> IngestResult:
        """Ingest documents from a local directory, and extracts metadata."""

        result, dataset, documents = self.create_dataset()
        breakpoint()
        splitter = SentenceSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        # Handle "forced" ingestion, which will affect both ingestion passes
        from catalog.store.vector import VectorStoreManager
        vector_manager = VectorStoreManager()

        if self.ingest_config.force:
            deleted = vector_manager.delete_by_dataset(dataset.name)
            if deleted > 0:
                logger.info(f"Cleared {deleted} vectors for dataset '{dataset.name}'")

        if self.embed_model is None:
            self.embed_model = get_embed_model()

        # Grab any source-specific transformations to apply pre- or post-persistence
        transformations = [
            splitter,
            self.embed_model,
        ]

        ingest_pipeline = IngestionPipeline(
            transformations=transformations,
            docstore=self.docstore,
            docstore_strategy=DocstoreStrategy.UPSERTS_AND_DELETE,
            vector_store=vector_manager.get_vector_store()
        )

        # Reload previous docstore state so LlamaIndex can skip
        # unchanged documents before they reach any transforms.
        load_pipeline(self.cache_key(dataset.name), ingest_pipeline)

        logger.info(f"Running {len(documents)} documents through pipeline")
        nodes = ingest_pipeline.run(documents=documents)

        persist_pipeline(self.cache_key(dataset.name), ingest_pipeline)

        result.vectors_inserted = len(nodes) if nodes else 0

        vector_manager.persist_vector_store()

        result.completed_at = datetime.now(tz=timezone.utc)

        logger.info(
            f"Ingestion complete: "
            f"created={result.documents_created}, "
            f"updated={result.documents_updated}, "
            f"skipped={result.documents_skipped}, "
            f"failed={result.documents_failed}, "
            f"chunks={result.chunks_created}, "
            f"vectors={result.vectors_inserted}"
        )

        return result

    @classmethod
    def from_config(cls, config_path: Path) -> DatasetIngestPipeline:
        """Create an ingestion job from a YAML configuration file.

        Loads the YAML via Hydra, validates into a DatasetJob, then runs
        the full ingestion pipeline with the configured source, embedding
        model, and pipeline caching settings.

        Args:
            config_path: Path to the YAML configuration file.

        Returns:
            IngestResult with statistics about the operation.
        """
        job: DatasetJob = DatasetJob.from_yaml(config_path)
        ingest_config: "DatasetIngestConfig" = job.to_ingest_config()
        embed_model: "BaseEmbedding" = job.create_embed_model()
        chunk_size: int = job.pipeline.splitter_chunk_size
        chunk_overlap: int = job.pipeline.splitter_chunk_overlap

        return cls(
            ingest_config=ingest_config,
            embed_model=embed_model,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
         )

if __name__ == "__main__":
    import sys
    configure_logging(level="DEBUG")
    if len(sys.argv) < 2:
        print("Usage: python -m catalog.ingest.pipelines <source_dir_or_yaml>")
        sys.exit(1)

    from pathlib import Path

    target = Path(sys.argv[1])


    if target.suffix in (".yaml", ".yml"):
        pipeline = DatasetIngestPipeline.from_config(target)
    else:

        config = IngestObsidianConfig(source_path=target)
        pipeline = DatasetIngestPipeline(ingest_config=config)

    result = pipeline.ingest()

    print(result.model_dump_json(indent=2))
