"""catalog.ingest.pipelines - Dataset ingestion pipeline (DEPRECATED).

.. deprecated::
    Use ``catalog.ingest.pipelines_v2.DatasetIngestPipelineV2`` instead.
    This module will be removed in a future release.

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
against the database. Unchanged documents are skipped but still passed
through for vector embedding if needed.
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

from catalog.store.vector import VectorStoreManager
from catalog.embedding import get_embed_model
from catalog.ingest.cache import clear_cache
from catalog.ingest.job import DatasetJob
from catalog.ingest.schemas import IngestResult, DatasetIngestConfig
from catalog.ingest.sources import BaseSource, create_source
from catalog.store.database import get_session
from catalog.store.dataset import DatasetInfo, DatasetService, normalize_dataset_name
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

class DatasetIngestPipeline(BaseModel):
    """Dataset ingestion pipeline (DEPRECATED).

    .. deprecated::
        Use ``DatasetIngestPipelineV2`` from ``catalog.ingest.pipelines_v2`` instead.

    Entry points:
        - ingest_dataset(config) - Takes config as argument
        - ingest() - Uses self.ingest_config

    Attributes:
        ingest_config: Optional configuration. Required for ingest(), not for ingest_dataset().
        embed_model: Embedding model for generating vectors.
        chunk_size: Size of text chunks for embedding.
        chunk_overlap: Overlap between adjacent chunks.
    """
    ingest_config: DatasetIngestConfig
    embed_model: Optional[BaseEmbedding] = Field(default_factory=get_embed_model)
    chunk_size: Optional[int] = Field(default=768)
    chunk_overlap: Optional[int] = Field(default=96)

    @cached_property
    def source(self) -> BaseSource:
        """Create the source from self.ingest_config."""
        #if self.ingest_config is None:
        #    raise ValueError("ingest_config is required when using source property")
        return create_source(self.ingest_config)

    def _cache_key(self, dataset_name: str) -> str:
        """Generate a cache key for a dataset."""
        return f"{dataset_name}"

    def ingest(self) -> IngestResult:
        """Ingest documents from a local directory, and extracts metadata.

        Requires self.ingest_config to be set. Use ingest_dataset(config) to
        pass config as an argument.

        Returns:
            IngestResult with statistics about the operation.

        Raises:
            ValueError: If ingest_config is not set.
        """
        if self.ingest_config is None:
            raise ValueError("ingest_config is required. Use ingest_dataset(config) instead.")

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
                # Get a reference to this source's dataset
                non_normalized_source_name = self.ingest_config.dataset_name
                dataset = DatasetService.create_or_update(
                    session,
                    non_normalized_source_name,
                    source_type=self.source.type_name,
                    source_path=str(self.source.path),
                    catalog_name=self.ingest_config.catalog_name,
                )

                # Handle "forced" ingestion, which will affect both ingestion passes
                vector_manager = VectorStoreManager()
                if self.ingest_config.force:
                    deleted = vector_manager.delete_by_dataset(dataset.name)
                    if deleted > 0:
                        logger.info(f"Force mode: clearing cache for dataset '{dataset.name}'")
                    clear_cache(self._cache_key(dataset.name))

                if self.embed_model is None:
                    self.embed_model = get_embed_model()

                # Define the pipeline dependencies
                persist = PersistenceTransform(
                    dataset_id=dataset.id,
                    force=self.ingest_config.force,
                )
                chunk_persist = ChunkPersistenceTransform(
                    dataset_name=dataset.name,
                )
                splitter = SentenceSplitter(
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                )

                # Grab any source-specific transformations to apply pre- or post-persistence
                # :returns: two-tuple of (pre-persist, post-persist) transformations
                source_transforms = self.source.get_transforms(dataset_id=dataset.id)

                transformations = [
                    *source_transforms[0],
                    persist,
                    *source_transforms[1],
                    splitter,
                    chunk_persist,
                    self.embed_model,
                ]

                ingest_pipeline = IngestionPipeline(
                    transformations=transformations,
                    docstore=SimpleDocumentStore(),
                    # Use DUPLICATES_ONLY to prevent docstore from filtering documents.
                    # PersistenceTransform handles dedup via database hash comparison.
                    # We don't load cached docstore, so all docs flow through transforms.
                    docstore_strategy=DocstoreStrategy.DUPLICATES_ONLY,
                    vector_store=vector_manager.get_vector_store()
                )

                logger.info(f"Running {len(self.source.documents)} documents through pipeline")
                nodes = ingest_pipeline.run(documents=self.source.documents)

                result.documents_created = persist.stats.created
                result.documents_updated = persist.stats.updated
                result.documents_skipped = persist.stats.skipped
                result.documents_failed = persist.stats.failed
                result.errors = list(persist.stats.errors)
                result.chunks_created = chunk_persist.stats.created
                result.documents_read = len(self.source.documents)
                result.dataset_id = dataset.id
                result.dataset_name = dataset.name

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
    def from_job_config(cls, config_path: Path) -> DatasetIngestPipeline:
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
        print("Usage: python -m catalog.ingest.pipelines <source_dir_or_yaml> [--force]")
        sys.exit(1)

    from pathlib import Path

    force = "--force" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--force"]
    target = Path(args[0])

    if target.suffix in (".yaml", ".yml"):
        pipeline = DatasetIngestPipeline.from_job_config(target)
    else:
        from catalog.integrations.obsidian import IngestObsidianConfig
        config = IngestObsidianConfig(source_path=target, force=force, catalog_name='pkm')
        pipeline = DatasetIngestPipeline(ingest_config=config)

    result = pipeline.ingest()

    print(result.model_dump_json(indent=2))
