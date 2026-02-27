from pydantic import BaseModel
from agentlayer.logging import get_logger


__all__ = [
    "DatasetIngestPipeline",
]

logger = get_logger(__name__)


class DatasetIngestPipeline(BaseModel):
    """Pipeline for indexing a dataset."""

    dataset_id: int
    dataset_name: str

    def run(self):
        """Run the pipeline."""
        pass
