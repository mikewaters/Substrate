"""index.pipelines.pipelines - Dataset index pipeline.

Loads persisted documents from the DB by dataset_id and runs them through
FTS indexing, chunking, chunk FTS, embedding, and vector insertion.

Can also accept nodes directly via index(nodes=...) for manual testing.

Pipeline flow:
1. DocumentFTSTransform (document-level FTS indexing)
2. ResilientSplitter (token-based with char fallback)
3. ChunkPersistenceTransform (chunk-level FTS + metadata assignment)
4. EmbeddingPrefixTransform (Nomic-style prefixes)
5. Vector identity transforms from VectorStoreManager
6. embed_model (generate embeddings)
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import cached_property
from typing import Sequence

from agentlayer.logging import get_logger
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.schema import BaseNode, Document as LlamaDocument, TransformComponent

from agentlayer.pipeline import BasePipeline
from agentlayer.session import current_session
from index.pipelines.schemas import IndexResult
from catalog.store.repositories import DocumentRepository
from index.store.cleanup import IndexCleanup, ReconciliationStats
from index.store.vector import VectorStoreManager
from index.transform.embedding import EmbeddingPrefixTransform
from index.transform.llama import ChunkPersistenceTransform, DocumentFTSTransform
from index.transform.splitter import ResilientSplitter

__all__ = [
    "DatasetIndexPipeline",
]

logger = get_logger(__name__)


class DatasetIndexPipeline(BasePipeline):
    """Index pipeline: FTS, chunking, embedding, and vector insertion.

    Loads active documents from the DB by dataset_id and produces searchable
    chunks with embeddings in the vector store. Accepts optional nodes
    override for manual testing.

    Entry point:
        index(nodes=None, vector_manager=None) -> IndexResult
    """

    @cached_property
    def _settings(self):
        """Get RAG settings from catalog configuration."""
        from catalog.core.settings import get_settings
        return get_settings().rag

    def _load_nodes(self) -> list[BaseNode]:
        """Load active documents from DB and convert to LlamaIndex nodes.

        Returns:
            List of LlamaDocument nodes with metadata matching what the
            ingest pipeline produces.
        """
        doc_repo = DocumentRepository()
        docs = doc_repo.list_by_parent(self.dataset_id, active_only=True)
        nodes: list[BaseNode] = []
        for doc in docs:
            metadata = doc.metadata_json or {}
            metadata["doc_id"] = doc.id
            metadata["relative_path"] = doc.path
            if doc.title:
                metadata["title"] = doc.title
            if doc.description:
                metadata["description"] = doc.description
            node = LlamaDocument(text=doc.body, metadata=metadata, id_=doc.path)
            nodes.append(node)
        return nodes

    def _get_transforms(
        self,
        vector_manager: VectorStoreManager,
    ) -> list[TransformComponent]:
        """Build the transform chain for indexing.

        Args:
            vector_manager: Vector manager providing backend-aware ingest transforms.
        """
        embed_model = self._get_embed_model()
        identity_transforms = vector_manager.build_ingest_transforms(embed_model)

        return [
            # Stage 1: Document-level FTS indexing
            DocumentFTSTransform(path_key="relative_path"),
            # Stage 2: Chunking
            ResilientSplitter(
                chunk_size_tokens=self._settings.chunk_size,
                chunk_overlap_tokens=self._settings.chunk_overlap,
                chars_per_token=self._settings.chunk_chars_per_token,
                fallback_enabled=self._settings.chunk_fallback_enabled,
            ),
            # Stage 3: Chunk FTS persistence + metadata assignment
            ChunkPersistenceTransform(
                dataset_name=self.dataset_name,
            ),
            # Stage 4: Embedding prefix
            EmbeddingPrefixTransform(
                prefix_template=self._settings.embed_prefix_doc,
            ),
            # Stage 5: Vector identity transforms + embedding model
            *identity_transforms,
            embed_model,
        ]

    def build_pipeline(
        self,
        vector_manager: VectorStoreManager,
    ) -> IngestionPipeline:
        """Build the index pipeline.

        Unlike the ingest pipeline, the index pipeline does NOT use a docstore
        or docstore_strategy -- change detection already happened in the ingest
        stage. All nodes passed here are new or changed and should be processed.

        Args:
            vector_manager: Vector store manager for embeddings.

        Returns:
            Configured IngestionPipeline ready to run.
        """
        transformations = self._get_transforms(vector_manager=vector_manager)
        vector_store = vector_manager.get_vector_store()

        pipeline = IngestionPipeline(
            transformations=transformations,
            vector_store=vector_store,
        )

        return pipeline

    def _reconcile_inactive_documents(
        self,
        vector_manager: VectorStoreManager,
    ) -> ReconciliationStats:
        """Remove index artifacts for documents marked inactive in the catalog.

        Runs at the start of index() so search artifacts match catalog state.
        Expects ambient session to be set (e.g. via use_session(session)).
        """
        session = current_session()
        cleanup = IndexCleanup(session)
        return cleanup.reconcile_inactive_documents(
            parent_id=self.dataset_id,
            dataset_name=self.dataset_name,
            vector_manager=vector_manager,
        )

    def index(
        self,
        nodes: Sequence[BaseNode] | None = None,
        vector_manager: VectorStoreManager | None = None,
    ) -> IndexResult:
        """Run the index pipeline on documents.

        Loads active documents from the DB unless nodes are passed directly.
        Reconciles index artifacts for inactive documents first, then indexes
        active docs. Expects to run within a session context (e.g. use_session(session)).

        Args:
            nodes: Optional document nodes override. If None, loads from DB.
            vector_manager: Optional vector manager. Creates a new one if not provided.

        Returns:
            IndexResult with statistics about the operation.
        """
        started_at = datetime.now(tz=timezone.utc)

        if vector_manager is None:
            vector_manager = VectorStoreManager()

        vector_manager.load_or_create()
        self._reconcile_inactive_documents(vector_manager)

        if nodes is None:
            nodes = self._load_nodes()

        logger.info(f"Starting indexing: {len(nodes)} nodes for dataset '{self.dataset_name}'")

        pipeline = self.build_pipeline(vector_manager=vector_manager)

        # SQLite does not support concurrent writers; persistence transforms
        # write to SQLite, so use 1 worker.
        result_nodes: Sequence[BaseNode] = pipeline.run(
            nodes=list(nodes), num_workers=1
        )

        # Collect statistics from transforms
        chunk_persist_transform = None
        for t in pipeline.transformations:
            if isinstance(t, ChunkPersistenceTransform):
                chunk_persist_transform = t

        result = IndexResult(
            dataset_id=self.dataset_id or 0,
            dataset_name=self.dataset_name or "",
            started_at=started_at,
            chunks_created=chunk_persist_transform.stats.created if chunk_persist_transform else 0,
            vectors_inserted=len(result_nodes) if result_nodes else 0,
            fts_documents_indexed=len(nodes),
            errors=(
                list(chunk_persist_transform.stats.errors)
                if chunk_persist_transform
                else []
            ),
            completed_at=datetime.now(tz=timezone.utc),
        )

        # Persist vector store state
        vector_manager.persist_vector_store()

        logger.info(
            f"Indexing complete: "
            f"fts_docs={result.fts_documents_indexed}, "
            f"chunks={result.chunks_created}, "
            f"vectors={result.vectors_inserted}"
        )

        return result
