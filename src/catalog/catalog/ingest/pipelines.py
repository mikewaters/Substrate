"""catalog.ingest.pipelines - Dataset ingestion pipeline.

Resilient chunking and embedding prefixes, designed to match TypeScript
QMD system behavior for retrieval parity.

Change detection is handled by LlamaIndex's docstore, which uses
SHA256(text + metadata) to detect changes. This catches frontmatter-only
changes that the old body-only hash missed. The docstore is persisted
between runs so only new/changed documents are reprocessed.

Deletion detection uses DocstoreStrategy.UPSERTS_AND_DELETE: documents
present in the docstore but not in the current batch are removed from
the docstore, vector store, and marked inactive in the SQLite DB.

Pipeline flow:
1. LlamaIndex docstore filters unchanged documents (upstream)
2. Source-specific pre-persist transforms
3. PersistenceTransform (upsert to documents table + documents_fts)
4. Source-specific post-persist transforms
5. ResilientSplitter (token-based with char fallback)
6. ChunkPersistenceTransform (persist chunks to FTS)
7. EmbeddingPrefixTransform (add Nomic-style prefixes)
8. embed_model (generate embeddings)
9. Post-pipeline deletion sync (deactivate removed docs in SQLite)
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import cached_property
from typing import Any, Optional

from agentlayer.logging import get_logger
from llama_index.core.ingestion import DocstoreStrategy, IngestionPipeline
from llama_index.core.storage.docstore import SimpleDocumentStore
from pydantic import BaseModel, Field

from catalog.core.settings import get_settings
from catalog.embedding import get_embed_model
from catalog.ingest.cache import (
    clear_cache,
    load_pipeline,
    persist_pipeline,
)
from catalog.ingest.schemas import IngestResult
from catalog.ingest.sources import BaseSource, create_source, DatasetSourceConfig
from catalog.store.database import get_session
from catalog.store.dataset import DatasetService
from catalog.store.fts import FTSManager
from catalog.store.repositories import DatasetRepository, DocumentRepository
from catalog.store.session_context import use_session
from catalog.store.vector import VectorStoreManager
from catalog.transform import EmbeddingPrefixTransform, ResilientSplitter
from catalog.transform.llama import ChunkPersistenceTransform, PersistenceTransform

__all__ = [
    "DatasetIngestPipeline",
]

logger = get_logger(__name__)


class DatasetIngestPipeline(BaseModel):
    """Dataset ingestion with resilient chunking and embedding prefixes.

    This pipeline provides feature parity with the TypeScript QMD system:
    - Resilient token-based chunking with char fallback
    - Nomic-style embedding prefixes for improved retrieval
    - Configurable via RAGSettings

    Entry points:
        - ingest_dataset(config) - Takes config as argument
        - ingest() - Uses self.ingest_config

    Attributes:
        ingest_config: Configuration for ingestion. Required for ingest().
        embed_model: Embedding model for generating vectors.
        resilient_embedding: Whether to use fallback on embedding errors.
    """

    ingest_config: Optional[DatasetSourceConfig] = None
    embed_model: Optional[Any] = None  # BaseEmbedding, but Any for Pydantic compat
    resilient_embedding: bool = Field(default=True)

    model_config = {"arbitrary_types_allowed": True}

    @cached_property
    def source(self) -> BaseSource:
        """Create the source from self.ingest_config."""
        return create_source(self.ingest_config)

    @cached_property
    def _settings(self):
        """Get RAG settings."""
        return get_settings().rag

    def _cache_key(self, dataset_name: str) -> str:
        """Generate a cache key for a dataset."""
        return f"{dataset_name}"

    def _get_embed_model(self) -> "BaseEmbedding":
        """Get embedding model, using resilient wrapper if enabled."""
        if self.embed_model is not None:
            return self.embed_model
        return get_embed_model(resilient=self.resilient_embedding)

    def build_pipeline(
        self,
        dataset_id: int,
        dataset_name: str,
        vector_manager: VectorStoreManager,
        source_transforms: tuple[list, list],
        incremental: bool = False,
    ) -> IngestionPipeline:
        """Build the ingestion pipeline.

        Args:
            dataset_id: Database ID of the dataset.
            dataset_name: Name of the dataset.
            vector_manager: Vector store manager for embeddings.
            source_transforms: Tuple of (pre-persist, post-persist) transforms.
            incremental: If True, use UPSERTS strategy instead of
                UPSERTS_AND_DELETE to avoid deleting unchanged documents
                that are absent from the partial batch.

        Returns:
            Configured IngestionPipeline ready to run.
        """
        settings = self._settings

        # Document persistence transform
        persist = PersistenceTransform(
            dataset_id=dataset_id,
        )

        # Resilient text chunking with fallback
        splitter = ResilientSplitter(
            chunk_size_tokens=settings.chunk_size,
            chunk_overlap_tokens=settings.chunk_overlap,
            chars_per_token=settings.chunk_chars_per_token,
            fallback_enabled=settings.chunk_fallback_enabled,
        )

        # Chunk persistence for FTS
        chunk_persist = ChunkPersistenceTransform(
            dataset_name=dataset_name,
        )

        # Embedding prefix for improved retrieval
        prefix_transform = EmbeddingPrefixTransform(
            prefix_template=settings.embed_prefix_doc,
        )

        # Embedding model
        embed_model = self._get_embed_model()

        # Build transformation chain
        transformations = [
            *source_transforms[0],  # Pre-persist source transforms
            persist,
            *source_transforms[1],  # Post-persist source transforms
            splitter,
            chunk_persist,
            prefix_transform,
            embed_model,
        ]

        # Create pipeline with docstore for change detection and deduplication.
        # LlamaIndex's docstore uses SHA256(text + metadata) for change detection,
        # which catches frontmatter-only changes that our old body-only hash missed.
        docstore = SimpleDocumentStore()
        vector_store = vector_manager.get_vector_store()

        # In incremental mode, use UPSERTS to avoid deleting docstore/vector
        # entries for documents not in the partial batch.
        if incremental:
            strategy = DocstoreStrategy.UPSERTS
        else:
            strategy = DocstoreStrategy.UPSERTS_AND_DELETE

        # Guard: UPSERTS_AND_DELETE silently downgrades to DUPLICATES_ONLY
        # without a vector store, losing upsert and deletion semantics.
        if vector_store is None and strategy == DocstoreStrategy.UPSERTS_AND_DELETE:
            raise ValueError(
                "Vector store is required for DocstoreStrategy.UPSERTS_AND_DELETE. "
                "Without it, LlamaIndex silently downgrades to DUPLICATES_ONLY."
            )

        pipeline = IngestionPipeline(
            transformations=transformations,
            docstore=docstore,
            docstore_strategy=strategy,
            vector_store=vector_store,
        )

        # Load cached pipeline state if available
        load_pipeline(dataset_name, pipeline)

        return pipeline

    def ingest(self) -> IngestResult:
        """Ingest documents using the pipeline.

        Uses resilient chunking and embedding prefixes for improved
        retrieval quality matching the TypeScript QMD system.

        Returns:
            IngestResult with statistics about the operation.

        Raises:
            ValueError: If ingest_config is not set.
        """
        if self.ingest_config is None:
            raise ValueError(
                "ingest_config is required. Use ingest_dataset(config) instead."
            )

        started_at = datetime.now(tz=timezone.utc)

        logger.info(f"Starting ingestion: {self.ingest_config.source_path}")

        result = IngestResult(
            dataset_id=0,
            dataset_name="",
            started_at=started_at,
        )

        with get_session() as session:
            with use_session(session):
                # Get or create dataset — use config fields (not self.source)
                # so source creation is deferred until after incremental
                # resolution below.
                dataset = DatasetService.create_or_update(
                    session,
                    self.ingest_config.dataset_name,
                    source_type=self.ingest_config.type_name,
                    source_path=str(self.ingest_config.source_path),
                    catalog_name=self.ingest_config.catalog_name,
                )

                # Resolve incremental flag to if_modified_since before
                # accessing self.source (which triggers file filtering).
                is_incremental = self.ingest_config.if_modified_since is not None
                if self.ingest_config.incremental and not is_incremental:
                    if dataset.last_ingested_at is not None:
                        self.ingest_config.if_modified_since = dataset.last_ingested_at
                        is_incremental = True
                        logger.info(
                            f"Incremental mode: filtering files modified since "
                            f"{dataset.last_ingested_at}"
                        )
                    else:
                        logger.info(
                            "Incremental mode: new dataset, running full ingestion"
                        )

                # Handle forced ingestion
                vector_manager = VectorStoreManager()
                if self.ingest_config.force:
                    deleted = vector_manager.delete_by_dataset(dataset.name)
                    if deleted > 0:
                        logger.info(
                            f"Force mode: cleared {deleted} vectors for "
                            f"dataset '{dataset.name}'"
                        )
                    clear_cache(self._cache_key(dataset.name))

                # Get source-specific transforms
                source_transforms = self.source.transforms(dataset_id=dataset.id)

                # Build and run pipeline
                pipeline = self.build_pipeline(
                    dataset_id=dataset.id,
                    dataset_name=dataset.name,
                    vector_manager=vector_manager,
                    source_transforms=source_transforms,
                    incremental=is_incremental,
                )

                source_docs = self.source.documents
                logger.info(
                    f"Running {len(source_docs)} documents through pipeline"
                )
                nodes = pipeline.run(documents=source_docs)

                # Collect statistics from transforms
                persist_transform = None
                chunk_persist_transform = None
                for t in pipeline.transformations:
                    if isinstance(t, PersistenceTransform):
                        persist_transform = t
                    elif isinstance(t, ChunkPersistenceTransform):
                        chunk_persist_transform = t

                # Deletion sync: mark documents not in the current batch
                # as inactive in our SQLite DB. LlamaIndex already handled
                # deletion in the docstore and vector store via
                # UPSERTS_AND_DELETE; this mirrors that to our DB.
                #
                # Skip in incremental mode: only a subset of files were
                # loaded, so missing docs are simply not-yet-modified,
                # not deleted.
                deactivated = 0
                if not is_incremental:
                    batch_paths = {
                        doc.metadata.get("relative_path", doc.id_)
                        for doc in source_docs
                    }
                    doc_repo = DocumentRepository()
                    deactivated = doc_repo.deactivate_missing(
                        dataset.id, batch_paths
                    )
                    if deactivated > 0:
                        # Clean up FTS entries for deactivated documents
                        fts = FTSManager()
                        active_paths = doc_repo.list_paths_by_parent(
                            dataset.id, active_only=True
                        )
                        all_paths = doc_repo.list_paths_by_parent(
                            dataset.id, active_only=False
                        )
                        removed_paths = all_paths - active_paths - batch_paths
                        for rpath in removed_paths:
                            removed_doc = doc_repo.get_by_path(dataset.id, rpath)
                            if removed_doc:
                                fts.delete(removed_doc.id)

                        logger.info(
                            f"Deletion sync: deactivated {deactivated} documents "
                            f"not in current batch"
                        )

                # Stamp last_ingested_at on the dataset
                ds_repo = DatasetRepository(session)
                dataset_orm = ds_repo.get_by_id(dataset.id)
                dataset_orm.last_ingested_at = datetime.now(tz=timezone.utc)

                session.flush()

                if persist_transform:
                    result.documents_created = persist_transform.stats.created
                    result.documents_updated = persist_transform.stats.updated
                    result.documents_failed = persist_transform.stats.failed
                    result.errors = list(persist_transform.stats.errors)

                if chunk_persist_transform:
                    result.chunks_created = chunk_persist_transform.stats.created

                result.documents_read = len(source_docs)
                result.dataset_id = dataset.id
                result.dataset_name = dataset.name
                result.vectors_inserted = len(nodes) if nodes else 0
                result.documents_deactivated = deactivated

                # Derive skipped count: docs in batch that weren't
                # created or updated were filtered by LlamaIndex's
                # docstore as unchanged.
                total_processed = (
                    (persist_transform.stats.created + persist_transform.stats.updated)
                    if persist_transform else 0
                )
                result.documents_skipped = len(source_docs) - total_processed

                # Persist state
                vector_manager.persist_vector_store()
                persist_pipeline(dataset.name, pipeline)

                result.completed_at = datetime.now(tz=timezone.utc)

                logger.info(
                    f"Ingestion complete: "
                    f"created={result.documents_created}, "
                    f"updated={result.documents_updated}, "
                    f"skipped={result.documents_skipped}, "
                    f"deactivated={result.documents_deactivated}, "
                    f"failed={result.documents_failed}, "
                    f"chunks={result.chunks_created}, "
                    f"vectors={result.vectors_inserted}"
                )

                return result

    def ingest_dataset(self, config: DatasetSourceConfig) -> IngestResult:
        """Ingest documents using the provided config.

        Creates a new pipeline instance with the given config and runs ingestion.

        Args:
            config: Dataset ingestion configuration.

        Returns:
            IngestResult with statistics about the operation.
        """
        pipeline = DatasetIngestPipeline(
            ingest_config=config,
            embed_model=self.embed_model,
            resilient_embedding=self.resilient_embedding,
        )
        return pipeline.ingest()

if __name__ == "__main__":
    import sys
    from agentlayer.logging import get_logger, configure_logging
    from catalog.integrations.obsidian import SourceObsidianConfig
    from catalog.integrations.heptabase import SourceHeptabaseConfig

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
        config = SourceHeptabaseConfig(source_path=target, force=force, catalog_name='pkm')
        pipeline = DatasetIngestPipeline(ingest_config=config)

    result = pipeline.ingest()

    print(result.model_dump_json(indent=2))
