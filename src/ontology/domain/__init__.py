"""Domain models for Topic entities.

These are attrs-based domain models representing Topic entities in the business layer.
They are separate from database ORM models and Pydantic I/O schemas.
"""

import uuid
from datetime import datetime
from typing import Literal, Optional, Any

from attrs import define, field

from ontology.utils.slug import (
    generate_identifier,
    generate_slug,
    split_namespace,
    DEFAULT_NAMESPACE_SPLIT,
)


# Enums
DocumentType = Literal[
    "Document", "Journal", "List", "Notebook", "Logbook", "Inventory", "Landscape"
]
NoteType = Literal["Note", "Log", "Thought", "Idea", "Reference", "Highlight"]
ResourceType = Literal["Resource", "Bookmark", "Collection", "Document", "Note"]


TopicStatus = Literal["draft", "active", "deprecated", "merged"]
EdgeRole = Literal["broader", "part_of", "instance_of", "related"]


TAXONOMY_DEFAULT_NAMESPACE_PREFIX = "tx"
CATALOG_DEFAULT_NAMESPACE_PREFIX = "cat"
REPOSITORY_DEFAULT_NAMESPACE_PREFIX = "rep"
PURPOSE_DEFAULT_NAMESPACE_PREFIX = "purp"
RESOURCE_DEFAULT_NAMESPACE_PREFIX = "res"
ACTIVITY_DEFAULT_NAMESPACE_PREFIX = "act"

DEFAULT_NAMESPACE_PREFIXES = {
    "Taxonomy": "tx",
    "Catalog": "cat",
    "Repository": "rep",
    "Purpose": "purp",
    "Resource": "res",
    "Bookmark": "bkmk",
    "Note": "note",
    "Document": "doc",
    "Collection": "coll",
}
# @define
# class Taxonomy:
#     """Domain model for a Taxonomy.

#     A taxonomy is a collection of related topics that provides organizational
#     structure for knowledge management.

#     Attributes:
#         id: Unique identifier (CURIE)
#         title: Human-readable title
#         description: Optional longer description
#         skos_uri: Optional SKOS URI for alignment
#         created_at: When the taxonomy was created
#         updated_at: When the taxonomy was last updated
#     """

#     title: str
#     id: str = field()
#     description: Optional[str] = None
#     skos_uri: Optional[str] = None
#     created_at: datetime = field(factory=lambda: datetime.now())
#     updated_at: datetime = field(factory=lambda: datetime.now())

#     @id.default
#     def _default_id(self):
#         return generate_identifier(self.title, TAXONOMY_DEFAULT_NAMESPACE_PREFIX)

#     def __str__(self) -> str:
#         return f"Taxonomy({self.title})"


# def taxonomy_to_ident(obj) -> str:
#     """Accept a serialized Taxonomy object and retrieve its id (uri form)."""
#     import pdb

#     pdb.set_trace()
#     if isinstance(obj, str):
#         return obj


# @define
# class Topic:
#     """Domain model for a Topic.

#     A topic represents a specific concept within a taxonomy.

#     Attributes:
#         id: Unique identifier (CURIE)
#         taxonomy_id: ID of the parent taxonomy (CURIE)
#         title: Human-readable title
#         slug: URL-friendly identifier
#         description: Optional longer description
#         status: Current status
#         aliases: List of alternative names
#         external_refs: Dictionary of external system references
#         path: Materialized path for hierarchy display
#         created_at: When the topic was created
#         updated_at: When the topic was last updated

#     Invariants:
#         1. ID: required
#             - An id can only be generated within the context of a wider taxonomy,
#             and so we can only perform this automatically if the taxonomy is known.
#             - For this reason, in the ORM we compute it, but in the domain we
#             require the caller to provide it.

#         2. Slug: required
#             - A slug can always be generated from the title, so this is optional
#             from the caller's perspective - we will just make one.
#     """

#     title: str
#     taxonomy_id: str
#     id: str = field()
#     slug: str = field()

#     description: Optional[str] = None
#     status: TopicStatus = "draft"
#     aliases: list[str] = field(factory=list)
#     external_refs: dict[str, str] = field(factory=dict)
#     path: Optional[str] = None
#     created_at: datetime = field(factory=lambda: datetime.now())
#     updated_at: datetime = field(factory=lambda: datetime.now())

#     @slug.default
#     def _default_slug(self):
#         return generate_slug(self.title)

#     @id.default
#     def _default_id(self):
#         return generate_identifier(
#             self.title, split_namespace(self.taxonomy_id)[1]
#         )

#     def __str__(self) -> str:
#         return f"Topic({self.title}, slug={self.slug})"


# @define
# class TopicSuggestion:
#     """Classifier-generated suggestion linking input text to a topic."""

#     input_text: str
#     input_hash: str
#     topic_id: str
#     confidence: float
#     rank: int
#     model_name: str
#     model_version: str
#     metadata: dict[str, Any] = field(factory=dict)
#     id: Optional[str] = None
#     taxonomy_id: Optional[str] = None
#     created_at: datetime = field(factory=datetime.utcnow)
#     updated_at: datetime = field(factory=datetime.utcnow)


# @define
# class TopicEdge:
#     """Domain model for a Topic Edge (relationship between topics).

#     Attributes:
#         id: Unique identifier (CURIE)
#         parent_id: ID of the parent topic (CURIE)
#         child_id: ID of the child topic (CURIE)
#         role: Relationship type
#         source: Where this relationship came from
#         confidence: Confidence score (0.0 to 1.0)
#         created_at: When the edge was created
#     """

#     parent_id: str
#     child_id: str
#     role: EdgeRole = "broader"
#     id: Optional[str] = None
#     source: Optional[str] = None
#     confidence: float = 1.0
#     is_primary: bool = False
#     created_at: datetime = field(factory=lambda: datetime.now())

#     def __str__(self) -> str:
#         return f"TopicEdge({self.parent_id} --{self.role}-> {self.child_id})"


# @define
# class DocumentClassification:
#     """Domain model for a document classification.

#     Represents the classification of a document into a taxonomy,
#     separate from ORM and API concerns.

#     Attributes:
#         document_id: ID of the document being classified
#         document_type: Type of document
#         taxonomy_id: ID of the suggested taxonomy (CURIE)
#         confidence: Confidence score (0.0 to 1.0)
#         reasoning: Optional explanation
#         model_name: LLM model used
#         model_version: Version of the model
#         prompt_version: Version of prompt template
#         metadata: Additional data
#         user_feedback: Optional user correction
#         id: Database ID (optional, set after persistence)
#         created_at: Creation timestamp
#         updated_at: Update timestamp
#     """

#     document_id: str
#     document_type: str
#     taxonomy_id: str
#     confidence: float
#     model_name: str
#     model_version: str
#     prompt_version: str

#     id: Optional[str] = None
#     reasoning: Optional[str] = None
#     metadata: dict[str, Any] = field(factory=dict)
#     user_feedback: Optional[str] = None
#     created_at: datetime = field(factory=datetime.utcnow)
#     updated_at: datetime = field(factory=datetime.utcnow)

#     def __attrs_post_init__(self):
#         """Validate confidence range."""
#         if not 0.0 <= self.confidence <= 1.0:
#             raise ValueError(
#                 f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
#             )


# @define
# class DocumentTopicAssignment:
#     """Domain model for a document-topic assignment.

#     Represents one topic suggestion within a document classification.

#     Attributes:
#         classification_id: Parent classification ID
#         topic_id: ID of the suggested topic (CURIE)
#         topic_title: Title of the topic (for convenience)
#         confidence: Confidence score
#         rank: Ranking of this suggestion
#         reasoning: Optional explanation
#         metadata: Additional data
#         user_feedback: Optional user correction
#         id: Database ID (optional)
#         created_at: Creation timestamp
#         updated_at: Update timestamp
#     """

#     classification_id: str
#     topic_id: str
#     topic_title: str
#     confidence: float
#     rank: int

#     id: Optional[str] = None
#     reasoning: Optional[str] = None
#     metadata: dict[str, Any] = field(factory=dict)
#     user_feedback: Optional[str] = None
#     created_at: datetime = field(factory=datetime.utcnow)
#     updated_at: datetime = field(factory=datetime.utcnow)

#     def __attrs_post_init__(self):
#         """Validate constraints."""
#         if not 0.0 <= self.confidence <= 1.0:
#             raise ValueError(
#                 f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
#             )
#         if self.rank < 1:
#             raise ValueError(f"Rank must be >= 1, got {self.rank}")


# @define
# class ClassificationResult:
#     """Complete classification result including taxonomy and topics.

#     This is a convenience model that aggregates the full classification
#     result for a document, including both taxonomy suggestion and topic
#     assignments.
#     """

#     document_id: str
#     document_type: str
#     document_content_preview: str  # First 200 chars for context

#     taxonomy_classification: DocumentClassification
#     topic_assignments: list[DocumentTopicAssignment] = field(factory=list)

#     def __str__(self) -> str:
#         topics_str = ", ".join([t.topic_title for t in self.topic_assignments[:3]])
#         return f"Classification(taxonomy={self.taxonomy_classification.taxonomy_id}, topics=[{topics_str}])"
# @define
# class Catalog:
#     """Domain model for a Catalog.

#     A catalog is a group of similar Resource instances around a theme or topic.

#     Attributes:
#         id: Unique identifier
#         identifier: Business identifier for the catalog
#         title: Human-readable title
#         description: Optional longer description
#         taxonomies: Optional list of taxonomy identifiers
#         created_by: Optional creator identifier
#         created_on: Optional creation timestamp
#         last_updated_on: Optional last update timestamp
#     """

#     identifier: str
#     title: str
#     id: uuid.UUID = field(factory=uuid.uuid4)
#     description: Optional[str] = None
#     taxonomies: list[str] = field(factory=list)
#     created_by: Optional[str] = None
#     created_on: Optional[datetime] = None
#     last_updated_on: Optional[datetime] = None

#     def __str__(self) -> str:
#         return f"Catalog({self.title})"


# @define
# class Repository:
#     """Domain model for a Repository.

#     A repository represents the system that houses a given resource.

#     Attributes:
#         id: Unique identifier
#         identifier: Business identifier for the repository
#         title: Human-readable title
#         service_name: The name of the app/service being used
#         description: Optional longer description
#         created_by: Optional creator identifier
#         created_on: Optional creation timestamp
#         last_updated_on: Optional last update timestamp
#     """

#     identifier: str
#     title: str
#     service_name: str
#     id: uuid.UUID = field(factory=uuid.uuid4)
#     description: Optional[str] = None
#     created_by: Optional[str] = None
#     created_on: Optional[datetime] = None
#     last_updated_on: Optional[datetime] = None

#     def __str__(self) -> str:
#         return f"Repository({self.title}, service={self.service_name})"


# @define
# class Purpose:
#     """Domain model for a Purpose.

#     Purpose describes the designated role or meaning of a resource.

#     Attributes:
#         id: Unique identifier
#         identifier: Business identifier for the purpose
#         title: Human-readable title
#         description: Optional longer description
#         role: Optional relationship type
#         meaning: Optional meaning applied to the purpose
#         created_by: Optional creator identifier
#         created_on: Optional creation timestamp
#         last_updated_on: Optional last update timestamp
#     """

#     identifier: str
#     title: str
#     id: uuid.UUID = field(factory=uuid.uuid4)
#     description: Optional[str] = None
#     role: Optional[str] = None
#     meaning: Optional[str] = None
#     created_by: Optional[str] = None
#     created_on: Optional[datetime] = None
#     last_updated_on: Optional[datetime] = None

#     def __str__(self) -> str:
#         return f"Purpose({self.title})"


# @define
# class Resource:
#     """Domain model for a Resource (base class).

#     A resource is the base class for information resources in the catalog.

#     Attributes:
#         id: Unique identifier
#         identifier: Business identifier for the resource
#         catalog: Identifier of the catalog this resource belongs to
#         title: Human-readable title
#         description: Optional longer description
#         resource_type: Type of resource
#         location: Required canonical URL for base Resource type
#         repository: Optional identifier of the repository (required for subtypes)
#         content_location: Optional URL of content (e.g., object store)
#         format: Optional file format
#         media_type: Optional MIME type
#         theme: Optional theme/topic identifier
#         subject: Optional subject
#         creator: Optional creator
#         has_purpose: Optional purpose identifier
#         has_use: Optional list of use identifiers
#         related_resources: List of related resource identifiers
#         related_topics: List of related topic identifiers
#         created: Optional creation datetime
#         modified: Optional modification datetime
#         created_by: Optional creator identifier
#         created_on: Optional creation timestamp
#         last_updated_on: Optional last update timestamp
#     """

#     identifier: str
#     catalog: str
#     title: str
#     id: uuid.UUID = field(factory=uuid.uuid4)
#     description: Optional[str] = None
#     resource_type: ResourceType = "Resource"
#     location: str = field(kw_only=True)
#     repository: Optional[str] = None
#     content_location: Optional[str] = None
#     format: Optional[str] = None
#     media_type: Optional[str] = None
#     theme: Optional[str] = None
#     subject: Optional[str] = None
#     creator: Optional[str] = None
#     has_purpose: Optional[str] = None
#     has_use: list[str] = field(factory=list)
#     related_resources: list[str] = field(factory=list)
#     related_topics: list[str] = field(factory=list)
#     created: Optional[datetime] = None
#     modified: Optional[datetime] = None
#     created_by: Optional[str] = None
#     created_on: Optional[str] = None
#     last_updated_on: Optional[str] = None

#     def __str__(self) -> str:
#         return f"Resource({self.title}, type={self.resource_type})"


# @define
# class Bookmark(Resource):
#     """Domain model for a Bookmark.

#     A bookmark is a collected resource - a URL with no content.

#     Attributes (in addition to Resource):
#         repository: Required repository identifier (overrides Resource)
#         location: Optional location (overrides Resource requirement)
#     """

#     location: Optional[str] = field(default=None, kw_only=True)
#     repository: str = field(kw_only=True)
#     resource_type: ResourceType = "Bookmark"

#     def __str__(self) -> str:
#         return f"Bookmark({self.title})"


# @define
# class Collection(Resource):
#     """Domain model for a Collection.

#     A collection is a group of resources centered around some need or theme.

#     Attributes (in addition to Resource):
#         repository: Required repository identifier (overrides Resource)
#         location: Optional location (overrides Resource requirement)
#         has_resources: List of resource identifiers in this collection
#     """

#     location: Optional[str] = field(default=None, kw_only=True)
#     repository: str = field(kw_only=True)
#     has_resources: list[str] = field(factory=list)
#     resource_type: ResourceType = "Collection"

#     def __str__(self) -> str:
#         return f"Collection({self.title}, {len(self.has_resources)} resources)"


# @define
# class Document(Resource):
#     """Domain model for a Document.

#     A document is a larger container or promoted note; used only for documents
#     authored by the Self.

#     Attributes (in addition to Resource):
#         repository: Required repository identifier (overrides Resource)
#         location: Optional location (overrides Resource requirement)
#         document_type: Type of document (defaults to "Document")
#     """

#     location: Optional[str] = field(default=None, kw_only=True)
#     repository: str = field(kw_only=True)
#     document_type: DocumentType = field(default="Document", kw_only=True)
#     resource_type: ResourceType = "Document"

#     def __str__(self) -> str:
#         return f"Document({self.title}, type={self.document_type})"


# @define
# class Note(Resource):
#     """Domain model for a Note.

#     A note is small data being ingested.

#     Attributes (in addition to Resource):
#         repository: Required repository identifier (overrides Resource)
#         location: Optional location (overrides Resource requirement)
#         note_type: Type of note (defaults to "Note")
#     """

#     location: Optional[str] = field(default=None, kw_only=True)
#     repository: str = field(kw_only=True)
#     note_type: NoteType = field(default="Note", kw_only=True)
#     resource_type: ResourceType = "Note"

#     def __str__(self) -> str:
#         return f"Note({self.title}, type={self.note_type})"
# """Domain models for Activity entities.

# These are attrs-based domain models representing Activity entities in the business layer.
# They are separate from database ORM models and Pydantic I/O schemas.
# """

# import uuid
# from datetime import datetime
# from typing import Literal, Optional

# from attrs import define, field

# from ontology.utils.slug import generate_identifier

# # Activity types based on the work domain schema
# ActivityType = Literal["Effort", "Experiment", "Research", "Study", "Task", "Thinking"]

# ACTIVITY_DEFAULT_NAMESPACE_PREFIX = "act"


# @define
# class Activity:
#     """Domain model for an Activity.

#     An activity represents work that requires focus, time, and energy.
#     This is an abstract base class for specific activity types.

#     Attributes:
#         identifier: Unique identifier (CURIE format)
#         title: Human-readable title
#         description: Optional longer description
#         activity_type: Type of activity (Effort, Task, etc.)
#         url: Optional URL associated with this activity
#         created_by: Who created this activity
#         created_on: When the activity was created
#         last_updated_on: When the activity was last updated
#         id: UUID for database relationships

#     Invariants:
#         1. Identifier: required
#            - An identifier can be generated from the title using a default namespace
#         2. Activity type: required
#            - Must be one of the valid activity types
#     """

#     title: str
#     activity_type: ActivityType
#     identifier: str = field()
#     id: uuid.UUID | None = None
#     description: str | None = None
#     url: str | None = None
#     created_by: str | None = None
#     created_on: datetime | None = None
#     last_updated_on: datetime | None = None

#     @identifier.default
#     def _default_identifier(self):
#         return generate_identifier(self.title, ACTIVITY_DEFAULT_NAMESPACE_PREFIX)

#     def __str__(self) -> str:
#         return f"{self.activity_type}({self.title})"


# @define
# class Effort(Activity):
#     """Some set of tasks and outcomes that you are spending time on.

#     An Effort is a collection of related work activities (like a project).
#     """

#     activity_type: ActivityType = field(default="Effort", init=False)

#     def __str__(self) -> str:
#         return f"Effort({self.title})"


# @define
# class Experiment(Activity):
#     """Just fooling around, a type of Activity.

#     An Experiment represents exploratory work without a specific outcome.
#     """

#     activity_type: ActivityType = field(default="Experiment", init=False)

#     def __str__(self) -> str:
#         return f"Experiment({self.title})"


# @define
# class Research(Activity):
#     """In preparation for work, you need to spend time figuring out how to approach a problem.

#     Research represents investigative work to understand a problem or domain.
#     """

#     activity_type: ActivityType = field(default="Research", init=False)

#     def __str__(self) -> str:
#         return f"Research({self.title})"


# @define
# class Study(Activity):
#     """You spend specific directed effort learning some new thing.

#     Study represents focused learning activities.
#     """

#     activity_type: ActivityType = field(default="Study", init=False)

#     def __str__(self) -> str:
#         return f"Study({self.title})"


# @define
# class Task(Activity):
#     """An individual item of work.

#     A Task represents a discrete, actionable work item.
#     """

#     activity_type: ActivityType = field(default="Task", init=False)

#     def __str__(self) -> str:
#         return f"Task({self.title})"


# @define
# class Thinking(Activity):
#     """You spend time creating mental models of life and the world in order to understand it better.

#     Thinking represents reflective, contemplative work.
#     """

#     activity_type: ActivityType = field(default="Thinking", init=False)

#     def __str__(self) -> str:
#         return f"Thinking({self.title})"
