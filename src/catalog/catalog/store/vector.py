"""catalog.store.vector - Vector store management using Qdrant.

Provides vector storage and retrieval capabilities using Qdrant in local
persistent mode via LlamaIndex's QdrantVectorStore integration.

Example usage:
    from catalog.store.vector import VectorStoreManager

    manager = VectorStoreManager()
    index = manager.load_or_create()
    manager.insert_nodes([node1, node2])
    retriever = manager.get_retriever(similarity_top_k=10)
"""

from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import qdrant_client
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, VectorParams
from agentlayer.logging import get_logger
from llama_index.core.vector_stores import SimpleVectorStore
from llama_index.vector_stores.qdrant import QdrantVectorStore

from catalog.core.settings import get_settings
from catalog.embedding.identity import (
    EMBEDDING_BACKEND_METADATA_KEY,
    EMBEDDING_MODEL_METADATA_KEY,
    EMBEDDING_PROFILE_METADATA_KEY,
    EmbeddingIdentity,
)

if TYPE_CHECKING:
    from llama_index.core import VectorStoreIndex
    from llama_index.core.embeddings import BaseEmbedding
    from llama_index.core.retrievers import VectorIndexRetriever
    from llama_index.core.schema import TextNode, TransformComponent

__all__ = [
    "VectorBackendCapabilities",
    "VectorQueryHit",
    "VectorStoreManager",
]

logger = get_logger(__name__)


class _ZvecClient:
    """Local-file client for experimental Zvec semantic queries."""

    def __init__(self, index_path: Path) -> None:
        self._index_path = index_path.expanduser()

    def query(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int,
        dataset_name: str | None,
        embedding_identity: EmbeddingIdentity | None = None,
    ) -> list["VectorQueryHit"]:
        entries = self._load_collection_entries(collection_name=collection_name)
        hits: list[VectorQueryHit] = []
        for entry in entries:
            metadata = entry["metadata"]
            if dataset_name and not self._matches_dataset(metadata, dataset_name):
                continue
            if not self._matches_embedding_identity(
                metadata=metadata,
                embedding_identity=embedding_identity,
            ):
                continue

            score = self._cosine_similarity(query_vector, entry["vector"])
            if score is None:
                continue

            hits.append(
                VectorQueryHit(
                    node_id=entry["id"],
                    score=score,
                    metadata=metadata,
                )
            )

        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:top_k]

    def get_embedding_identities(
        self,
        collection_name: str,
        dataset_name: str | None = None,
    ) -> list[EmbeddingIdentity]:
        """Discover embedding identities from local index entry metadata."""
        entries = self._load_collection_entries(collection_name=collection_name)
        seen: dict[str, EmbeddingIdentity] = {}
        for entry in entries:
            metadata = entry["metadata"]
            if dataset_name and not self._matches_dataset(metadata, dataset_name):
                continue
            identity = EmbeddingIdentity.from_metadata(metadata)
            if identity is None:
                continue
            if identity.profile not in seen:
                seen[identity.profile] = identity
        return list(seen.values())

    def _load_collection_entries(self, collection_name: str) -> list[dict[str, Any]]:
        """Load and normalize vector entries from the configured local file."""
        if not self._index_path.exists():
            raise FileNotFoundError(
                f"Zvec index file does not exist: {self._index_path}"
            )

        with self._index_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        raw_entries: Any = []
        if isinstance(payload, dict):
            embedding_dict = payload.get("embedding_dict")
            metadata_dict = payload.get("metadata_dict")
            if isinstance(embedding_dict, dict):
                simple_entries: list[dict[str, Any]] = []
                for node_id, vector in embedding_dict.items():
                    metadata: Any = {}
                    if isinstance(metadata_dict, dict):
                        metadata = metadata_dict.get(node_id, {})
                    simple_entries.append(
                        {
                            "id": node_id,
                            "vector": vector,
                            "metadata": metadata,
                        }
                    )
                raw_entries = simple_entries
            else:
                collections = payload.get("collections")
                if isinstance(collections, dict):
                    raw_entries = collections.get(collection_name, [])
                elif isinstance(payload.get("entries"), list):
                    raw_entries = payload["entries"]
                elif isinstance(payload.get("vectors"), list):
                    raw_entries = payload["vectors"]
        elif isinstance(payload, list):
            raw_entries = payload

        if not isinstance(raw_entries, list):
            raise ValueError(
                "Zvec index file format is invalid. Expected a list of entries or "
                "a dict containing 'collections', 'entries', or 'vectors'."
            )

        entries: list[dict[str, Any]] = []
        for raw_entry in raw_entries:
            if not isinstance(raw_entry, dict):
                continue

            entry_collection = raw_entry.get("collection_name")
            if (
                isinstance(entry_collection, str)
                and entry_collection
                and entry_collection != collection_name
            ):
                continue

            node_id = raw_entry.get("id")
            raw_vector = raw_entry.get("vector")
            if node_id is None or not isinstance(raw_vector, list):
                continue

            try:
                vector = [float(value) for value in raw_vector]
            except (TypeError, ValueError):
                continue

            metadata = raw_entry.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}

            dataset_name = raw_entry.get("dataset_name")
            if (
                isinstance(dataset_name, str)
                and dataset_name
                and "dataset_name" not in metadata
            ):
                metadata = {
                    **metadata,
                    "dataset_name": dataset_name,
                }

            entries.append(
                {
                    "id": str(node_id),
                    "vector": vector,
                    "metadata": metadata,
                }
            )

        return entries

    @staticmethod
    def _matches_dataset(metadata: dict[str, Any], dataset_name: str) -> bool:
        """Return True when metadata belongs to the requested dataset."""
        meta_dataset = metadata.get("dataset_name")
        if isinstance(meta_dataset, str) and meta_dataset == dataset_name:
            return True

        source_doc_id = metadata.get("source_doc_id")
        if isinstance(source_doc_id, str):
            return source_doc_id.startswith(f"{dataset_name}:")

        return False

    @staticmethod
    def _matches_embedding_identity(
        metadata: dict[str, Any],
        embedding_identity: EmbeddingIdentity | None,
    ) -> bool:
        """Return True when metadata matches requested embedding identity filter."""
        if embedding_identity is None:
            return True

        stored_identity = EmbeddingIdentity.from_metadata(metadata)
        if stored_identity is None:
            return False
        return stored_identity.profile == embedding_identity.profile

    @staticmethod
    def _cosine_similarity(
        left: list[float],
        right: list[float],
    ) -> float | None:
        """Compute cosine similarity, returning None for invalid vectors."""
        if not left or not right:
            return None
        if len(left) != len(right):
            return None

        dot = sum(a * b for a, b in zip(left, right, strict=False))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0.0 or right_norm == 0.0:
            return None
        return dot / (left_norm * right_norm)


@dataclass(frozen=True, slots=True)
class VectorBackendCapabilities:
    """Capabilities exposed by the active vector backend."""

    native_embedding_identity: bool = False


@dataclass(frozen=True, slots=True)
class VectorQueryHit:
    """Normalized vector query hit."""

    node_id: str
    score: float
    metadata: dict[str, Any]


class _EmbeddingIdentityStrategy(Protocol):
    """Strategy interface for embedding identity handling."""

    def build_ingest_transforms(
        self,
        manager: "VectorStoreManager",
        embed_model: "BaseEmbedding",
    ) -> list["TransformComponent"]:
        """Return transforms required before vector insert."""

    def query(
        self,
        manager: "VectorStoreManager",
        query: str,
        top_k: int,
        dataset_name: str | None = None,
    ) -> list["VectorQueryHit"]:
        """Execute vector query with backend-specific identity behavior."""


class _NativeEmbeddingIdentityStrategy:
    """No-op identity strategy for backends with native identity support."""

    def build_ingest_transforms(
        self,
        manager: "VectorStoreManager",
        embed_model: "BaseEmbedding",
    ) -> list["TransformComponent"]:
        return []

    def query(
        self,
        manager: "VectorStoreManager",
        query: str,
        top_k: int,
        dataset_name: str | None = None,
    ) -> list["VectorQueryHit"]:
        if manager.vector_backend == "zvec":
            return manager._query_zvec(
                query=query,
                top_k=top_k,
                dataset_name=dataset_name,
            )

        from llama_index.core.vector_stores import VectorStoreQuery

        vector_store = manager.get_vector_store()
        embed_model = manager._get_embed_model()
        query_embedding = embed_model.get_query_embedding(query)
        filters = manager._build_filters(dataset_name=dataset_name)

        vs_query = VectorStoreQuery(
            query_embedding=query_embedding,
            similarity_top_k=top_k,
            filters=filters,
        )
        result = vector_store.query(vs_query)
        return manager._normalize_query_hits(result)


class _PayloadEmbeddingIdentityStrategy:
    """Payload-based strategy for backends lacking native identity support."""

    def build_ingest_transforms(
        self,
        manager: "VectorStoreManager",
        embed_model: "BaseEmbedding",
    ) -> list["TransformComponent"]:
        from catalog.embedding import resolve_embedding_identity
        from catalog.transform.embedding import EmbeddingIdentityTransform

        identity = resolve_embedding_identity(
            embed_model,
            fallback=manager.get_configured_embedding_identity(),
        )
        return [
            EmbeddingIdentityTransform(
                backend=identity.backend,
                model_name=identity.model_name,
            )
        ]

    def query(
        self,
        manager: "VectorStoreManager",
        query: str,
        top_k: int,
        dataset_name: str | None = None,
    ) -> list["VectorQueryHit"]:
        from llama_index.core.vector_stores import VectorStoreQuery

        stored_identities = manager.get_embedding_identities(dataset_name=dataset_name)
        use_identity_filter = len(stored_identities) > 0
        identities = (
            stored_identities
            if stored_identities
            else [manager.get_configured_embedding_identity()]
        )

        vector_store = manager.get_vector_store() if manager.vector_backend == "qdrant" else None
        best_hits: dict[str, VectorQueryHit] = {}
        for identity in identities:
            embed_model = manager.get_embed_model_for_identity(identity)
            query_embedding = embed_model.get_query_embedding(query)
            if manager.vector_backend == "zvec":
                hits = manager._query_zvec(
                    top_k=top_k,
                    dataset_name=dataset_name,
                    query_embedding=query_embedding,
                    embedding_identity=identity if use_identity_filter else None,
                    fallback_identity=identity,
                )
            else:
                if vector_store is None:
                    raise RuntimeError("Vector store is unavailable for qdrant backend query")
                filters = manager._build_filters(
                    dataset_name=dataset_name,
                    embedding_identity=identity if use_identity_filter else None,
                )
                vs_query = VectorStoreQuery(
                    query_embedding=query_embedding,
                    similarity_top_k=top_k,
                    filters=filters,
                )
                result = vector_store.query(vs_query)
                hits = manager._normalize_query_hits(
                    result=result,
                    fallback_identity=identity,
                )
            for hit in hits:
                existing = best_hits.get(hit.node_id)
                if existing is None or hit.score > existing.score:
                    best_hits[hit.node_id] = hit

        return sorted(
            best_hits.values(),
            key=lambda hit: hit.score,
            reverse=True,
        )[:top_k]


@lru_cache(maxsize=8)
def _build_embed_model(
    backend: str,
    model_name: str,
    batch_size: int,
):
    """Build and cache embedding models per process.

    The catalog CLI often creates multiple ``VectorStoreManager`` instances
    during a single run (e.g. comparing fts/vector/hybrid modes). Loading the
    embedding model each time dominates latency, so this cache keeps one model
    instance per unique backend/model/batch configuration in the current
    process. Delegates to ``catalog.embedding.build_embed_model`` so backend
    dispatch and constructor logic live in one place.

    Args:
        backend: Embedding backend name (``mlx`` or ``huggingface``).
        model_name: Embedding model identifier.
        batch_size: Embedding batch size.

    Returns:
        Configured embedding model.
    """
    from catalog.embedding import build_embed_model

    return build_embed_model(backend=backend, model_name=model_name, batch_size=batch_size)


class VectorStoreManager:
    """Manages vector storage backends for semantic retrieval.

    Qdrant remains the default backend and supports full ingest/search lifecycle.
    Zvec support is intentionally latent and experimental, intended to exercise
    local-file vector query integration without changing runtime defaults.
    """

    def __init__(
        self,
        persist_dir: Path | None = None,
        capabilities: VectorBackendCapabilities | None = None,
    ) -> None:
        """Initialize the VectorStoreManager.

        Args:
            persist_dir: Directory for Qdrant's local storage.
                If None, uses settings.vector_store_path.
            capabilities: Optional backend capability overrides. Defaults to
                Qdrant capabilities (no native embedding identity support).
        """
        settings = get_settings()
        self._persist_dir = persist_dir or settings.vector_store_path
        self._embed_settings = settings.embedding
        self._qdrant_settings = settings.qdrant
        self._vector_backend = settings.vector_db.backend
        self._zvec_settings = settings.zvec
        self._configured_identity = EmbeddingIdentity(
            backend=self._embed_settings.backend,
            model_name=self._embed_settings.model_name,
        )

        if (
            self._vector_backend == "zvec"
            and not settings.vector_db.enable_experimental_zvec
        ):
            raise ValueError(
                "Zvec backend is disabled. Set IDX_VECTOR_DB__ENABLE_EXPERIMENTAL_ZVEC=true to opt in."
            )

        default_capabilities = VectorBackendCapabilities(
            native_embedding_identity=False
        )
        self._capabilities = capabilities or default_capabilities
        self._identity_strategy: _EmbeddingIdentityStrategy = (
            _NativeEmbeddingIdentityStrategy()
            if self._capabilities.native_embedding_identity
            else _PayloadEmbeddingIdentityStrategy()
        )

        # Lazy-initialized components
        self._client: qdrant_client.QdrantClient | None = None
        self._index: "VectorStoreIndex | None" = None
        self._embed_model: "BaseEmbedding | None" = None
        self._vector_store: QdrantVectorStore | None = None
        self._zvec_vector_store: SimpleVectorStore | None = None
        self._zvec_client: _ZvecClient | None = None

        logger.debug(
            f"VectorStoreManager initialized with persist_dir={self._persist_dir}"
        )

    @property
    def persist_dir(self) -> Path:
        """Get the persistence directory path."""
        return self._persist_dir

    @property
    def capabilities(self) -> VectorBackendCapabilities:
        """Get declared capabilities for the active vector backend."""
        return self._capabilities

    @property
    def vector_backend(self) -> str:
        """Get selected vector backend name."""
        return self._vector_backend

    def _get_zvec_client(self) -> _ZvecClient:
        """Get or create the experimental Zvec local-file client."""
        if self._zvec_client is None:
            self._zvec_client = _ZvecClient(
                index_path=self._zvec_settings.index_path,
            )
        return self._zvec_client

    def _get_client(self) -> qdrant_client.QdrantClient:
        """Get or create the Qdrant client (lazy initialization).

        Returns:
            QdrantClient configured for local persistent storage.
        """
        if self._vector_backend != "qdrant":
            raise RuntimeError("Qdrant client is unavailable for non-qdrant backends")

        if self._client is None:
            self._persist_dir.mkdir(parents=True, exist_ok=True)
            self._client = qdrant_client.QdrantClient(
                path=str(self._persist_dir)
            )
            logger.debug(f"Qdrant client initialized at {self._persist_dir}")

        return self._client

    def _ensure_collection(self) -> None:
        """Ensure the collection exists with correct configuration."""
        client = self._get_client()
        collection_name = self._qdrant_settings.collection_name

        collections = client.get_collections().collections
        exists = any(c.name == collection_name for c in collections)

        if not exists:
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=self._embed_settings.embedding_dim,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(
                f"Created Qdrant collection: {collection_name} "
                f"(dim={self._embed_settings.embedding_dim})"
            )

            # Create payload index for efficient dataset filtering
            client.create_payload_index(
                collection_name=collection_name,
                field_name="dataset_name",
                field_schema="keyword",
            )
            logger.debug(f"Created payload index on 'dataset_name'")
            if not self._capabilities.native_embedding_identity:
                client.create_payload_index(
                    collection_name=collection_name,
                    field_name=EMBEDDING_PROFILE_METADATA_KEY,
                    field_schema="keyword",
                )
                logger.debug(f"Created payload index on '{EMBEDDING_PROFILE_METADATA_KEY}'")

    def _collection_exists(self) -> bool:
        """Return True when the active backend collection exists."""
        if self._vector_backend != "qdrant":
            return True

        client = self._get_client()
        collection_name = self._qdrant_settings.collection_name
        collections = client.get_collections().collections
        return any(c.name == collection_name for c in collections)

    def get_configured_embedding_identity(self) -> EmbeddingIdentity:
        """Get embedding identity from current process settings."""
        return self._configured_identity

    def build_ingest_transforms(
        self,
        embed_model: "BaseEmbedding",
    ) -> list["TransformComponent"]:
        """Build ingest-time transforms for embedding identity handling.

        Backends with native embedding identity support return an empty list.
        """
        return self._identity_strategy.build_ingest_transforms(self, embed_model)

    def semantic_query(
        self,
        query: str,
        top_k: int,
        dataset_name: str | None = None,
    ) -> list["VectorQueryHit"]:
        """Execute a semantic query using the active identity strategy."""
        return self._identity_strategy.query(
            self,
            query=query,
            top_k=top_k,
            dataset_name=dataset_name,
        )

    def _query_zvec(
        self,
        top_k: int,
        dataset_name: str | None = None,
        query: str | None = None,
        query_embedding: list[float] | None = None,
        embedding_identity: EmbeddingIdentity | None = None,
        fallback_identity: EmbeddingIdentity | None = None,
    ) -> list[VectorQueryHit]:
        """Execute semantic query using the experimental Zvec backend."""
        if query_embedding is None:
            if query is None:
                raise ValueError("query or query_embedding is required for zvec query")
            embed_model = self._get_embed_model()
            query_embedding = embed_model.get_query_embedding(query)

        zvec_client = self._get_zvec_client()
        hits = zvec_client.query(
            collection_name=self._zvec_settings.collection_name,
            query_vector=query_embedding,
            top_k=top_k,
            dataset_name=dataset_name,
            embedding_identity=embedding_identity,
        )
        if fallback_identity is None:
            return hits
        return self._add_fallback_identity(hits, fallback_identity)

    def _get_embed_model(self) -> "BaseEmbedding":
        """Get or create the embedding model (lazy initialization).

        Returns the configured embedding model based on settings.embedding.backend:
        - "mlx": MLXEmbedding for Apple Silicon
        - "huggingface": HuggingFaceEmbedding for general use

        Returns:
            BaseEmbedding instance configured from settings.
        """
        if self._embed_model is None:
            self._embed_model = self.get_embed_model_for_identity(
                self._configured_identity
            )

        return self._embed_model

    def get_embed_model_for_identity(
        self,
        identity: EmbeddingIdentity,
    ) -> "BaseEmbedding":
        """Build or reuse an embedding model for a specific identity."""
        return _build_embed_model(
            backend=identity.backend,
            model_name=identity.model_name,
            batch_size=self._embed_settings.batch_size,
        )

    def get_embedding_identities(
        self,
        dataset_name: str | None = None,
    ) -> list[EmbeddingIdentity]:
        """Discover embedding identities stored in vector payloads.

        Args:
            dataset_name: Optional dataset filter.

        Returns:
            Distinct identities present in the collection, preserving first
            encounter order.
        """
        if self._capabilities.native_embedding_identity:
            return []

        if self._vector_backend == "zvec":
            zvec_client = self._get_zvec_client()
            return zvec_client.get_embedding_identities(
                collection_name=self._zvec_settings.collection_name,
                dataset_name=dataset_name,
            )

        if not self._collection_exists():
            return []

        client = self._get_client()
        collection_name = self._qdrant_settings.collection_name
        seen: dict[str, EmbeddingIdentity] = {}

        scroll_filter = None
        if dataset_name:
            scroll_filter = Filter(
                must=[
                    FieldCondition(
                        key="dataset_name",
                        match=MatchValue(value=dataset_name),
                    )
                ]
            )

        next_offset: Any = None
        while True:
            records, next_offset = client.scroll(
                collection_name=collection_name,
                scroll_filter=scroll_filter,
                limit=256,
                offset=next_offset,
                with_payload=[
                    EMBEDDING_BACKEND_METADATA_KEY,
                    EMBEDDING_MODEL_METADATA_KEY,
                    EMBEDDING_PROFILE_METADATA_KEY,
                ],
                with_vectors=False,
            )

            if not records:
                break

            for record in records:
                payload = record.payload if record.payload is not None else {}
                identity = EmbeddingIdentity.from_metadata(payload)
                if identity is None:
                    continue
                if identity.profile not in seen:
                    seen[identity.profile] = identity

            if next_offset is None:
                break

        return list(seen.values())

    @staticmethod
    def _add_fallback_identity(
        hits: list["VectorQueryHit"],
        fallback_identity: EmbeddingIdentity,
    ) -> list["VectorQueryHit"]:
        """Attach fallback embedding identity metadata when missing."""
        normalized_hits: list[VectorQueryHit] = []
        for hit in hits:
            metadata = hit.metadata
            if EMBEDDING_PROFILE_METADATA_KEY not in metadata:
                metadata = {
                    **metadata,
                    **fallback_identity.to_metadata(),
                }
            normalized_hits.append(
                VectorQueryHit(
                    node_id=hit.node_id,
                    score=hit.score,
                    metadata=metadata,
                )
            )
        return normalized_hits

    def _build_filters(
        self,
        dataset_name: str | None,
        embedding_identity: EmbeddingIdentity | None = None,
    ):
        """Build vector metadata filters."""
        from llama_index.core.vector_stores.types import (
            FilterCondition,
            MetadataFilter,
            MetadataFilters,
        )

        filters: list[MetadataFilter] = []
        if dataset_name:
            filters.append(
                MetadataFilter(
                    key="dataset_name",
                    value=dataset_name,
                )
            )
        if embedding_identity is not None:
            filters.append(
                MetadataFilter(
                    key=EMBEDDING_PROFILE_METADATA_KEY,
                    value=embedding_identity.profile,
                )
            )

        if not filters:
            return None

        return MetadataFilters(
            filters=filters,
            condition=FilterCondition.AND,
        )

    def _normalize_query_hits(
        self,
        result: Any,
        fallback_identity: EmbeddingIdentity | None = None,
    ) -> list["VectorQueryHit"]:
        """Normalize a vector-store query result to VectorQueryHit records."""
        if not result.ids:
            return []

        hits: list[VectorQueryHit] = []
        for i, node_id in enumerate(result.ids):
            score = result.similarities[i] if result.similarities else 0.0
            metadata: dict[str, Any] = {}
            if result.nodes and i < len(result.nodes):
                node = result.nodes[i]
                metadata = (
                    node.metadata if hasattr(node, "metadata") and node.metadata else {}
                )

            if fallback_identity and EMBEDDING_PROFILE_METADATA_KEY not in metadata:
                metadata = {**metadata, **fallback_identity.to_metadata()}

            hits.append(
                VectorQueryHit(
                    node_id=str(node_id),
                    score=score,
                    metadata=metadata,
                )
            )
        return hits

    def load_or_create(self) -> "VectorStoreIndex":
        """Load or create a VectorStoreIndex backed by Qdrant.

        Creates the collection if it doesn't exist, then returns
        a VectorStoreIndex that uses the Qdrant vector store.

        Returns:
            VectorStoreIndex ready for use.
        """
        if self._vector_backend != "qdrant":
            raise RuntimeError(
                "load_or_create is only implemented for qdrant backend. "
                "Zvec support is currently latent for semantic_query only."
            )

        if self._index is not None:
            return self._index

        from llama_index.core import StorageContext, VectorStoreIndex

        vector_store = self.get_vector_store()
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        self._index = VectorStoreIndex.from_vector_store(
            vector_store=vector_store,
            storage_context=storage_context,
            embed_model=self._get_embed_model(),
        )

        logger.info("VectorStoreIndex created from Qdrant")
        return self._index

    def get_vector_store(self):
        """Get or create the active backend vector store for pipeline integration.

        Returns the backend-specific vector store instance, creating it if needed.
        This is used to pass the vector store to IngestionPipeline's vector_store
        parameter for native integration.

        Returns:
            Backend vector store instance for pipeline use.
        """
        if self._vector_backend == "zvec":
            if self._zvec_vector_store is not None:
                return self._zvec_vector_store

            index_path = self._zvec_settings.index_path.expanduser()
            index_path.parent.mkdir(parents=True, exist_ok=True)
            if index_path.exists():
                self._zvec_vector_store = SimpleVectorStore.from_persist_path(
                    str(index_path)
                )
                logger.info(f"SimpleVectorStore initialized for Zvec from {index_path}")
            else:
                self._zvec_vector_store = SimpleVectorStore()
                logger.info(
                    f"SimpleVectorStore initialized for Zvec (new index at {index_path})"
                )
            return self._zvec_vector_store

        if self._vector_store is not None:
            return self._vector_store

        self._ensure_collection()
        client = self._get_client()

        self._vector_store = QdrantVectorStore(
            client=client,
            collection_name=self._qdrant_settings.collection_name,
        )
        logger.info("QdrantVectorStore initialized")
        return self._vector_store

    def persist(self) -> None:
        """Persist vector state for backends that require explicit flush."""
        if self._vector_backend == "zvec":
            self.persist_vector_store()
            return
        logger.debug("Qdrant auto-persists; explicit persist() is no-op")

    def persist_vector_store(self, persist_dir: Path | None = None) -> None:
        """Persist vector store state where applicable.

        Args:
            persist_dir: Optional override for persist target.
        """
        if self._vector_backend == "zvec":
            vector_store = self.get_vector_store()
            persist_path = (
                (persist_dir / "vector_store.json")
                if persist_dir is not None
                else self._zvec_settings.index_path.expanduser()
            )
            persist_path.parent.mkdir(parents=True, exist_ok=True)
            vector_store.persist(str(persist_path))
            logger.debug(f"Persisted Zvec vector store to {persist_path}")
            return
        logger.debug("Qdrant auto-persists; explicit persist_vector_store() is no-op")

    def insert_nodes(self, nodes: list["TextNode"]) -> None:
        """Add nodes to the index with automatic embedding generation.

        Nodes will have their embeddings computed if not already present.
        Existing nodes with the same ID will be updated.

        Args:
            nodes: List of TextNode objects to insert.

        Raises:
            RuntimeError: If the index hasn't been loaded or created yet.
        """
        if not nodes:
            logger.debug("No nodes to insert")
            return

        if self._index is None:
            raise RuntimeError(
                "No index loaded. Call load_or_create() first."
            )

        logger.debug(f"Inserting {len(nodes)} nodes into vector store")
        self._index.insert_nodes(nodes)
        logger.info(f"Inserted {len(nodes)} nodes into vector store")

    def delete_nodes(self, node_ids: list[str]) -> None:
        """Delete specific nodes from the index by their IDs.

        Args:
            node_ids: List of node IDs to delete.

        Raises:
            RuntimeError: If the index hasn't been loaded or created yet.
        """
        if not node_ids:
            logger.debug("No node IDs to delete")
            return

        if self._index is None:
            raise RuntimeError(
                "No index loaded. Call load_or_create() first."
            )

        logger.debug(f"Deleting {len(node_ids)} nodes from vector store")
        self._index.delete_nodes(node_ids)
        logger.info(f"Deleted {len(node_ids)} nodes from vector store")

    def delete_ref_doc(self, ref_doc_id: str) -> None:
        """Delete all nodes associated with a reference document.

        This removes all chunks/nodes that were derived from the
        specified source document.

        Args:
            ref_doc_id: Reference document ID (source_doc_id).

        Raises:
            RuntimeError: If the index hasn't been loaded or created yet.
        """
        if self._index is None:
            raise RuntimeError(
                "No index loaded. Call load_or_create() first."
            )

        logger.debug(f"Deleting nodes for ref_doc_id: {ref_doc_id}")
        self._index.delete_ref_doc(ref_doc_id)
        logger.info(f"Deleted nodes for ref_doc_id: {ref_doc_id}")

    def delete_by_dataset(self, dataset_name: str) -> int:
        """Delete all vectors associated with a dataset.

        Uses Qdrant's filter-based deletion to remove all points
        whose dataset_name payload field matches the given value.

        Args:
            dataset_name: Name of the dataset to clear vectors for.

        Returns:
            Number of points deleted.
        """
        if self._vector_backend != "qdrant":
            logger.warning("delete_by_dataset is not implemented for backend %s", self._vector_backend)
            return 0

        client = self._get_client()
        collection_name = self._qdrant_settings.collection_name

        # Check if collection exists
        if not self._collection_exists():
            logger.debug(f"Collection {collection_name} does not exist, nothing to delete")
            return 0

        # Count points before deletion
        count_filter = Filter(
            must=[
                FieldCondition(
                    key="dataset_name",
                    match=MatchValue(value=dataset_name),
                )
            ]
        )

        count_result = client.count(
            collection_name=collection_name,
            count_filter=count_filter,
            exact=True,
        )
        count = count_result.count

        if count > 0:
            # Delete using filter
            from qdrant_client.models import FilterSelector

            client.delete(
                collection_name=collection_name,
                points_selector=FilterSelector(filter=count_filter),
            )
            logger.info(f"Deleted {count} vectors for dataset '{dataset_name}'")
        else:
            logger.debug(f"No vectors found for dataset '{dataset_name}'")

        return count

    def get_retriever(
        self,
        similarity_top_k: int = 10,
    ) -> "VectorIndexRetriever":
        """Get a retriever for similarity search.

        Args:
            similarity_top_k: Number of most similar nodes to retrieve.

        Returns:
            VectorIndexRetriever configured for the index.

        Raises:
            RuntimeError: If the index hasn't been loaded or created yet.
        """
        if self._index is None:
            raise RuntimeError(
                "No index loaded. Call load_or_create() first."
            )

        logger.debug(f"Creating retriever with similarity_top_k={similarity_top_k}")
        return self._index.as_retriever(similarity_top_k=similarity_top_k)

    def clear(self) -> None:
        """Clear the in-memory caches.

        This forces the index and vector store to be reloaded on next access.
        Does not delete persisted data from Qdrant.
        Note: The client connection is preserved for reuse.
        """
        self._index = None
        self._vector_store = None
        self._zvec_vector_store = None
        logger.debug("Vector store index cache cleared")

    @property
    def is_loaded(self) -> bool:
        """Check if an index is currently loaded in memory."""
        return self._index is not None
