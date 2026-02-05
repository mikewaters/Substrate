"""catalog.ingest - Source management and ingestion pipelines.

Abstractions for reading, parsing, and extracting from dataset sources,
and pipelines for ingesting documents into the catalog.
"""

from catalog.ingest.directory import DirectorySource
from catalog.ingest.pipelines import DatasetIngestPipeline
from catalog.ingest.pipelines_v2 import DatasetIngestPipelineV2

__all__ = [
    "DatasetIngestPipeline",
    "DatasetIngestPipelineV2",
    "DirectorySource",
]
