"""index.transform - LlamaIndex TransformComponent classes for indexing.

Provides transforms for FTS indexing, chunking, embedding, and splitting.
"""

from __future__ import annotations

from importlib import import_module

__all__ = [
    "Chunk",
    "ChunkerTransform",
    "ChunkPersistenceTransform",
    "ChunkPersistenceStats",
    "DocumentFTSTransform",
    "EmbeddingIdentityTransform",
    "EmbeddingPrefixTransform",
    "LineChunker",
    "ResilientSplitter",
    "SizeAwareChunkSplitter",
]

_SYMBOL_TO_MODULE = {
    "Chunk": "index.transform.chunker",
    "ChunkerTransform": "index.transform.chunker",
    "LineChunker": "index.transform.chunker",
    "ChunkPersistenceTransform": "index.transform.llama",
    "ChunkPersistenceStats": "index.transform.llama",
    "DocumentFTSTransform": "index.transform.llama",
    "EmbeddingIdentityTransform": "index.transform.embedding",
    "EmbeddingPrefixTransform": "index.transform.embedding",
    "ResilientSplitter": "index.transform.splitter",
    "SizeAwareChunkSplitter": "index.transform.splitter",
}


def __getattr__(name: str):
    """Lazily resolve transform symbols to avoid import-time cycles."""
    module_name = _SYMBOL_TO_MODULE.get(name)
    if module_name is None:
        raise AttributeError(f"module 'index.transform' has no attribute {name!r}")

    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value
