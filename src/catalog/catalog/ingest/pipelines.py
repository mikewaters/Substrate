"""Ingest pipeline for indexing documents.

Provides the IngestPipeline class for ingesting documents from various
sources into the idx system, persisting them to the database and
updating derived indexes (FTS, vector).

Uses LlamaIndex's IngestionPipeline for document transformations with
PersistenceTransform handling database persistence and FTS indexing
as the final pipeline step. Uses ambient session via contextvars.

Pipeline flow:
1. TextNormalizerTransform (normalize whitespace, BOM, etc.)
2. PersistenceTransform (upsert to documents table + documents_fts)
3. MarkdownNodeParser (split into chunks)
4. ChunkPersistenceTransform (upsert chunks to chunks_fts)
5. SizeAwareChunkSplitter (split oversized nodes for embedding)
6. embed_model (generate embeddings via native vector_store integration)

Vector store integration uses LlamaIndex's native vector_store parameter
with DocstoreStrategy.UPSERTS for proper upsert semantics on document changes.
"""

from __future__ import annotations

import hashlib
from dataclasses import field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agentlayer.logging import get_logger, configure_logging
from llama_index.core import Document, Settings, SimpleDirectoryReader, VectorStoreIndex
from llama_index.core.extractors import KeywordExtractor, TitleExtractor
from llama_index.core.ingestion import DocstoreStrategy, IngestionPipeline
from llama_index.core.ingestion.pipeline import DocstoreStrategy
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.core.schema import BaseNode, TransformComponent
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.storage.docstore.duckdb import DuckDBDocumentStore
from llama_index.vector_stores.duckdb import DuckDBVectorStore

from catalog.embedding import get_embed_model
from catalog.ingest.cache import clear_cache, persist_documents
from catalog.ingest.schemas import IngestDirectoryConfig, IngestObsidianConfig, IngestResult, DatasetIngestConfig
from catalog.ingest.sources import create_source, create_reader
from catalog.store.database import get_session
from catalog.store.dataset import DatasetService, normalize_dataset_name
from catalog.store.fts import create_fts_table
from catalog.store.fts_chunk import create_chunks_fts_table
from catalog.store.session_context import use_session
from catalog.transform.frontmatter import FrontmatterTransform
from catalog.transform.llama import (
    ChunkPersistenceTransform,
    LinkResolutionTransform,
    PersistenceTransform,
    TextNormalizerTransform,
)
from catalog.transform.splitter import SizeAwareChunkSplitter


if TYPE_CHECKING:
    from llama_index.core.embeddings import BaseEmbedding

    from catalog.store.vector import VectorStoreManager

__all__ = [
    "IngestPipeline",
]

logger = get_logger(__name__)




class IngestPipeline:
    """Pipeline for ingesting documents from sources.

    Pipeline flow:
    1. TextNormalizerTransform - normalize whitespace, BOM, etc.
    2. PersistenceTransform - upsert to documents table + documents_fts
    3. MarkdownNodeParser - split into chunks (TextNodes)
    4. ChunkPersistenceTransform - upsert chunks to chunks_fts
    5. SizeAwareChunkSplitter - split oversized nodes for embedding
    6. embed_model - generate embeddings via native vector_store integration

    Uses LlamaIndex's IngestionPipeline with native vector_store parameter
    for vector storage. This enables DocstoreStrategy.UPSERTS which properly
    handles document updates by re-embedding changed content.

    Vector indexing is always performed using the configured embedding
    backend (MLX or HuggingFace).

    Note: Stale document handling has been moved to catalog.store.cleanup.
    Use cleanup_stale_documents() for maintenance operations.

    Example:
        config = IngestDirectoryConfig(
            directory=Path("/path/to/docs"),
            dataset_name="my-docs",
            patterns=["**/*.md"],
        )
        pipeline = IngestPipeline()
        result = pipeline.ingest(config)
        print(f"Processed {result.total_processed} documents")
        print(f"Chunks: {result.chunks_created}, Vectors: {result.vectors_inserted}")
    """

    def ingest_dataset(self, config: DatasetIngestConfig) -> IngestResult:
        """Ingest documents from a local directory, and extracts metadata."""
        started_at = datetime.now(tz=timezone.utc)
        normalized_name = normalize_dataset_name(config.dataset_name)

        logger.info(
            f"Starting directory ingestion: {config.source_path} -> {normalized_name}"
        )

        #source = _get_source_instance(config)
        reader = create_reader(config)

        # Track results
        result = IngestResult(
            dataset_id=0,  # Will be set after dataset creation
            dataset_name=normalized_name,
            started_at=started_at,
        )

        with get_session() as session:
            # we want to wrap the dataset creation and populating it in a transaction
            with use_session(session):

                # Ensure FTS tables exist
                #TODO: move to migration?
                engine = session.get_bind()
                if engine is not None:
                    create_fts_table(engine)  # type: ignore
                    create_chunks_fts_table(engine)  # type: ignore

                # Create or get dataset
                dataset_id = DatasetService.create_or_update(
                    session,
                    config.dataset_name,
                    source_type=config.type_name,
                    source_path=str(config.source_path),
                )
                result.dataset_id = dataset_id

                # Create persistence transform (uses ambient session)
                persist = PersistenceTransform(
                    dataset_id=dataset_id,
                    force=config.force,
                )

                # Get vector store manager and embed model for caching via UPSERT
                from catalog.store.vector import VectorStoreManager
                vector_manager = VectorStoreManager()
                embed_model = get_embed_model()

                # Handle force=True: clear cache and dataset vectors
                if config.force:
                    logger.info(f"Force mode: clearing cache for dataset '{normalized_name}'")
                    clear_cache(normalized_name)
                    deleted = vector_manager.delete_by_dataset(normalized_name)
                    if deleted > 0:
                        logger.info(f"Cleared {deleted} vectors for dataset '{normalized_name}'")

                # Get the vector store for native pipeline integration
                vector_store = vector_manager.get_vector_store()

                link_resolve = LinkResolutionTransform(dataset_id=dataset_id)

                # Build pipeline with native vector_store integration
                # Using UPSERTS strategy for proper handling of document updates
                pipeline = IngestionPipeline(
                    transformations=[
                        FrontmatterTransform(),
                        persist,
                        link_resolve,
                        #embed_model,
                    ],
                    # docstore=SimpleDocumentStore(),
                    # docstore_strategy=DocstoreStrategy.UPSERTS,
                    # vector_store=vector_store,
                )

                # Run pipeline - persistence happens inside using ambient session
                documents = reader.load_data()

                logger.info(f"Running {len(documents)} documents through pipeline")
                nodes = pipeline.run(documents=documents)

                count = persist_documents(normalized_name, nodes)
                if count != len(documents):
                    logger.error(f"Persisted document count {count} does not match source document count {len(documents)}")


                # Copy stats from persistence transform
                result.documents_created = persist.stats.created
                result.documents_updated = persist.stats.updated
                result.documents_skipped = persist.stats.skipped
                result.documents_failed = persist.stats.failed
                result.errors = list(persist.stats.errors)

                # Copy stats from chunk persistence transform
                result.chunks_created = 0

                # this only works because the reader doesn't split documents
                result.documents_read = len(documents)

                # Vectors are inserted by native vector_store integration during pipeline run
                # Count is equal to the number of nodes returned by the pipeline
                result.vectors_inserted = len(nodes) if nodes else 0

                # Persist vector store after successful pipeline run
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

    def ingest(self, config: IngestDirectoryConfig | IngestObsidianConfig) -> IngestResult:
        """Ingest documents from a local directory.

        Creates or retrieves the dataset, enumerates matching files,
        and runs them through the LlamaIndex transformation pipeline
        with PersistenceTransform and ChunkPersistenceTransform handling
        persistence and FTS indexing.

        Vector indexing uses LlamaIndex's native vector_store integration
        with DocstoreStrategy.UPSERTS for proper handling of document updates.

        Notes:
        - This implementation uses LlamaIndex's docstore caching. Documents
        with unchanged content hashes are skipped. Changed documents are
        re-embedded automatically via the UPSERTS strategy.

        - LlamaIndex can technically split Documents into TextNodes,
        but effectively this pipeline treats each Document as a single node,
        and so the terms are used interchangeably.

        - When force=True, the pipeline cache and dataset vectors are cleared
        before running, ensuring a complete re-index.

        Args:
            config: Ingestion configuration, either directory or Obsidian.

        Returns:
            IngestResult with statistics about the operation.

        Raises:
            FileNotFoundError: If the directory does not exist.
            NotADirectoryError: If the path is not a directory.
        """

        started_at = datetime.now(tz=timezone.utc)
        normalized_name = normalize_dataset_name(config.dataset_name)

        logger.info(
            f"Starting directory ingestion: {config.source_path} -> {normalized_name}"
        )

        #source = _get_source_instance(config)
        source = create_source(config)

        # Track results
        result = IngestResult(
            dataset_id=0,  # Will be set after dataset creation
            dataset_name=normalized_name,
            started_at=started_at,
        )

        with get_session() as session:
            # we want to wrap the
            with use_session(session):

                # Ensure FTS tables exist
                #TODO: move to migration?
                engine = session.get_bind()
                if engine is not None:
                    create_fts_table(engine)  # type: ignore
                    create_chunks_fts_table(engine)  # type: ignore

                # Create or get dataset
                dataset_id = DatasetService.create_or_update(
                    session,
                    config.dataset_name,
                    source_type=source.type_name,
                    source_path=str(source.path),
                )
                result.dataset_id = dataset_id

                # Create persistence transform (uses ambient session)
                persist = PersistenceTransform(
                    dataset_id=dataset_id,
                    force=config.force,
                )
                split = MarkdownNodeParser(
                    include_metadata=True,
                    include_prev_next_rel=True,
                    header_path_separator=" / ",
                )
                # Create chunk persistence transform (uses ambient session)
                chunk_persist = ChunkPersistenceTransform(
                    dataset_name=normalized_name,
                )

                # Create size-aware splitter for oversized chunks
                size_splitter = SizeAwareChunkSplitter(
                    max_chars=2000,
                    fallback_chunk_size=512,
                    fallback_chunk_overlap=50,
                )

                # Get vector store manager and embed model
                from catalog.store.vector import VectorStoreManager
                vector_manager = VectorStoreManager()
                embed_model = self._get_embed_model()

                # Handle force=True: clear cache and dataset vectors
                if config.force:
                    logger.info(f"Force mode: clearing cache for dataset '{normalized_name}'")
                    clear_cache(normalized_name)
                    deleted = vector_manager.delete_by_dataset(normalized_name)
                    if deleted > 0:
                        logger.info(f"Cleared {deleted} vectors for dataset '{normalized_name}'")

                # Get the vector store for native pipeline integration
                vector_store = vector_manager.get_vector_store()

                # Build FrontmatterTransform with vault schema if available.
                vault_schema = getattr(source, "vault_schema", None)
                frontmatter = FrontmatterTransform(vault_schema_cls=vault_schema)

                link_resolve = LinkResolutionTransform(dataset_id=dataset_id)

                # Build pipeline with native vector_store integration
                # Using UPSERTS strategy for proper handling of document updates
                pipeline = IngestionPipeline(
                    transformations=[
                        TextNormalizerTransform(),
                        frontmatter,
                        persist,
                        link_resolve,
                        split,
                        chunk_persist,
                        size_splitter,
                        embed_model,
                    ],
                    docstore=SimpleDocumentStore(),
                    docstore_strategy=DocstoreStrategy.UPSERTS,
                    vector_store=vector_store,
                )

                # Run pipeline - persistence happens inside using ambient session
                logger.info(f"Running {len(source.documents)} documents through pipeline")
                nodes = pipeline.run(documents=source.documents)

                # Update the cache
                #persist_pipeline(normalized_name, pipeline)

                # Copy stats from persistence transform
                result.documents_created = persist.stats.created
                result.documents_updated = persist.stats.updated
                result.documents_skipped = persist.stats.skipped
                result.documents_failed = persist.stats.failed
                result.errors = list(persist.stats.errors)

                # Copy stats from chunk persistence transform
                result.chunks_created = chunk_persist.stats.created

                # this only works because the reader doesn't split documents
                result.documents_read = len(source.documents)

                # Vectors are inserted by native vector_store integration during pipeline run
                # Count is equal to the number of nodes returned by the pipeline
                result.vectors_inserted = len(nodes) if nodes else 0

                # Persist vector store after successful pipeline run
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

    def ingest_test(self, config: IngestObsidianConfig) -> IngestResult:
        """Ingest documents from a local directory.

        """

        started_at = datetime.now(tz=timezone.utc)
        normalized_name = normalize_dataset_name(config.dataset_name)

        logger.info(
            f"Starting directory ingestion: {config.source_path} -> {normalized_name}"
        )

        #source = _get_source_instance(config)
        source = create_source(config)

        # Track results
        result = IngestResult(
            dataset_id=0,  # Will be set after dataset creation
            dataset_name=normalized_name,
            started_at=started_at,
        )

        with get_session() as session:
            with use_session(session):

                # Ensure FTS tables exist
                #TODO: move to migration?
                engine = session.get_bind()
                if engine is not None:
                    create_fts_table(engine)  # type: ignore
                    create_chunks_fts_table(engine)  # type: ignore

                # Create or get dataset
                dataset_id = DatasetService.create_or_update(
                    session,
                    config.dataset_name,
                    source_type=source.type_name,
                    source_path=str(source.path),
                )
                result.dataset_id = dataset_id

                # Create persistence transform (uses ambient session)
                persist = PersistenceTransform(
                    dataset_id=dataset_id,
                    force=config.force,
                )
                split = MarkdownNodeParser(
                    include_metadata=True,
                    include_prev_next_rel=True,
                    header_path_separator=" / ",
                )
                # Create chunk persistence transform (uses ambient session)
                chunk_persist = ChunkPersistenceTransform(
                    dataset_name=normalized_name,
                )

                # Create size-aware splitter for oversized chunks
                size_splitter = SizeAwareChunkSplitter(
                    max_chars=2000,
                    fallback_chunk_size=512,
                    fallback_chunk_overlap=50,
                )

                # Get vector store manager and embed model
                #vector_manager = self._get_vector_store_manager()
                embed_model = self._get_embed_model()
                Settings.embed_model = embed_model

                # Handle force=True: clear cache and dataset vectors
                # if config.force:
                #     logger.info(f"Force mode: clearing cache for dataset '{normalized_name}'")
                #     clear_cache(normalized_name)
                #     deleted = vector_manager.delete_by_dataset(normalized_name)
                #     if deleted > 0:
                #         logger.info(f"Cleared {deleted} vectors for dataset '{normalized_name}'")

                # Get the vector store for native pipeline integration
                from catalog.store.vector import VectorStoreManager
                vector_manager = VectorStoreManager()
                vector_store = vector_manager.get_vector_store()
                # Create DuckDB vector store for downstream
                vector_store = DuckDBVectorStore(
                    database_name="downstream.duckdb",
                    persist_dir="./downstream_persist",
                    flat_metadata=False
                )
                # Build pipeline with native vector_store integration
                # Using UPSERTS strategy for proper handling of document updates
                pipeline = IngestionPipeline(
                    transformations=[
                        TextNormalizerTransform(),
                        BronzeMetadataTransform(meta_version="1.0.0"),
                        BronzeMetaHashTransform(),
                        # Add composite hash for change detection
                        CompositeHashTransform(include_metadata=True),
                        persist,
                        split,
                        chunk_persist,
                        size_splitter,  # get rid of this, add a real embedding splitter
                        #StripMetadataTransform(keys_to_strip=["frontmatter", "wikilinks", "backlinks"]),
                        embed_model,

                    ],
                    docstore=SimpleDocumentStore(),
                    docstore_strategy=DocstoreStrategy.UPSERTS_AND_DELETE,
                    vector_store=vector_store,
                )

                # Load persisted pipeline docstore if available
                #if not config.force:
                #    pipeline = load_pipeline(normalized_name, pipeline)

                # Run pipeline - persistence happens inside using ambient session
                logger.info(f"Running {len(source.documents)} documents through pipeline")
                for doc in source.documents:
                    print(f"Document: {doc.metadata}")
                    print(doc.excluded_embed_metadata_keys)
                nodes = pipeline.run(documents=source.documents)

                # Update the cache
                #persist_pipeline(normalized_name, pipeline)

                # Copy stats from persistence transform
                result.documents_created = persist.stats.created
                result.documents_updated = persist.stats.updated
                result.documents_skipped = persist.stats.skipped
                result.documents_failed = persist.stats.failed
                result.errors = list(persist.stats.errors)

                # Copy stats from chunk persistence transform
                result.chunks_created = chunk_persist.stats.created

                # this only works because the reader doesn't split documents
                result.documents_read = len(source.documents)

                # Vectors are inserted by native vector_store integration during pipeline run
                # Count is equal to the number of nodes returned by the pipeline
                result.vectors_inserted = len(nodes) if nodes else 0

                # Persist vector store after successful pipeline run
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

if __name__ == "__main__":
    import sys
    configure_logging(level="DEBUG")
    if len(sys.argv) < 2:
        print("Usage: python -m catalog.ingest.two_stage <source_dir>")
        sys.exit(1)

    from pathlib import Path
    import shutil

    idx_dir = Path.home() / ".idx"

    if idx_dir.exists() and idx_dir.is_dir():
        shutil.rmtree(idx_dir)

    config = IngestObsidianConfig(source_path=Path(sys.argv[1]))

    pipeline = IngestPipeline()
    result = pipeline.ingest_dataset(
        config
    )
