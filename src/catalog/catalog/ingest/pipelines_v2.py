"""catalog.ingest.pipelines_v2 - V2 Dataset ingestion pipeline.

V2 ingestion with resilient chunking and embedding prefixes.
Designed to match TypeScript QMD system behavior for retrieval parity.

Pipeline flow:
1. Source-specific pre-persist transforms
2. PersistenceTransform (upsert to documents table + documents_fts)
3. Source-specific post-persist transforms
4. ResilientSplitter (token-based with char fallback)
5. ChunkPersistenceTransform (persist chunks to FTS)
6. EmbeddingPrefixTransform (add Nomic-style prefixes)
7. embed_model (generate embeddings)
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
from catalog.ingest.schemas import DatasetIngestConfig, IngestResult
from catalog.ingest.sources import BaseSource, create_source
from catalog.store.database import get_session
from catalog.store.dataset import DatasetService
from catalog.store.session_context import use_session
from catalog.store.vector import VectorStoreManager
from catalog.transform import EmbeddingPrefixTransform, ResilientSplitter
from catalog.transform.llama import ChunkPersistenceTransform, PersistenceTransform

__all__ = [
    "DatasetIngestPipelineV2",
]

logger = get_logger(__name__)


class DatasetIngestPipelineV2(BaseModel):
    """V2 ingestion with resilient chunking and embedding prefixes.

    This pipeline provides feature parity with the TypeScript QMD system:
    - Resilient token-based chunking with char fallback
    - Nomic-style embedding prefixes for improved retrieval
    - Configurable via RAGv2Settings

    Entry points:
        - ingest_dataset(config) - Takes config as argument
        - ingest() - Uses self.ingest_config

    Attributes:
        ingest_config: Configuration for ingestion. Required for ingest().
        embed_model: Embedding model for generating vectors.
        resilient_embedding: Whether to use fallback on embedding errors.
    """

    ingest_config: Optional[DatasetIngestConfig] = None
    embed_model: Optional[Any] = None  # BaseEmbedding, but Any for Pydantic compat
    resilient_embedding: bool = Field(default=True)

    model_config = {"arbitrary_types_allowed": True}

    @cached_property
    def source(self) -> BaseSource:
        """Create the source from self.ingest_config."""
        return create_source(self.ingest_config)

    @cached_property
    def _settings(self):
        """Get RAG v2 settings."""
        return get_settings().rag_v2

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
        force: bool = False,
    ) -> IngestionPipeline:
        """Build the v2 ingestion pipeline.

        Args:
            dataset_id: Database ID of the dataset.
            dataset_name: Name of the dataset.
            vector_manager: Vector store manager for embeddings.
            source_transforms: Tuple of (pre-persist, post-persist) transforms.
            force: Whether to force re-ingestion.

        Returns:
            Configured IngestionPipeline ready to run.
        """
        settings = self._settings

        # Document persistence transform
        persist = PersistenceTransform(
            dataset_id=dataset_id,
            force=force,
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

        # Create pipeline with docstore for deduplication
        docstore = SimpleDocumentStore()

        pipeline = IngestionPipeline(
            transformations=transformations,
            docstore=docstore,
            docstore_strategy=DocstoreStrategy.UPSERTS_AND_DELETE,
            vector_store=vector_manager.get_vector_store(),
        )

        # Load cached pipeline state if available
        load_pipeline(dataset_name, pipeline)

        return pipeline

    def ingest(self) -> IngestResult:
        """Ingest documents using v2 pipeline.

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

        logger.info(f"Starting v2 ingestion: {self.ingest_config.source_path}")

        result = IngestResult(
            dataset_id=0,
            dataset_name="",
            started_at=started_at,
        )

        with get_session() as session:
            with use_session(session):
                # Get or create dataset
                dataset = DatasetService.create_or_update(
                    session,
                    self.ingest_config.dataset_name,
                    source_type=self.source.type_name,
                    source_path=str(self.source.path),
                    catalog_name=self.ingest_config.catalog_name,
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
                source_transforms = self.source.get_transforms(dataset_id=dataset.id)

                # Build and run pipeline
                pipeline = self.build_pipeline(
                    dataset_id=dataset.id,
                    dataset_name=dataset.name,
                    vector_manager=vector_manager,
                    source_transforms=source_transforms,
                    force=self.ingest_config.force,
                )

                logger.info(
                    f"Running {len(self.source.documents)} documents through v2 pipeline"
                )
                nodes = pipeline.run(documents=self.source.documents)

                # Collect statistics from transforms
                persist_transform = None
                chunk_persist_transform = None
                for t in pipeline.transformations:
                    if isinstance(t, PersistenceTransform):
                        persist_transform = t
                    elif isinstance(t, ChunkPersistenceTransform):
                        chunk_persist_transform = t

                if persist_transform:
                    result.documents_created = persist_transform.stats.created
                    result.documents_updated = persist_transform.stats.updated
                    result.documents_skipped = persist_transform.stats.skipped
                    result.documents_failed = persist_transform.stats.failed
                    result.errors = list(persist_transform.stats.errors)

                if chunk_persist_transform:
                    result.chunks_created = chunk_persist_transform.stats.created

                result.documents_read = len(self.source.documents)
                result.dataset_id = dataset.id
                result.dataset_name = dataset.name
                result.vectors_inserted = len(nodes) if nodes else 0

                # Persist state
                vector_manager.persist_vector_store()
                persist_pipeline(dataset.name, pipeline)

                result.completed_at = datetime.now(tz=timezone.utc)

                logger.info(
                    f"V2 ingestion complete: "
                    f"created={result.documents_created}, "
                    f"updated={result.documents_updated}, "
                    f"skipped={result.documents_skipped}, "
                    f"failed={result.documents_failed}, "
                    f"chunks={result.chunks_created}, "
                    f"vectors={result.vectors_inserted}"
                )

                return result

    def ingest_dataset(self, config: DatasetIngestConfig) -> IngestResult:
        """Ingest documents using the provided config.

        Creates a new pipeline instance with the given config and runs ingestion.

        Args:
            config: Dataset ingestion configuration.

        Returns:
            IngestResult with statistics about the operation.
        """
        pipeline = DatasetIngestPipelineV2(
            ingest_config=config,
            embed_model=self.embed_model,
            resilient_embedding=self.resilient_embedding,
        )
        return pipeline.ingest()
