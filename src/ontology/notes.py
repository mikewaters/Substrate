"""
Note use cases:
- Assign a `subject` CURIE given the title of some document
-
- Determine which existing topics are relevant to a block of text
"""

import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from ontology.schema import TopicResponse
from ontology.relational.services import TopicTaxonomyService
from ontology.relational.database import get_async_session

logger = logging.getLogger(__name__)


async def get_subject_for_title(
    note_title: str, taxonomy_ident: str, session: AsyncSession | None = None
) -> TopicResponse:
    """
    Each catalog.Note and catalog.Document's title is represented as a Topic in the ontology,
    and this is stored in the entity's "subject" property.
    When adding a new entity instance to the catalog, we need to upsert the corresponding Topic,
    as well as an Edge that links the entity to this Topic having the "subject" relationship type.

    We require the caller to provide the taxonomy (as this is a data model requirement),
    but in the future this could be derived.

    For now, this will use the basic TopicSuggestion to find a potential parent, otherwise insert
    a new top-level topic into the taxonomy; in the future a new topic would be "parented" in
    the background.

    Retrieve a hydrated `ontology.information.schema.TopicResponse` instance from the database,
    given a note's title; this should represent an existing Topic, or a new one.


    Params:
        - note_title: What to search for, or to use for the new Topic's title
        - taxonomy_ident: The `id` for a taxonomy (CURIE format), found in `Taxonomy.id` property
    """
    if session is not None:
        # Use provided session
        svc = TopicTaxonomyService(session=session)
        topic, flag = await svc.repository.get_or_upsert(
            match_fields=["title", "taxonomy_id"],
            **dict(title=note_title, taxonomy_id=taxonomy_ident),
        )
        if not flag:
            logger.info(
                f"Found matching topic {topic.id} for note subject {note_title}."
            )
        else:
            logger.info(f"Created new topic {topic.id} for note subject {note_title}.")

        return topic
    else:
        # Create our own session
        async with get_async_session() as session:
            svc = TopicTaxonomyService(session=session)
            topic, flag = await svc.repository.get_or_upsert(
                match_fields=["title", "taxonomy_id"],
                **dict(title=note_title, taxonomy_id=taxonomy_ident),
            )
            if not flag:
                logger.info(
                    f"Found matching topic {topic.id} for note subject {note_title}."
                )
            else:
                logger.info(
                    f"Created new topic {topic.id} for note subject {note_title}."
                )

            return topic


async def main():
    """Example usage of get_note_subject function."""
    async with get_async_session() as session:
        result = await get_subject_for_title(
            "Artificial Intelligence", "tx:tech", session=session
        )
        print(f"Subject will be: {result}")
        print(f"Theme will be: {result.taxonomy}")


if __name__ == "__main__":
    asyncio.run(main())
