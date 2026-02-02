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
from pathlib import Path
from typing import TYPE_CHECKING

from agentlayer.logging import get_logger, configure_logging
from llama_index.core.ingestion import DocstoreStrategy, IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.storage.docstore import SimpleDocumentStore

from catalog.embedding import get_embed_model
from catalog.ingest.cache import clear_cache, load_pipeline, persist_pipeline
from catalog.ingest.job import DatasetJob
from catalog.ingest.schemas import IngestResult, DatasetIngestConfig
from catalog.integrations.obsidian import IngestObsidianConfig
from catalog.ingest.sources import create_source
from catalog.store.database import get_session
from catalog.store.dataset import DatasetService, normalize_dataset_name
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



class DatasetIngestPipeline:
    def ingest_dataset(self,
                    ingest_config: DatasetIngestConfig,
                    embed_model: "BaseEmbedding" = None,
                    chunk_size: int = 768,
                    chunk_overlap: int = 96
                       ) -> IngestResult:
        """Ingest documents from a local directory, and extracts metadata."""
        started_at = datetime.now(tz=timezone.utc)
        normalized_name = normalize_dataset_name(ingest_config.dataset_name)

        logger.info(
            f"Starting config-driven ingestion: {ingest_config.source_path} -> {normalized_name}"
        )

        source = create_source(ingest_config)

        result = IngestResult(
            dataset_id=0,
            dataset_name=normalized_name,
            started_at=started_at,
        )

        with get_session() as session:
            with use_session(session):
                engine = session.get_bind()
                if engine is not None:
                    create_fts_table(engine)  # type: ignore
                    create_chunks_fts_table(engine)  # type: ignore

                dataset_id = DatasetService.create_or_update(
                    session,
                    ingest_config.dataset_name,
                    source_type=source.type_name,
                    source_path=str(source.path),
                )
                result.dataset_id = dataset_id

                persist = PersistenceTransform(
                    dataset_id=dataset_id,
                    force=ingest_config.force,
                )
                chunk_persist = ChunkPersistenceTransform(
                    dataset_name=normalized_name,
                )

                splitter = SentenceSplitter(
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
                # Handle "forced" ingestion, which will affect both ingestion passes
                from catalog.store.vector import VectorStoreManager
                vector_manager = VectorStoreManager()

                if ingest_config.force:
                    logger.info(f"Force mode: clearing cache for dataset '{normalized_name}'")
                    clear_cache(normalized_name)
                    deleted = vector_manager.delete_by_dataset(normalized_name)
                    if deleted > 0:
                        logger.info(f"Cleared {deleted} vectors for dataset '{normalized_name}'")

                if embed_model is None:
                    embed_model = get_embed_model()

                # Grab any source-specific transformations to apply pre- or post-persistence
                source_transforms = source.get_transforms(dataset_id=dataset_id)
                transformations = [
                    *source_transforms[0],
                    persist,
                    #
                    # chunk_persist,
                    *source_transforms[1],
                    splitter,
                    #embed_model commented out for speed of fixing de-dupe issue
                ]

                ingest_pipeline = IngestionPipeline(
                    transformations=transformations,
                    docstore=SimpleDocumentStore(),
                    docstore_strategy=DocstoreStrategy.UPSERTS_AND_DELETE,
                    #vector_store=vector_manager.get_vector_store(),  commented out for speed of fixing de-dupe issue
                )

                # Reload previous docstore state so LlamaIndex can skip
                # unchanged documents before they reach any transforms.
                load_pipeline(normalized_name, ingest_pipeline)

                logger.info(f"Running {len(source.documents)} documents through pipeline")
                nodes = ingest_pipeline.run(documents=source.documents)
                persist_pipeline(normalized_name, ingest_pipeline)

                result.documents_created = persist.stats.created
                result.documents_updated = persist.stats.updated
                result.documents_skipped = persist.stats.skipped
                result.documents_failed = persist.stats.failed
                result.errors = list(persist.stats.errors)
                result.chunks_created = chunk_persist.stats.created
                result.documents_read = len(source.documents)

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

    def ingest_from_config(self, config_path: Path) -> IngestResult:
        """Run an ingestion job from a YAML configuration file.

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

        return self.ingest_dataset(
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
    pipeline = DatasetIngestPipeline()

    if target.suffix in (".yaml", ".yml"):
        result = pipeline.ingest_from_config(target)
    else:
        config = IngestObsidianConfig(source_path=target)
        result = pipeline.ingest_dataset(config)

    print(result.model_dump_json(indent=2))
