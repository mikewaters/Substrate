"""catalog.transform - Custom LlamaIndex TransformComponent classes.

Used by catalog.pipelines to gather metadata and transform resource content
for persistence and indexing.
"""

from catalog.transform.chunker import Chunk, ChunkerTransform, LineChunker
from catalog.transform.embedding import EmbeddingPrefixTransform
from catalog.integrations.obsidian.transforms import FrontmatterTransform
from catalog.transform.llama import FTSIndexerTransform, TextNormalizerTransform
from catalog.transform.normalize import (
                                     MimeDetector,
                                     TextNormalizer,
                                     TextPolicy,
                                     detect_mime,
                                     is_text_file,
                                     is_text_mime,
)
from catalog.transform.splitter import ResilientSplitter, SizeAwareChunkSplitter

__all__ = [
    "Chunk",
    "ChunkerTransform",
    "EmbeddingPrefixTransform",
    "FTSIndexerTransform",
    "LineChunker",
    "MimeDetector",
    "ResilientSplitter",
    "SizeAwareChunkSplitter",
    "TextNormalizer",
    "TextNormalizerTransform",
    "TextPolicy",
    "detect_mime",
    "is_text_file",
    "is_text_mime",
]
