"""catalog.transform - Custom LlamaIndex TransformComponent classes.

Used by catalog.pipelines to gather metadata and transform resource content
for persistence and indexing.
"""

from catalog.transform.chunker import Chunk, ChunkerTransform, LineChunker
from catalog.transform.llama import FTSIndexerTransform, TextNormalizerTransform
from catalog.transform.normalize import (
                                     MimeDetector,
                                     TextNormalizer,
                                     TextPolicy,
                                     detect_mime,
                                     is_text_file,
                                     is_text_mime,
)
from catalog.transform.obsidian import ObsidianEnrichmentTransform
from catalog.transform.splitter import SizeAwareChunkSplitter

__all__ = [
    "Chunk",
    "ChunkerTransform",
    "FTSIndexerTransform",
    "LineChunker",
    "MimeDetector",
    "ObsidianEnrichmentTransform",
    "SizeAwareChunkSplitter",
    "TextNormalizer",
    "TextNormalizerTransform",
    "TextPolicy",
    "detect_mime",
    "is_text_file",
    "is_text_mime",
]
