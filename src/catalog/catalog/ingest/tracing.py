"""catalog.ingest.tracing - Instrumentation helpers for ingestion pipelines.

Provides lightweight hooks for inspecting nodes between pipeline stages and
tracing docstore behavior that influences cache hits and skips.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Sequence

from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.schema import BaseNode, MetadataMode, TransformComponent
from llama_index.core.storage.docstore import BaseDocumentStore
from llama_index.core.storage.docstore.types import (DEFAULT_PERSIST_PATH,
                                                     RefDocInfo)
from llama_index.core.storage.kvstore.types import DEFAULT_BATCH_SIZE

from agentlayer.logging import get_logger

logger = get_logger(__name__)

__all__ = [
    "SnapshotTransform",
    "TracingDocstore",
    "DebugPipeline",
]


def _stable_sample(key: str, mod: int) -> bool:
    """Return True if a key is selected by a deterministic sampling modulus."""
    if mod <= 1:
        return True
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % mod == 0


class SnapshotTransform(TransformComponent):
    """Pass-through transform that logs sampled node snapshots.

    This is useful for inspecting pipeline stages without changing behavior.
    Sampling is deterministic based on the node hash (or id fallback).
    """

    def __init__(
        self,
        label: str,
        *,
        sample_mod: int = 100,
        metadata_mode: MetadataMode = MetadataMode.NONE,
        **kwargs: Any,
    ) -> None:
        """Initialize the snapshot transform.

        Args:
            label: Stage label to include in logs.
            sample_mod: Deterministic sampling modulus (1 = log all).
            metadata_mode: Metadata mode for content length calculation.
            **kwargs: Extra arguments forwarded to TransformComponent.
        """
        super().__init__(**kwargs)
        self._label = label
        self._sample_mod = max(1, sample_mod)
        self._metadata_mode = metadata_mode

    def __call__(self, nodes: list[BaseNode], **kwargs: Any) -> list[BaseNode]:
        """Log sampled nodes and pass them through unchanged."""
        for node in nodes:
            key = node.hash or node.id_
            if not key or not _stable_sample(key, self._sample_mod):
                continue
            text_len = len(node.get_content(metadata_mode=self._metadata_mode))
            meta_keys = sorted(node.metadata.keys()) if node.metadata else []
            logger.info(
                f"pipeline_snapshot label={self._label} id={node.id_} "
                f"ref_doc_id={getattr(node, 'ref_doc_id', None)} hash={node.hash} "
                f"text_len={text_len} meta_keys={meta_keys}"
            )
        return nodes


class TracingDocstore(BaseDocumentStore):
    """Docstore wrapper that logs access patterns and hash decisions.
    Usage:
    1. Without caching:
        docstore = TracingDocstore(SimpleDocumentStore())

    2. Modify your cached pipelin'es docstore after cache load:
        # existing code
        load_pipeline(dataset_name, pipeline)

        # add this to attach tracing after loading (so we can see cache hits/misses)
        if pipeline.docstore is not None:
            pipeline.docstore = TracingDocstore(
                pipeline.docstore,
                label="docstore",
                sample_mod=1,  # set to 1 to verify logs
            )

    """

    def __init__(
        self,
        inner: BaseDocumentStore,
        *,
        label: str = "docstore",
        sample_mod: int = 100,
    ) -> None:
        """Initialize the tracing wrapper.

        Args:
            inner: The docstore to wrap.
            label: Log label for grouping.
            sample_mod: Deterministic sampling modulus (1 = log all).
        """
        self._inner = inner
        self._label = label
        self._sample_mod = max(1, sample_mod)

    def _sample(self, key: str) -> bool:
        """Determine if a key should be logged."""
        return _stable_sample(key, self._sample_mod)

    def persist(
        self,
        persist_path: str = DEFAULT_PERSIST_PATH,
        fs: Optional[Any] = None,
    ) -> None:
        """Persist the wrapped docstore and log the operation."""
        self._inner.persist(persist_path=persist_path, fs=fs)
        logger.info(f"docstore_persist label={self._label} path={persist_path}")

    @property
    def docs(self) -> Dict[str, BaseNode]:
        """Return all documents from the wrapped docstore."""
        return self._inner.docs

    def add_documents(
        self,
        docs: Sequence[BaseNode],
        allow_update: bool = True,
        batch_size: int = DEFAULT_BATCH_SIZE,
        store_text: bool = True,
    ) -> None:
        """Add documents and log a sampled subset."""
        self._inner.add_documents(
            docs,
            allow_update=allow_update,
            batch_size=batch_size,
            store_text=store_text,
        )
        logger.info(
            f"docstore_add_documents label={self._label} count={len(docs)}"
        )
        for doc in docs:
            key = doc.hash or doc.id_
            if key and self._sample(key):
                logger.info(
                    f"docstore_add_document label={self._label} id={doc.id_} "
                    f"ref_doc_id={getattr(doc, 'ref_doc_id', None)} hash={doc.hash}"
                )

    async def async_add_documents(
        self,
        docs: Sequence[BaseNode],
        allow_update: bool = True,
        batch_size: int = DEFAULT_BATCH_SIZE,
        store_text: bool = True,
    ) -> None:
        """Async add documents and log a sampled subset."""
        await self._inner.async_add_documents(
            docs,
            allow_update=allow_update,
            batch_size=batch_size,
            store_text=store_text,
        )
        logger.info(
            f"docstore_async_add_documents label={self._label} count={len(docs)}"
        )

    def get_document(
        self, doc_id: str, raise_error: bool = True
    ) -> Optional[BaseNode]:
        """Get a document and log the request."""
        doc = self._inner.get_document(doc_id, raise_error=raise_error)
        if self._sample(doc_id):
            logger.info(
                f"docstore_get_document label={self._label} doc_id={doc_id}"
            )
        return doc

    async def aget_document(
        self, doc_id: str, raise_error: bool = True
    ) -> Optional[BaseNode]:
        """Async get a document and log the request."""
        doc = await self._inner.aget_document(doc_id, raise_error=raise_error)
        if self._sample(doc_id):
            logger.info(
                f"docstore_aget_document label={self._label} doc_id={doc_id}"
            )
        return doc

    def delete_document(self, doc_id: str, raise_error: bool = True) -> None:
        """Delete a document and log the operation."""
        self._inner.delete_document(doc_id, raise_error=raise_error)
        if self._sample(doc_id):
            logger.info(
                f"docstore_delete_document label={self._label} doc_id={doc_id}"
            )

    async def adelete_document(self, doc_id: str, raise_error: bool = True) -> None:
        """Async delete a document and log the operation."""
        await self._inner.adelete_document(doc_id, raise_error=raise_error)
        if self._sample(doc_id):
            logger.info(
                f"docstore_adelete_document label={self._label} doc_id={doc_id}"
            )

    def document_exists(self, doc_id: str) -> bool:
        """Check if a document exists and log sampled checks."""
        exists = self._inner.document_exists(doc_id)
        if self._sample(doc_id):
            logger.info(
                f"docstore_document_exists label={self._label} doc_id={doc_id} "
                f"exists={exists}"
            )
        return exists

    async def adocument_exists(self, doc_id: str) -> bool:
        """Async check for document existence and log sampled checks."""
        exists = await self._inner.adocument_exists(doc_id)
        if self._sample(doc_id):
            logger.info(
                f"docstore_adocument_exists label={self._label} doc_id={doc_id} "
                f"exists={exists}"
            )
        return exists

    def set_document_hash(self, doc_id: str, doc_hash: str) -> None:
        """Set a document hash and log sampled updates."""
        self._inner.set_document_hash(doc_id, doc_hash)
        if self._sample(doc_id):
            logger.info(
                f"docstore_set_document_hash label={self._label} doc_id={doc_id} "
                f"hash={doc_hash}"
            )

    async def aset_document_hash(self, doc_id: str, doc_hash: str) -> None:
        """Async set a document hash and log sampled updates."""
        await self._inner.aset_document_hash(doc_id, doc_hash)
        if self._sample(doc_id):
            logger.info(
                f"docstore_aset_document_hash label={self._label} doc_id={doc_id} "
                f"hash={doc_hash}"
            )

    def set_document_hashes(self, doc_hashes: Dict[str, str]) -> None:
        """Set multiple document hashes and log counts."""
        self._inner.set_document_hashes(doc_hashes)
        logger.info(
            f"docstore_set_document_hashes label={self._label} count={len(doc_hashes)}"
        )

    async def aset_document_hashes(self, doc_hashes: Dict[str, str]) -> None:
        """Async set multiple document hashes and log counts."""
        await self._inner.aset_document_hashes(doc_hashes)
        logger.info(
            f"docstore_aset_document_hashes label={self._label} count={len(doc_hashes)}"
        )

    def get_document_hash(self, doc_id: str) -> Optional[str]:
        """Get a document hash and log sampled lookups."""
        doc_hash = self._inner.get_document_hash(doc_id)
        if self._sample(doc_id):
            logger.info(
                f"docstore_get_document_hash label={self._label} doc_id={doc_id} "
                f"hash={doc_hash}"
            )
        return doc_hash

    async def aget_document_hash(self, doc_id: str) -> Optional[str]:
        """Async get a document hash and log sampled lookups."""
        doc_hash = await self._inner.aget_document_hash(doc_id)
        if self._sample(doc_id):
            logger.info(
                f"docstore_aget_document_hash label={self._label} doc_id={doc_id} "
                f"hash={doc_hash}"
            )
        return doc_hash

    def get_all_document_hashes(self) -> Dict[str, str]:
        """Return all document hashes and log the count."""
        hashes = self._inner.get_all_document_hashes()
        logger.info(
            f"docstore_get_all_document_hashes label={self._label} count={len(hashes)}"
        )
        return hashes

    async def aget_all_document_hashes(self) -> Dict[str, str]:
        """Async return all document hashes and log the count."""
        hashes = await self._inner.aget_all_document_hashes()
        logger.info(
            f"docstore_aget_all_document_hashes label={self._label} count={len(hashes)}"
        )
        return hashes

    def get_all_ref_doc_info(self) -> Optional[Dict[str, RefDocInfo]]:
        """Return all ref doc info and log the count."""
        info = self._inner.get_all_ref_doc_info()
        logger.info(
            f"docstore_get_all_ref_doc_info label={self._label} "
            f"count={len(info or {})}"
        )
        return info

    async def aget_all_ref_doc_info(self) -> Optional[Dict[str, RefDocInfo]]:
        """Async return all ref doc info and log the count."""
        info = await self._inner.aget_all_ref_doc_info()
        logger.info(
            f"docstore_aget_all_ref_doc_info label={self._label} "
            f"count={len(info or {})}"
        )
        return info

    def get_ref_doc_info(self, ref_doc_id: str) -> Optional[RefDocInfo]:
        """Get ref doc info and log sampled lookups."""
        info = self._inner.get_ref_doc_info(ref_doc_id)
        if self._sample(ref_doc_id):
            logger.info(
                f"docstore_get_ref_doc_info label={self._label} ref_doc_id={ref_doc_id}"
            )
        return info

    async def aget_ref_doc_info(self, ref_doc_id: str) -> Optional[RefDocInfo]:
        """Async get ref doc info and log sampled lookups."""
        info = await self._inner.aget_ref_doc_info(ref_doc_id)
        if self._sample(ref_doc_id):
            logger.info(
                f"docstore_aget_ref_doc_info label={self._label} ref_doc_id={ref_doc_id}"
            )
        return info

    def delete_ref_doc(self, ref_doc_id: str, raise_error: bool = True) -> None:
        """Delete a ref doc and log the operation."""
        self._inner.delete_ref_doc(ref_doc_id, raise_error=raise_error)
        if self._sample(ref_doc_id):
            logger.info(
                f"docstore_delete_ref_doc label={self._label} ref_doc_id={ref_doc_id}"
            )

    async def adelete_ref_doc(self, ref_doc_id: str, raise_error: bool = True) -> None:
        """Async delete a ref doc and log the operation."""
        await self._inner.adelete_ref_doc(ref_doc_id, raise_error=raise_error)
        if self._sample(ref_doc_id):
            logger.info(
                f"docstore_adelete_ref_doc label={self._label} ref_doc_id={ref_doc_id}"
            )


class DebugPipeline(IngestionPipeline):
    """IngestionPipeline with deterministic sampling logs for dedup stages."""

    trace_label: str = "pipeline"
    trace_sample_mod: int = 100

    def _sample(self, key: str) -> bool:
        """Determine if a key should be logged."""
        return _stable_sample(key, max(1, self.trace_sample_mod))

    def _summarize_nodes(self, nodes: Sequence[BaseNode]) -> List[Dict[str, Any]]:
        """Build a sampled summary of nodes."""
        summaries: List[Dict[str, Any]] = []
        for node in nodes:
            key = node.hash or node.id_
            if not key or not self._sample(key):
                continue
            summaries.append(
                {
                    "id": node.id_,
                    "ref_doc_id": getattr(node, "ref_doc_id", None),
                    "hash": node.hash,
                }
            )
        return summaries

    def _handle_upserts(self, nodes: Sequence[BaseNode]) -> Sequence[BaseNode]:
        """Log upsert dedup decisions and delegate to the base implementation."""
        logger.info(
            f"pipeline_upserts_input label={self.trace_label} count={len(nodes)} "
            f"sample={self._summarize_nodes(nodes)}"
        )
        result = super()._handle_upserts(nodes)
        logger.info(
            f"pipeline_upserts_output label={self.trace_label} count={len(result)} "
            f"sample={self._summarize_nodes(result)}"
        )
        return result

    def _handle_duplicates(self, nodes: Sequence[BaseNode]) -> Sequence[BaseNode]:
        """Log duplicate-only dedup decisions and delegate to the base implementation."""
        logger.info(
            f"pipeline_duplicates_input label={self.trace_label} count={len(nodes)} "
            f"sample={self._summarize_nodes(nodes)}"
        )
        result = super()._handle_duplicates(nodes)
        logger.info(
            f"pipeline_duplicates_output label={self.trace_label} count={len(result)} "
            f"sample={self._summarize_nodes(result)}"
        )
        return result
