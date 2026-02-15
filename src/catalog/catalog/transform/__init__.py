"""catalog.transform - Custom LlamaIndex TransformComponent classes.

Used by catalog pipelines to gather metadata and transform resource content for
persistence and indexing.
"""

from __future__ import annotations

from importlib import import_module

__all__ = [
    "Chunk",
    "ChunkerTransform",
    "EmbeddingIdentityTransform",
    "EmbeddingPrefixTransform",
    "FTSIndexerTransform",
    "LineChunker",
    "MimeDetector",
    "OntologyMapper",
    "ResilientSplitter",
    "SizeAwareChunkSplitter",
    "TextNormalizer",
    "TextNormalizerTransform",
    "TextPolicy",
    "detect_mime",
    "is_text_file",
    "is_text_mime",
]

_SYMBOL_TO_MODULE = {
    "Chunk": "catalog.transform.chunker",
    "ChunkerTransform": "catalog.transform.chunker",
    "LineChunker": "catalog.transform.chunker",
    "EmbeddingIdentityTransform": "catalog.transform.embedding",
    "EmbeddingPrefixTransform": "catalog.transform.embedding",
    "FTSIndexerTransform": "catalog.transform.llama",
    "TextNormalizerTransform": "catalog.transform.llama",
    "MimeDetector": "catalog.transform.normalize",
    "TextNormalizer": "catalog.transform.normalize",
    "TextPolicy": "catalog.transform.normalize",
    "detect_mime": "catalog.transform.normalize",
    "is_text_file": "catalog.transform.normalize",
    "is_text_mime": "catalog.transform.normalize",
    "OntologyMapper": "catalog.transform.ontology",
    "ResilientSplitter": "catalog.transform.splitter",
    "SizeAwareChunkSplitter": "catalog.transform.splitter",
}


def __getattr__(name: str):
    """Lazily resolve transform symbols to avoid import-time cycles."""
    module_name = _SYMBOL_TO_MODULE.get(name)
    if module_name is None:
        raise AttributeError(f"module 'catalog.transform' has no attribute {name!r}")

    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value
