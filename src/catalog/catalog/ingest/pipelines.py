"""catalog.ingest.pipelines - Dataset ingestion pipeline.

Handles source acquisition, dataset creation, ontology mapping, and document
DB persistence. Returns after persistence -- indexing is handled separately
by DatasetIndexPipeline via the DatasetSync orchestrator.

Change detection is handled by LlamaIndex's docstore, which uses
SHA256(text + metadata) to detect changes. This catches frontmatter-only
changes that the old body-only hash missed. The docstore is persisted
between runs so only new/changed documents are reprocessed.

Deletion detection uses DocstoreStrategy.UPSERTS_AND_DELETE: documents
present in the docstore but not in the current batch are removed from
the docstore, vector store, and marked inactive in the SQLite DB.

Pipeline flow:
1. LlamaIndex docstore filters unchanged documents (upstream)
2. OntologyMapper
3. PersistenceTransform (upsert to documents table, DB-only)
4. Source-specific post-persist transforms
5. Post-pipeline deletion sync (deactivate removed docs in SQLite)
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import cached_property
from typing import Optional, Sequence

from agentlayer.logging import get_logger
from llama_index.core.ingestion import DocstoreStrategy, IngestionPipeline
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.schema import BaseNode, TransformComponent

from agentlayer.pipeline import BasePipeline
from catalog.ingest.cache import (
    clear_cache,
    load_pipeline,
    persist_pipeline,
)
from catalog.ingest.schemas import IngestResult
from catalog.ingest.sources import BaseSource, create_source, DatasetSourceConfig
from catalog.ingest.tracing import TracingDocstore
from catalog.store.database import get_session
from catalog.store.dataset import DatasetService
from catalog.store.repositories import DatasetRepository, DocumentRepository
from agentlayer.session import use_session
from index.store.vector import VectorStoreManager
from catalog.transform.links import LinkResolutionTransform
from catalog.transform.ontology import OntologyMapper
from catalog.transform.llama import PersistenceTransform

__all__ = [
    "DatasetIngestPipeline",
]

logger = get_logger(__name__)


class DatasetIngestPipeline(BasePipeline):
    """Dataset ingestion: source acquisition, ontology mapping, DB persistence.

    Entry points:
        - ingest_dataset(config) - Takes config as argument
        - ingest() - Uses self.ingest_config

    Attributes:
        ingest_config: Configuration for ingestion. Required for ingest().

    The goals of an IngestionPipeline are:
    1. Populate the Index to facilitate search;
    2. Populate the Catalog with references to the new resources to facilitate retrieval;
    3. Ensure that resource content metadata is abstracted from the original source application,
    and is in a common format to be used broadly.

    Non-goals are:
    1. Performing rich classification up-front.
    2. Translate documenht metadata into the Ontology
    3. Asociate documents with non-dataset members.
    """

    ingest_config: Optional[DatasetSourceConfig] = None

    @cached_property
    def _settings(self):
        """Get RAG settings from catalog configuration."""
        from catalog.core.settings import get_settings
        return get_settings().rag

    @cached_property
    def source(self) -> BaseSource:
        """Create the source from self.ingest_config."""
        return create_source(self.ingest_config)

    def _get_transforms(self) -> list[TransformComponent]:
        """Get document-level transforms for the dataset.

        Returns only document-level transforms: ontology mapping, DB
        persistence, and source-specific post-persist hooks.  Chunking,
        embedding, and FTS are handled by DatasetIndexPipeline.
        """
        #
        # Document-level transformations, including persistence
        # Varies-by:
        # - data source-specific Ontology mapping
        #
        #from catalog.ingest.tracing import DebugPipeline, TracingDocstore, SnapshotTransform
        # Document-level transformation, followed by document persistence and cross-dataset normalization
        transforms = [
            OntologyMapper(
                ontology_spec_cls=getattr(self.source, "ontology_spec", None),
            ),
            PersistenceTransform(
                dataset_id=self.dataset_id,
                dataset_name=self.dataset_name,
            )
        ] + self.source.transforms(dataset_id=self.dataset_id)

        # Link resolution runs last -- needs doc_id from persistence
        resolver = self.source.link_resolver
        if resolver is not None:
            transforms.append(LinkResolutionTransform(
                dataset_id=self.dataset_id,
                resolver=resolver,
            ))

        return transforms

    def build_pipeline(
        self,
        vector_manager: VectorStoreManager,
        incremental: bool = False,
    ) -> IngestionPipeline:
        """Build the ingestion pipeline.

        Args:
            vector_manager: Vector store manager (needed for docstore strategy).
            incremental: If True, use UPSERTS strategy instead of
                UPSERTS_AND_DELETE to avoid deleting unchanged documents
                that are absent from the partial batch.

        Returns:
            Configured IngestionPipeline ready to run.
        """
        transformations = self._get_transforms()

        # Create pipeline with docstore for change detection and deduplication.
        # LlamaIndex's docstore uses SHA256(text + metadata) for change detection,
        # which catches frontmatter-only changes that our old body-only hash missed.
        docstore = SimpleDocumentStore(namespace=self.dataset_name)
        vector_store = vector_manager.get_vector_store()

        # In incremental mode, use UPSERTS to avoid deleting docstore/vector
        # entries for documents not in the partial batch.
        if incremental:
            strategy = DocstoreStrategy.UPSERTS
        else:
            strategy = DocstoreStrategy.UPSERTS_AND_DELETE

        # Guard: UPSERTS_AND_DELETE silently downgrades to DUPLICATES_ONLY
        # without a vector store, losing upsert and deletion semantics.
        if vector_store is None and strategy == DocstoreStrategy.UPSERTS_AND_DELETE:
            raise ValueError(
                "Vector store is required for DocstoreStrategy.UPSERTS_AND_DELETE. "
                "Without it, LlamaIndex silently downgrades to DUPLICATES_ONLY."
            )

        pipeline = IngestionPipeline(
            transformations=transformations,
            docstore=docstore,
            docstore_strategy=strategy,
            vector_store=vector_store,
        )

        # Load cached pipeline state if available
        load_pipeline(self.dataset_name, pipeline)

        if self._settings.tracing:
            # Wrap the pipeline's docstore with a trace
            pipeline.docstore = TracingDocstore(
                pipeline.docstore,
                label=self.dataset_name,
                sample_mod=1,  # set to 1 to verify logs
            )

        return pipeline

    def ingest(self) -> IngestResult:
        """Ingest documents using the pipeline.

        Persists documents to the database. Returns after persistence --
        indexing is handled separately by the caller (DatasetSync).

        Returns:
            IngestResult with statistics about the operation.

        Raises:
            ValueError: If ingest_config is not set.
        """
        if self.ingest_config is None:
            raise ValueError(
                "ingest_config is required. Use ingest_dataset(config) instead."
            )

        started_at = datetime.now(tz=timezone.utc)

        logger.info(f"Starting ingestion: {self.ingest_config.source_path}")

        result = IngestResult(
            dataset_id=0,
            dataset_name="",
            started_at=started_at,
        )

        with get_session() as session:
            with use_session(session):
                # Get or create dataset — use config fields (not self.source)
                # so source creation is deferred until after incremental
                # resolution below.
                dataset = DatasetService.create_or_update(
                    session,
                    self.ingest_config.dataset_name,
                    source_type=self.ingest_config.type_name,
                    source_path=str(self.ingest_config.source_path),
                    catalog_name=self.ingest_config.catalog_name,
                )
                self.dataset_id = dataset.id
                self.dataset_name = dataset.name

                # Resolve incremental flag to if_modified_since before
                # accessing self.source (which triggers file filtering).
                is_incremental = self.ingest_config.if_modified_since is not None
                if self.ingest_config.incremental and not is_incremental:
                    if dataset.last_ingested_at is not None:
                        self.ingest_config.if_modified_since = dataset.last_ingested_at
                        is_incremental = True
                        logger.info(
                            f"Incremental mode: filtering files modified since "
                            f"{dataset.last_ingested_at}"
                        )
                    else:
                        logger.info(
                            "Incremental mode: new dataset, running full ingestion"
                        )

                # Handle forced ingestion
                vector_manager: VectorStoreManager = VectorStoreManager()
                if self.ingest_config.force:
                    deleted: int = vector_manager.delete_by_dataset(dataset.name)
                    if deleted > 0:
                        logger.info(
                            f"Force mode: cleared {deleted} vectors for "
                            f"dataset '{dataset.name}'"
                        )
                    clear_cache(self._cache_key(dataset.name))

                # Build and run pipeline
                pipeline: IngestionPipeline = self.build_pipeline(
                    vector_manager=vector_manager,
                    incremental=is_incremental,
                )

                source_docs: Callable[[], None] = self.source.documents
                logger.info(
                    f"Running {len(source_docs)} documents through pipeline"
                )
                # SQLite does not support concurrent writers from multiple
                # processes; persistence transforms write to SQLite, so use 1.
                nodes: Sequence[BaseNode] = pipeline.run(
                    documents=source_docs, num_workers=1
                )

                # Collect statistics from transforms
                persist_transform = None
                for t in pipeline.transformations:
                    if isinstance(t, PersistenceTransform):
                        persist_transform = t

                # Deletion sync: mark documents not in the current batch
                # as inactive in our SQLite DB. LlamaIndex already handled
                # deletion in the docstore and vector store via
                # UPSERTS_AND_DELETE; this mirrors that to our DB.
                #
                # Skip in incremental mode: only a subset of files were
                # loaded, so missing docs are simply not-yet-modified,
                # not deleted.
                deactivated = 0
                if not is_incremental:
                    batch_paths = {
                        doc.metadata.get("relative_path", doc.id_)
                        for doc in source_docs
                    }
                    doc_repo = DocumentRepository()
                    deactivated = doc_repo.deactivate_missing(
                        dataset.id, batch_paths
                    )
                    if deactivated > 0:
                        logger.info(
                            f"Deletion sync: deactivated {deactivated} documents "
                            f"not in current batch"
                        )

                # Stamp last_ingested_at on the dataset
                ds_repo = DatasetRepository(session)
                dataset_orm = ds_repo.get_by_id(dataset.id)
                dataset_orm.last_ingested_at = datetime.now(tz=timezone.utc)

                session.flush()

                if persist_transform:
                    result.documents_created = persist_transform.stats.created
                    result.documents_updated = persist_transform.stats.updated
                    result.documents_failed = persist_transform.stats.failed
                    result.errors = list(persist_transform.stats.errors)

                result.documents_read = len(source_docs)
                result.dataset_id = dataset.id
                result.dataset_name = dataset.name
                result.documents_deactivated = deactivated

                # Derive skipped count: docs in batch that weren't
                # created or updated were filtered by LlamaIndex's
                # docstore as unchanged.
                total_processed = (
                    (persist_transform.stats.created + persist_transform.stats.updated)
                    if persist_transform else 0
                )
                result.documents_skipped = len(source_docs) - total_processed

                # Persist pipeline cache state
                persist_pipeline(dataset.name, pipeline)

                result.completed_at = datetime.now(tz=timezone.utc)

                logger.info(
                    f"Ingestion complete: "
                    f"created={result.documents_created}, "
                    f"updated={result.documents_updated}, "
                    f"skipped={result.documents_skipped}, "
                    f"deactivated={result.documents_deactivated}, "
                    f"failed={result.documents_failed}"
                )

                return result

    def ingest_dataset(self, config: DatasetSourceConfig) -> IngestResult:
        """Ingest documents using the provided config.

        Creates a new pipeline instance with the given config and runs ingestion.

        Args:
            config: Dataset ingestion configuration.

        Returns:
            IngestResult with statistics about the operation.
        """
        pipeline = DatasetIngestPipeline(
            ingest_config=config,
            embed_model=self.embed_model,
            resilient_embedding=self.resilient_embedding,
        )
        return pipeline.ingest()

if __name__ == "__main__":
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

    if target.suffix in (".yaml", ".yml"):
        pipeline = DatasetIngestPipeline.from_job_config(target)
    else:
        config = SourceHeptabaseConfig(source_path=target, force=force, catalog_name='pkm')
        pipeline = DatasetIngestPipeline(ingest_config=config)

    result = pipeline.ingest()

    print(result.model_dump_json(indent=2))
