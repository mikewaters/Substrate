"""catalog.sync - Orchestrates ingest -> index for dataset jobs.

DatasetSync replaces the old IndexSync (catalog/index/index.py) and serves as
the single entry point for running full dataset synchronization: ingest first,
then index. Each stage is independently usable -- this module coordinates them.

Usage::

    from catalog.sync import DatasetSync

    sync = DatasetSync()
    sync.load_jobs()
    asyncio.run(sync.arun())

Or for a single config::

    result = sync.sync(config)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List

from agentlayer.logging import get_logger
from pydantic import BaseModel, Field

from catalog.core.settings import get_settings
from index.pipelines import DatasetIndexPipeline
from index.pipelines.schemas import IndexResult
from catalog.ingest.job import DatasetJob
from catalog.ingest.pipelines import DatasetIngestPipeline
from catalog.ingest.schemas import IngestResult
from catalog.ingest.sources import DatasetSourceConfig
from catalog.store.database import get_session
from agentlayer.session import use_session

__all__ = [
    "DatasetSync",
    "SyncResult",
]

logger = get_logger(__name__)


class SyncResult(BaseModel):
    """Composite result of an ingest + index cycle.

    Attributes:
        ingest: Result from the ingest stage.
        index: Result from the index stage.
    """

    ingest: IngestResult
    index: IndexResult


class DatasetSync:
    """Orchestrates ingest -> index for dataset jobs.

    Loads job configs from YAML, runs ingest for each, then runs index.
    """

    def __init__(
        self,
        base_dir: Path | None = None,
        per_job_concurrency: int = 1,
    ) -> None:
        self._pipelines: List[DatasetIngestPipeline] = []
        self._configs: List[DatasetSourceConfig] = []
        self.base_dir = base_dir or get_settings().job_config_path
        self.per_job_concurrency = per_job_concurrency

    def sync(self, config: DatasetSourceConfig) -> SyncResult:
        """Run ingest then index for a single dataset.

        Args:
            config: Source configuration for the dataset.

        Returns:
            SyncResult with both ingest and index results.
        """
        ingest_pipeline = DatasetIngestPipeline(ingest_config=config)
        ingest_result = ingest_pipeline.ingest()

        index_pipeline = DatasetIndexPipeline(
            dataset_id=ingest_result.dataset_id,
            dataset_name=ingest_result.dataset_name,
        )

        with get_session() as session:
            with use_session(session):
                index_result = index_pipeline.index()

        return SyncResult(ingest=ingest_result, index=index_result)

    def load_jobs(self) -> None:
        """Load job configurations from YAML files in base_dir."""
        self._pipelines = []
        self._configs = []

        logger.info(f"Loading jobs from {self.base_dir}")
        base_dir = self.base_dir
        if not base_dir.exists():
            logger.warning(f"Job config directory does not exist: {base_dir}")
            return
        if not base_dir.is_dir():
            logger.error(f"Job config path is not a directory: {base_dir}")
            return

        for path in base_dir.iterdir():
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            if suffix not in (".yaml", ".yml"):
                continue

            try:
                job = DatasetJob.from_yaml(path)
                config = job.to_ingest_config()
                self._configs.append(config)
                logger.debug(f"Loaded job config: {path.name}")
            except Exception as e:
                logger.error(f"Failed to load job config {path}: {e}")

    async def arun(self) -> list[SyncResult]:
        """Run all configured jobs, each as ingest -> index.

        Returns:
            List of SyncResult for each job.
        """
        if not self._configs:
            logger.warning("No configs to run. Did you call load_jobs()?")
            return []

        logger.info(f"Starting execution of {len(self._configs)} jobs")

        tasks = []
        for config in self._configs:
            tasks.append(asyncio.to_thread(self.sync, config))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        sync_results: list[SyncResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Job {i} failed with error: {result}")
            else:
                logger.info(f"Job {i} completed successfully")
                sync_results.append(result)

        return sync_results


if __name__ == "__main__":
    import sys

    from agentlayer.logging import configure_logging

    configure_logging(level="DEBUG")

    if len(sys.argv) < 2:
        print("Usage: python -m catalog.sync <job_config_dir>")
        sys.exit(1)

    target = Path(sys.argv[1])

    sync = DatasetSync(base_dir=target)
    sync.load_jobs()
    asyncio.run(sync.arun())
