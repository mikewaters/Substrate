"""Dataset loader for YAML fixtures.

This utility loads datasets from YAML files into an existing SQLAlchemy session.
It supports loading entities across all ontology modules:
 - Information: Taxonomy, Topic, TopicEdge, TopicClosure, TopicSuggestion, Match
 - Work: Activity
 - Catalog: Catalog, Repository, Purpose, Resource (and subtypes)

This loader intentionally uses deterministic string IDs to simplify tests.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Literal

import yaml
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ontology.relational.models import Catalog, Purpose, Repository, Resource
from ontology.relational.repository.catalog import (
    CatalogRepository,
    PurposeRepository,
    RepositoryRepository,
    ResourceRepository,
)
from ontology.relational.models import (
    DocumentClassification,
    DocumentTopicAssignment,
    Match,
    Taxonomy,
    Topic,
    TopicClosure,
    TopicEdge,
    TopicSuggestion,
)
from ontology.relational.repository import (
    DocumentClassificationRepository,
    TopicEdgeRepository,
    TopicRepository,
    TopicSuggestionRepository,
)
from ontology.relational.repository import TaxonomyRepository
from ontology.relational.models import Activity
from ontology.relational.repository.work import ActivityRepository

logger = logging.getLogger(__name__)


class DatasetLoaderError(Exception):
    """Base exception for dataset loading errors."""

    pass


async def load_yaml_dataset(path: str | Path, db: AsyncSession) -> dict[str, Any]:
    """Load all YAML dataset files from a directory or single file.

    Args:
        path: Path to directory of YAML dataset files or single YAML file
        db: SQLAlchemy session

    Logic:
        1. Load taxonomy/topic dataset (sample_taxonomies.yaml)
        2. Load activity dataset (sample_activities.yaml)
        3. Load catalog dataset (sample_catalog.yaml)
        4. Load extended information dataset (sample_information_extended.yaml)

    Returns:
        Summary dict with counts for all loaded entities

    """
    p = Path(path)

    # If path is a file, load just that file
    if p.is_file():
        logger.info(f"Loading single file: {p}")
        dataset_kind = _detect_dataset_kind(p)
        if dataset_kind == "taxonomy":
            return await load_taxonomy_dataset(p, db)
        if dataset_kind == "activity":
            return await load_activity_dataset(p, db)
        if dataset_kind == "catalog":
            return await load_catalog_dataset(p, db)
        if dataset_kind == "information_extended":
            return await load_information_extended_dataset(p, db)
        if dataset_kind == "document_classifications":
            return await load_document_classification_dataset(p, db)
        raise DatasetLoaderError(f"Unsupported dataset file: {p}")

    # If path is a directory, load all known dataset files
    if not p.is_dir():
        raise DatasetLoaderError(f"Path is neither a file nor directory: {path}")

    logger.info(f"Loading all datasets from directory: {p}")
    summary: dict[str, Any] = {}

    # Load taxonomy dataset
    taxonomy_file = p / "sample_taxonomies.yaml"
    if taxonomy_file.exists():
        logger.info(f"Loading taxonomies from {taxonomy_file}")
        taxonomy_summary = await load_taxonomy_dataset(taxonomy_file, db)
        summary.update(taxonomy_summary)
    else:
        logger.warning(f"Taxonomy file not found: {taxonomy_file}")

    # Load activity dataset
    activity_file = p / "sample_activities.yaml"
    if activity_file.exists():
        logger.info(f"Loading activities from {activity_file}")
        activity_summary = await load_activity_dataset(activity_file, db)
        summary.update(activity_summary)
    else:
        logger.warning(f"Activity file not found: {activity_file}")

    # Load catalog dataset
    catalog_file = p / "sample_catalog.yaml"
    if catalog_file.exists():
        logger.info(f"Loading catalog from {catalog_file}")
        catalog_summary = await load_catalog_dataset(catalog_file, db)
        summary.update(catalog_summary)
    else:
        logger.warning(f"Catalog file not found: {catalog_file}")

    # Load extended information dataset (TopicSuggestion, Match)
    info_extended_file = p / "sample_information_extended.yaml"
    if info_extended_file.exists():
        logger.info(f"Loading extended information from {info_extended_file}")
        info_summary = await load_information_extended_dataset(info_extended_file, db)
        summary.update(info_summary)
    else:
        logger.warning(f"Extended information file not found: {info_extended_file}")

    # Load document classification dataset (DocumentClassification, DocumentTopicAssignment)
    doc_class_file = p / "sample_document_classifications.yaml"
    if doc_class_file.exists():
        logger.info(f"Loading document classifications from {doc_class_file}")
        doc_class_summary = await load_document_classification_dataset(
            doc_class_file, db
        )
        summary.update(doc_class_summary)
    else:
        logger.warning(f"Document classification file not found: {doc_class_file}")

    return summary


DatasetKind = Literal[
    "taxonomy",
    "activity",
    "catalog",
    "information_extended",
    "document_classifications",
]


def _detect_dataset_kind(path: Path) -> DatasetKind:
    """Inspect a dataset file and determine which loader to use."""
    try:
        data = yaml.safe_load(path.read_text())
    except FileNotFoundError as exc:
        raise DatasetLoaderError(f"Dataset file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise DatasetLoaderError(f"Invalid YAML in dataset file: {path}") from exc

    if not isinstance(data, dict):
        raise DatasetLoaderError(
            f"Dataset file must contain a mapping at the top level: {path}"
        )

    keys = set(data.keys())

    if "taxonomies" in keys:
        return "taxonomy"

    if "activities" in keys:
        return "activity"

    catalog_keys = {"catalogs", "repositories", "purposes", "resources"}
    if catalog_keys & keys:
        return "catalog"

    info_keys = {"topic_suggestions", "matches"}
    if info_keys & keys:
        return "information_extended"

    if "document_classifications" in keys:
        return "document_classifications"

    raise DatasetLoaderError(
        f"Could not detect dataset kind for {path}. "
        "Expected keys such as 'taxonomies', 'activities', 'catalogs', 'topic_suggestions', or 'document_classifications'."
    )


async def load_taxonomy_dataset(path: str | Path, db: AsyncSession) -> dict[str, Any]:
    """Load taxonomy/topic dataset from a YAML file into the database.

    Args:
        path: Path to YAML dataset file
        db: SQLAlchemy session s

    Returns:
        Summary dict with counts: {taxonomies: int, topics: int, edges: int, closures: int}
    """
    p = Path(path)
    if not p.exists():
        raise DatasetLoaderError(f"Dataset file not found: {path}")

    logger.info(f"Loading taxonomy dataset from {p}")
    data = yaml.safe_load(p.read_text())

    taxonomies_data: list[dict[str, Any]] = data.get("taxonomies", [])
    if not taxonomies_data:
        raise DatasetLoaderError("No taxonomies found in dataset")

    taxonomy_id_map: dict[str, Taxonomy] = {}
    topic_map: dict[str, Topic] = {}
    edges_to_create: list[tuple[str, str]] = []  # (parent_id, child_id)

    # 1. Create taxonomies
    taxonomy_repo = TaxonomyRepository(session=db)
    for tx in taxonomies_data:
        taxonomy = Taxonomy(
            id=tx["id"],
            title=tx["title"],
            description=tx.get("description"),
            skos_uri=None,
        )
        instance = await taxonomy_repo.add(taxonomy)
        # db.add(taxonomy)
        taxonomy_id_map[instance.id] = taxonomy
        tx["_internal_id"] = instance.id

    await db.flush()  # assign any defaults

    # 2. Create topics (without edges yet)
    for tx in taxonomies_data:
        # import pdb; pdb.set_trace()
        taxonomy_id = tx["_internal_id"]
        for tp in tx.get("topics", []):
            topic = Topic(
                id=tp["id"],
                taxonomy_id=taxonomy_id,
                title=tp["title"],
                slug=tp["id"].replace("_", "-") if tp.get("id") else None,
                description=tp.get("description"),
                status=tp.get("status", "active"),
                aliases=tp.get("aliases", []),
                external_refs={},
                path=None,
            )
            db.add(topic)
            topic_map[tp["id"]] = topic
            # import pdb; pdb.set_trace()
            for parent_identifier in tp.get("parents", []):
                edges_to_create.append((parent_identifier, tp["id"]))

    await db.flush()

    # 3. Create TopicEdge entries
    topic_repo = TopicRepository(session=db)
    edge_repo = TopicEdgeRepository(topic_repo=topic_repo, session=db)
    edge_models: list[TopicEdge] = []
    for parent_identifier, child_identifier in edges_to_create:
        # import pdb; pdb.set_trace()
        if parent_identifier not in topic_map or child_identifier not in topic_map:
            raise DatasetLoaderError(
                f"Edge references unknown topic IDs: {parent_identifier} -> {child_identifier}"
            )
        child_topic = topic_map[child_identifier]
        parent_topic = topic_map[parent_identifier]

        edge = TopicEdge(
            parent_id=parent_topic.id, child_id=child_topic.id, role="broader"
        )
        instance = await edge_repo.add(edge)

        # db.add(edge)
        edge_models.append(edge)

    await db.flush()

    # 4. Build closure table (simple BFS per root)
    # Clear existing closures for deterministic test behavior
    await db.execute(delete(TopicClosure))
    await db.flush()

    # adjacency map
    children_map: dict[str, list[str]] = {}
    parent_map: dict[str, list[str]] = {}
    for parent_id, child_id in edges_to_create:
        children_map.setdefault(parent_id, []).append(child_id)
        parent_map.setdefault(child_id, []).append(parent_id)

    # identify roots (topics with no parents)
    roots = [tid for tid in topic_map if tid not in parent_map]
    # import pdb; pdb.set_trace()
    # Insert self closures depth=0
    for tident, obj in topic_map.items():
        db.add(TopicClosure(ancestor_id=obj.id, descendant_id=obj.id, depth=0))

    # BFS from each root with duplicate prevention
    inserted_pairs: set[tuple[str, str]] = set((tid, tid) for tid in topic_map.keys())
    for root in roots:
        queue: list[tuple[str, int]] = [(root, 0)]
        visited: set[str] = set()
        while queue:
            current, depth = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for child in children_map.get(current, []):
                root_id = topic_map[root].id
                child_id = topic_map[child].id
                current_id = topic_map[current].id
                # ancestor=root path
                pair_root = (root, child)
                if pair_root not in inserted_pairs:
                    db.add(
                        TopicClosure(
                            ancestor_id=root_id, descendant_id=child_id, depth=depth + 1
                        )
                    )
                    inserted_pairs.add(pair_root)
                # immediate parent path (excluding root which already covers depth=1)
                if current != root:
                    pair_parent = (current, child)
                    if pair_parent not in inserted_pairs:
                        db.add(
                            TopicClosure(
                                ancestor_id=current_id, descendant_id=child_id, depth=1
                            )
                        )
                        inserted_pairs.add(pair_parent)
                queue.append((child, depth + 1))

    await db.commit()

    closures_count_result = await db.execute(
        select(func.count()).select_from(TopicClosure)
    )
    closures_count = closures_count_result.scalar_one()
    logger.info(
        "Loaded dataset: %d taxonomies, %d topics, %d edges, %d closures",
        len(taxonomy_id_map),
        len(topic_map),
        len(edge_models),
        closures_count,
    )
    return {
        "taxonomies": len(taxonomy_id_map),
        "topics": len(topic_map),
        "edges": len(edge_models),
        "closures": closures_count,
    }


async def load_activity_dataset(path: str | Path, db: AsyncSession) -> dict[str, Any]:
    """Load activity dataset from a YAML file into the database.

    Args:
        path: Path to YAML dataset file
        db: SQLAlchemy session

    Returns:
        Summary dict with counts: {activities: int}
    """
    p = Path(path)
    if not p.exists():
        raise DatasetLoaderError(f"Dataset file not found: {path}")

    logger.info(f"Loading activity dataset from {p}")
    data = yaml.safe_load(p.read_text())

    activities_data: list[dict[str, Any]] = data.get("activities", [])
    if not activities_data:
        raise DatasetLoaderError("No activities found in dataset")

    activity_repo = ActivityRepository(session=db)

    # Create activities
    for act_data in activities_data:
        activity = Activity(
            id=act_data.get("id"),
            title=act_data["title"],
            description=act_data.get("description"),
            activity_type=act_data["activity_type"],
            url=act_data.get("url"),
            created_by=act_data.get("created_by"),
        )
        await activity_repo.add(activity)

    await db.commit()

    logger.info(f"Loaded dataset: {len(activities_data)} activities")
    return {"activities": len(activities_data)}


async def load_catalog_dataset(path: str | Path, db: AsyncSession) -> dict[str, Any]:
    """Load catalog dataset from a YAML file into the database.

    Args:
        path: Path to YAML dataset file
        db: SQLAlchemy session

    Returns:
        Summary dict with counts: {catalogs: int, repositories: int, purposes: int, resources: int}
    """
    p = Path(path)
    if not p.exists():
        raise DatasetLoaderError(f"Dataset file not found: {path}")

    logger.info(f"Loading catalog dataset from {p}")
    data = yaml.safe_load(p.read_text())

    catalogs_data: list[dict[str, Any]] = data.get("catalogs", [])
    repositories_data: list[dict[str, Any]] = data.get("repositories", [])
    purposes_data: list[dict[str, Any]] = data.get("purposes", [])
    resources_data: list[dict[str, Any]] = data.get("resources", [])

    catalog_repo = CatalogRepository(session=db)
    repository_repo = RepositoryRepository(session=db)
    purpose_repo = PurposeRepository(session=db)
    resource_repo = ResourceRepository(session=db)

    # Create catalogs
    catalog_id_map: dict[str, Catalog] = {}
    for cat_data in catalogs_data:
        catalog = Catalog(
            id=cat_data["id"],
            title=cat_data["title"],
            description=cat_data.get("description"),
        )
        instance = await catalog_repo.add(catalog)

        # Handle taxonomy relationships (themes field in YAML -> taxonomies relationship)
        theme_ids = cat_data.get("themes", [])
        if theme_ids:
            from sqlalchemy import select

            from ontology.relational.models import Taxonomy

            taxonomies = []
            for theme_id in theme_ids:
                result = await db.execute(
                    select(Taxonomy).where(Taxonomy.id == theme_id)
                )
                taxonomy = result.scalar_one_or_none()
                if taxonomy:
                    taxonomies.append(taxonomy)

            if taxonomies:
                instance.taxonomies = taxonomies

        catalog_id_map[instance.id] = instance

    await db.flush()

    # Create repositories
    repository_id_map: dict[str, Repository] = {}
    for repo_data in repositories_data:
        repository = Repository(
            id=repo_data["id"],
            title=repo_data["title"],
            service_name=repo_data["service_name"],
            description=repo_data.get("description"),
        )
        instance = await repository_repo.add(repository)
        repository_id_map[instance.id] = instance

    await db.flush()

    # Create purposes
    for purpose_data in purposes_data:
        purpose = Purpose(
            id=purpose_data["id"],
            title=purpose_data["title"],
            description=purpose_data.get("description"),
            role=purpose_data.get("role"),
            meaning=purpose_data.get("meaning"),
        )
        await purpose_repo.add(purpose)

    await db.flush()

    # Create resources
    resource_id_map: dict[str, Resource] = {}
    for res_data in resources_data:
        # Get catalog ID from identifier
        catalog_identifier = res_data["catalog"]
        if catalog_identifier not in catalog_id_map:
            raise DatasetLoaderError(
                f"Resource references unknown catalog: {catalog_identifier}"
            )
        catalog_obj = catalog_id_map[catalog_identifier]

        # Get repository ID if specified
        repository_id = None
        if "repository" in res_data and res_data["repository"]:
            repo_identifier = res_data["repository"]
            if repo_identifier in repository_id_map:
                repository_id = repository_id_map[repo_identifier].id

        resource = Resource(
            id=res_data["id"],
            catalog_id=catalog_obj.id,
            catalog=res_data["catalog"],
            title=res_data["title"],
            description=res_data.get("description"),
            resource_type=res_data["resource_type"],
            location=res_data.get("location"),
            repository_id=repository_id,
            repository=res_data.get("repository"),
            content_location=res_data.get("content_location"),
            format=res_data.get("format"),
            media_type=res_data.get("media_type"),
            theme=res_data.get("theme"),
            subject=res_data.get("subject"),
            creator=res_data.get("creator"),
            has_purpose=res_data.get("has_purpose"),
            has_use=res_data.get("has_use", []),
            has_resources=res_data.get("has_resources", []),
            document_type=res_data.get("document_type"),
            note_type=res_data.get("note_type"),
        )
        instance = await resource_repo.add(resource)
        resource_id_map[instance.id] = instance

    await db.flush()

    # Handle resource-to-resource and resource-to-topic relationships via association tables
    from ontology.relational.models import (
        resource_related_resources,
        resource_related_topics,
    )
    from ontology.relational.models import Topic

    for res_data in resources_data:
        resource_id = res_data["id"]

        # Handle related resources (resource-to-resource many-to-many)
        related_resource_ids = res_data.get("related_resources", [])
        if related_resource_ids:
            for related_id in related_resource_ids:
                if related_id not in resource_id_map:
                    logger.warning(
                        f"Resource {resource_id} references unknown related resource: {related_id}, skipping"
                    )
                    continue

                # Insert into association table
                await db.execute(
                    resource_related_resources.insert().values(
                        source_resource_id=resource_id,
                        related_resource_id=related_id,
                    )
                )

        # Handle related topics (resource-to-topic many-to-many)
        related_topic_ids = res_data.get("related_topics", [])
        if related_topic_ids:
            for topic_id in related_topic_ids:
                # Verify topic exists
                result = await db.execute(select(Topic).where(Topic.id == topic_id))
                topic = result.scalar_one_or_none()
                if not topic:
                    logger.warning(
                        f"Resource {resource_id} references unknown topic: {topic_id}, skipping"
                    )
                    continue

                # Insert into association table
                await db.execute(
                    resource_related_topics.insert().values(
                        resource_id=resource_id,
                        topic_id=topic_id,
                    )
                )

    await db.commit()

    logger.info(
        f"Loaded dataset: {len(catalogs_data)} catalogs, {len(repositories_data)} repositories, "
        f"{len(purposes_data)} purposes, {len(resources_data)} resources"
    )
    return {
        "catalogs": len(catalogs_data),
        "repositories": len(repositories_data),
        "purposes": len(purposes_data),
        "resources": len(resources_data),
    }


async def load_information_extended_dataset(
    path: str | Path, db: AsyncSession
) -> dict[str, Any]:
    """Load extended information dataset (TopicSuggestion, Match) from a YAML file.

    Args:
        path: Path to YAML dataset file
        db: SQLAlchemy session

    Returns:
        Summary dict with counts: {topic_suggestions: int, matches: int}
    """
    p = Path(path)
    if not p.exists():
        raise DatasetLoaderError(f"Dataset file not found: {path}")

    logger.info(f"Loading extended information dataset from {p}")
    data = yaml.safe_load(p.read_text())

    suggestions_data: list[dict[str, Any]] = data.get("topic_suggestions", [])
    matches_data: list[dict[str, Any]] = data.get("matches", [])

    suggestion_repo = TopicSuggestionRepository(session=db)

    # Create topic suggestions
    for sugg_data in suggestions_data:
        # Get topic by id
        topic_identifier = sugg_data["topic_identifier"]
        topic = (
            await db.execute(select(Topic).where(Topic.id == topic_identifier))
        ).scalar_one_or_none()

        if not topic:
            logger.warning(
                f"Topic not found for suggestion: {topic_identifier}, skipping"
            )
            continue

        # Get taxonomy if specified
        taxonomy_id = None
        if "taxonomy_identifier" in sugg_data:
            taxonomy_identifier = sugg_data["taxonomy_identifier"]
            taxonomy = (
                await db.execute(
                    select(Taxonomy).where(Taxonomy.id == taxonomy_identifier)
                )
            ).scalar_one_or_none()
            if taxonomy:
                taxonomy_id = taxonomy.id

        # Compute hash of input text
        input_text = sugg_data["input_text"]
        input_hash = hashlib.sha256(input_text.encode()).hexdigest()

        suggestion = TopicSuggestion(
            input_text=input_text,
            input_hash=input_hash,
            taxonomy_id=taxonomy_id,
            topic_id=topic.id,
            confidence=sugg_data["confidence"],
            rank=sugg_data["rank"],
            model_name=sugg_data["model_name"],
            model_version=sugg_data["model_version"],
            context=sugg_data.get("context", {}),
        )
        await suggestion_repo.add(suggestion)

    await db.flush()

    # Create matches
    for match_data in matches_data:
        entity_type = match_data["entity_type"]
        entity_identifier = match_data["entity_identifier"]

        # Get entity ID
        if entity_type == "topic":
            entity = (
                await db.execute(select(Topic).where(Topic.id == entity_identifier))
            ).scalar_one_or_none()
        elif entity_type == "taxonomy":
            entity = (
                await db.execute(
                    select(Taxonomy).where(Taxonomy.id == entity_identifier)
                )
            ).scalar_one_or_none()
        else:
            raise DatasetLoaderError(f"Unknown entity type: {entity_type}")

        if not entity:
            logger.warning(
                f"Entity not found for match: {entity_type}:{entity_identifier}, skipping"
            )
            continue

        match = Match(
            entity_type=entity_type,
            entity_id=entity.id,
            system=match_data["system"],
            external_id=match_data["external_id"],
            match_type=match_data["match_type"],
            confidence=match_data["confidence"],
            evidence=match_data.get("evidence", {}),
        )
        db.add(match)

    await db.commit()

    logger.info(
        f"Loaded dataset: {len(suggestions_data)} topic suggestions, {len(matches_data)} matches"
    )
    return {
        "topic_suggestions": len(suggestions_data),
        "matches": len(matches_data),
    }


async def load_document_classification_dataset(
    path: str | Path, db: AsyncSession
) -> dict[str, Any]:
    """Load document classification dataset from a YAML file into the database.

    This loads DocumentClassification and DocumentTopicAssignment entities,
    demonstrating the FEAT-008 document classification feature.

    Args:
        path: Path to YAML dataset file
        db: SQLAlchemy session

    Returns:
        Summary dict with counts: {document_classifications: int, topic_assignments: int}
    """

    p = Path(path)
    if not p.exists():
        raise DatasetLoaderError(f"Dataset file not found: {path}")

    logger.info(f"Loading document classification dataset from {p}")
    data = yaml.safe_load(p.read_text())

    classifications_data: list[dict[str, Any]] = data.get(
        "document_classifications", []
    )
    if not classifications_data:
        raise DatasetLoaderError("No document_classifications found in dataset")

    classification_repo = DocumentClassificationRepository(session=db)

    total_classifications = 0
    total_assignments = 0

    for doc_data in classifications_data:
        # Get taxonomy by id
        taxonomy_id = doc_data["taxonomy_classification"]["taxonomy_identifier"]
        taxonomy = (
            await db.execute(select(Taxonomy).where(Taxonomy.id == taxonomy_id))
        ).scalar_one_or_none()

        if not taxonomy:
            logger.warning(
                f"Taxonomy not found: {taxonomy_id}, skipping document {doc_data['document_id']}"
            )
            continue

        # Create DocumentClassification
        # Note: id will be auto-generated by event listener
        classification = DocumentClassification(
            document_id=doc_data["document_id"],
            document_type=doc_data["document_type"],
            taxonomy_id=taxonomy.id,
            confidence=doc_data["taxonomy_classification"]["confidence"],
            reasoning=doc_data["taxonomy_classification"].get("reasoning"),
            model_name=doc_data["taxonomy_classification"]["model_name"],
            model_version=doc_data["taxonomy_classification"]["model_version"],
            prompt_version=doc_data["taxonomy_classification"]["prompt_version"],
            meta={},
        )
        db.add(classification)
        await db.flush()  # Get the classification ID
        total_classifications += 1

        # Create DocumentTopicAssignments
        topic_assignments_data = doc_data.get("topic_assignments", [])
        for assignment_data in topic_assignments_data:
            # Get topic by id
            topic_id = assignment_data["topic_identifier"]
            topic = (
                await db.execute(select(Topic).where(Topic.id == topic_id))
            ).scalar_one_or_none()

            if not topic:
                logger.warning(
                    f"Topic not found: {topic_id}, skipping assignment for document {doc_data['document_id']}"
                )
                continue

            assignment = DocumentTopicAssignment(
                classification_id=classification.id,
                topic_id=topic.id,
                confidence=assignment_data["confidence"],
                rank=assignment_data["rank"],
                reasoning=assignment_data.get("reasoning"),
                meta={},
            )
            db.add(assignment)
            total_assignments += 1

    await db.commit()

    logger.info(
        f"Loaded dataset: {total_classifications} document classifications, "
        f"{total_assignments} topic assignments"
    )
    return {
        "document_classifications": total_classifications,
        "topic_assignments": total_assignments,
    }


__all__ = ["load_yaml_dataset", "DatasetLoaderError"]
