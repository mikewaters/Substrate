"""catalog.transform - Custom LlamaIndex TransformComponent classes.

Used by catalog pipelines for persistence and ontology mapping.
Indexing transforms (FTS, chunking, embedding, splitting) have moved to `index.transform`.
"""

from __future__ import annotations

from importlib import import_module

__all__ = [
    "MimeDetector",
    "OntologyMapper",
    "TextNormalizer",
    "TextNormalizerTransform",
    "TextPolicy",
    "detect_mime",
    "is_text_file",
    "is_text_mime",
]

_SYMBOL_TO_MODULE = {
    "TextNormalizerTransform": "catalog.transform.llama",
    "MimeDetector": "agentlayer.normalize",
    "TextNormalizer": "agentlayer.normalize",
    "TextPolicy": "agentlayer.normalize",
    "detect_mime": "agentlayer.normalize",
    "is_text_file": "agentlayer.normalize",
    "is_text_mime": "agentlayer.normalize",
    "OntologyMapper": "catalog.transform.ontology",
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
