import asyncio
from typing import List
from pathlib import Path
from loguru import logger
from attrs import define, field
from catalog.ingest.job import DatasetJob
from catalog.ingest.pipelines import DatasetIngestPipeline
from catalog.core.settings import get_settings

# Assumed imports based on project structure patterns described in AGENTS.md
# We will need to adjust these paths if the actual class locations differ.
# Assuming Job is a domain config object
# Assuming IngestionPipeline is the runner
# Assuming a way to load configs exists, or we pass them in.
# For now, we'll assume the Index is initialized with them or loads them.

@define
class Index:
    """
    Class for managing and executing ingestion pipelines.

    This class is responsible for instantiating IngestionPipelines based on
    provided Job configurations and executing them.
    """
    _pipelines: List[DatasetIngestPipeline] = field(factory=list)
    #_jobs: List[Job] = field(factory=list)
    base_dir: Path = field(default=get_settings().job_config_path)

    def load_jobs(self) -> None:
        """
        Loads job configurations and prepares pipelines.
        """
        #self._jobs = jobs
        self._pipelines = []

        logger.info(f"Loading jobs from {self.base_dir} into Index")
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
                pipeline = DatasetIngestPipeline(
                    ingest_config=job.to_ingest_config()
                )
                self._pipelines.append(pipeline)
                logger.debug(f"Created pipeline for job config: {path.name}")
            except Exception as e:
                logger.error(f"Failed to load job config {path}: {e}")

    async def run(self) -> None:
        """
        Executes all loaded pipelines concurrently.
        """
        if not self._pipelines:
            logger.warning("No pipelines to run. Did you call load_jobs()?")
            return

        logger.info(f"Starting execution of {len(self._pipelines)} pipelines")

        tasks = []
        for pipeline in self._pipelines:
            tasks.append(asyncio.to_thread(pipeline.ingest))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Pipeline {i} failed with error: {result}")
            else:
                logger.info(f"Pipeline {i} completed successfully")


if __name__ == '__main__':
    import sys
    from agentlayer.logging import get_logger, configure_logging
    from catalog.integrations.obsidian import SourceObsidianConfig
    from catalog.integrations.heptabase import SourceHeptabaseConfig

    configure_logging(level="DEBUG")
    if len(sys.argv) < 2:
        print("Usage: python -m catalog.ingest.pipelines <source_dir_or_yaml> [--force]")
        sys.exit(1)

    from pathlib import Path

    force = "--force" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--force"]
    target = Path(args[0])

    if target.is_dir():

        index = Index(base_dir=target)
        index.load_jobs()
        asyncio.run(index.run())
