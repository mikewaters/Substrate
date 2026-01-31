# Auto generated from lifeos.yaml by pythongen.py version: 0.0.1
# Generation date: 2025-10-11T19:11:58
# Schema: ontology
#
# id: http://lifeos.org/ontology/lifeos-ontology
# description: A comprehensive ontology for modeling personal life management, including self-identity, work activities, and world objects.
#
# license: https://creativecommons.org/publicdomain/zero/1.0/

from dataclasses import dataclass
from typing import Any, ClassVar, Optional, Union

from linkml_runtime.linkml_model.meta import EnumDefinition, PermissibleValue
from linkml_runtime.utils.curienamespace import CurieNamespace
from linkml_runtime.utils.enumerations import EnumDefinitionImpl
from linkml_runtime.utils.metamodelcore import URI, XSDDateTime, empty_dict, empty_list
from linkml_runtime.utils.slot import Slot
from linkml_runtime.utils.yamlutils import YAMLRoot, extended_str
from rdflib import URIRef

metamodel_version = "1.7.0"
version = None

# Namespaces
DBO = CurieNamespace("dbo", "http://dbpedia.org/ontology/")
DCAT = CurieNamespace("dcat", "http://www.w3.org/ns/dcat#")
DCTERMS = CurieNamespace("dcterms", "http://purl.org/dc/terms/")
FOAF = CurieNamespace("foaf", "http://xmlns.com/foaf/0.1/")
LIFEOS = CurieNamespace("lifeos", "http://lifeos.org/ontology/")
LINKML = CurieNamespace("linkml", "https://w3id.org/linkml/")
SCHEMA = CurieNamespace("schema", "http://schema.org/")
SKOS = CurieNamespace("skos", "http://www.w3.org/2004/02/skos/core#")
DEFAULT_ = LIFEOS


# Types


# Class references
class ActivityId(extended_str):
    pass


class ExperimentId(ActivityId):
    pass


class ResearchId(ActivityId):
    pass


class StudyId(ActivityId):
    pass


class ThinkingId(ActivityId):
    pass


class TaskId(ActivityId):
    pass


class ProjectId(ActivityId):
    pass


class TopicTaxonomyId(extended_str):
    pass


class TopicId(extended_str):
    pass


class RepositoryId(extended_str):
    pass


class CatalogId(extended_str):
    pass


class ResourceId(extended_str):
    pass


class CollectionId(ResourceId):
    pass


class PurposeId(extended_str):
    pass


class NoteId(ResourceId):
    pass


class DocumentId(ResourceId):
    pass


class BookmarkId(ResourceId):
    pass


class HighlightId(ResourceId):
    pass


@dataclass(repr=False)
class Self(YAMLRoot):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = LIFEOS["Self"]
    class_class_curie: ClassVar[str] = "lifeos:Self"
    class_name: ClassVar[str] = "Self"
    class_model_uri: ClassVar[URIRef] = LIFEOS.Self

    activities: (
        dict[str | ActivityId, Union[dict, "Activity"]]
        | list[Union[dict, "Activity"]]
        | None
    ) = empty_dict()
    catalog: (
        dict[str | CatalogId, Union[dict, "Catalog"]]
        | list[Union[dict, "Catalog"]]
        | None
    ) = empty_dict()
    purposes: (
        dict[str | PurposeId, Union[dict, "Purpose"]]
        | list[Union[dict, "Purpose"]]
        | None
    ) = empty_dict()
    repositories: (
        dict[str | RepositoryId, Union[dict, "Repository"]]
        | list[Union[dict, "Repository"]]
        | None
    ) = empty_dict()
    collections: (
        dict[str | CollectionId, Union[dict, "Collection"]]
        | list[Union[dict, "Collection"]]
        | None
    ) = empty_dict()
    documents: (
        dict[str | DocumentId, Union[dict, "Document"]]
        | list[Union[dict, "Document"]]
        | None
    ) = empty_dict()
    notes: (
        dict[str | NoteId, Union[dict, "Note"]] | list[Union[dict, "Note"]] | None
    ) = empty_dict()
    bookmarks: (
        dict[str | BookmarkId, Union[dict, "Bookmark"]]
        | list[Union[dict, "Bookmark"]]
        | None
    ) = empty_dict()
    highlights: (
        dict[str | HighlightId, Union[dict, "Highlight"]]
        | list[Union[dict, "Highlight"]]
        | None
    ) = empty_dict()
    resources: (
        dict[str | ResourceId, Union[dict, "Resource"]]
        | list[Union[dict, "Resource"]]
        | None
    ) = empty_dict()
    themes: (
        dict[str | TopicTaxonomyId, Union[dict, "TopicTaxonomy"]]
        | list[Union[dict, "TopicTaxonomy"]]
        | None
    ) = empty_dict()
    topics: (
        dict[str | TopicId, Union[dict, "Topic"]] | list[Union[dict, "Topic"]] | None
    ) = empty_dict()

    def __post_init__(self, *_: str, **kwargs: Any):
        self._normalize_inlined_as_list(
            slot_name="activities", slot_type=Activity, key_name="id", keyed=True
        )

        self._normalize_inlined_as_list(
            slot_name="catalog", slot_type=Catalog, key_name="id", keyed=True
        )

        self._normalize_inlined_as_list(
            slot_name="purposes", slot_type=Purpose, key_name="id", keyed=True
        )

        self._normalize_inlined_as_list(
            slot_name="repositories", slot_type=Repository, key_name="id", keyed=True
        )

        self._normalize_inlined_as_list(
            slot_name="collections", slot_type=Collection, key_name="id", keyed=True
        )

        self._normalize_inlined_as_list(
            slot_name="documents", slot_type=Document, key_name="id", keyed=True
        )

        self._normalize_inlined_as_list(
            slot_name="notes", slot_type=Note, key_name="id", keyed=True
        )

        self._normalize_inlined_as_list(
            slot_name="bookmarks", slot_type=Bookmark, key_name="id", keyed=True
        )

        self._normalize_inlined_as_list(
            slot_name="highlights", slot_type=Highlight, key_name="id", keyed=True
        )

        self._normalize_inlined_as_list(
            slot_name="resources", slot_type=Resource, key_name="id", keyed=True
        )

        self._normalize_inlined_as_list(
            slot_name="themes", slot_type=TopicTaxonomy, key_name="id", keyed=True
        )

        self._normalize_inlined_as_list(
            slot_name="topics", slot_type=Topic, key_name="id", keyed=True
        )

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Activity(YAMLRoot):
    """
    Represents work that requires focus, time, and energy, and may have associated resources
    """

    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = DBO["Work"]
    class_class_curie: ClassVar[str] = "dbo:Work"
    class_name: ClassVar[str] = "Activity"
    class_model_uri: ClassVar[URIRef] = LIFEOS.Activity

    id: str | ActivityId = None
    title: str = None
    description: str | None = None
    created_by: str | None = None
    created_on: str | None = None
    last_updated_on: str | None = None
    url: str | URI | None = None
    activity_type: str | None = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, ActivityId):
            self.id = ActivityId(self.id)

        if self._is_empty(self.title):
            self.MissingRequiredField("title")
        if not isinstance(self.title, str):
            self.title = str(self.title)

        if self.description is not None and not isinstance(self.description, str):
            self.description = str(self.description)

        if self.created_by is not None and not isinstance(self.created_by, str):
            self.created_by = str(self.created_by)

        if self.created_on is not None and not isinstance(self.created_on, str):
            self.created_on = str(self.created_on)

        if self.last_updated_on is not None and not isinstance(
            self.last_updated_on, str
        ):
            self.last_updated_on = str(self.last_updated_on)

        if self.url is not None and not isinstance(self.url, URI):
            self.url = URI(self.url)

        self.activity_type = str(self.class_name)

        super().__post_init__(**kwargs)

    def __new__(cls, *args, **kwargs):
        type_designator = "activity_type"
        if type_designator not in kwargs:
            return super().__new__(cls, *args, **kwargs)
        else:
            type_designator_value = kwargs[type_designator]
            target_cls = cls._class_for("class_name", type_designator_value)

            if target_cls is None:
                raise ValueError(
                    f"Wrong type designator value: class {cls.__name__} "
                    f"has no subclass with ['class_name']='{kwargs[type_designator]}'"
                )
            return super().__new__(target_cls, *args, **kwargs)


@dataclass(repr=False)
class Experiment(Activity):
    """
    Just fooling around, a type of Activity
    """

    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = LIFEOS["Experiment"]
    class_class_curie: ClassVar[str] = "lifeos:Experiment"
    class_name: ClassVar[str] = "Experiment"
    class_model_uri: ClassVar[URIRef] = LIFEOS.Experiment

    id: str | ExperimentId = None
    title: str = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, ExperimentId):
            self.id = ExperimentId(self.id)

        super().__post_init__(**kwargs)
        self.activity_type = str(self.class_name)


@dataclass(repr=False)
class Research(Activity):
    """
    In preparation for work, you need to spend time figuring out how to approach a problem
    """

    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = LIFEOS["Research"]
    class_class_curie: ClassVar[str] = "lifeos:Research"
    class_name: ClassVar[str] = "Research"
    class_model_uri: ClassVar[URIRef] = LIFEOS.Research

    id: str | ResearchId = None
    title: str = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, ResearchId):
            self.id = ResearchId(self.id)

        super().__post_init__(**kwargs)
        self.activity_type = str(self.class_name)


@dataclass(repr=False)
class Study(Activity):
    """
    You spend specific directed effort learning some new thing
    """

    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = LIFEOS["Study"]
    class_class_curie: ClassVar[str] = "lifeos:Study"
    class_name: ClassVar[str] = "Study"
    class_model_uri: ClassVar[URIRef] = LIFEOS.Study

    id: str | StudyId = None
    title: str = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, StudyId):
            self.id = StudyId(self.id)

        super().__post_init__(**kwargs)
        self.activity_type = str(self.class_name)


@dataclass(repr=False)
class Thinking(Activity):
    """
    You spend time creating mental models of life and the world in order to understand it better
    """

    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = LIFEOS["Thinking"]
    class_class_curie: ClassVar[str] = "lifeos:Thinking"
    class_name: ClassVar[str] = "Thinking"
    class_model_uri: ClassVar[URIRef] = LIFEOS.Thinking

    id: str | ThinkingId = None
    title: str = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, ThinkingId):
            self.id = ThinkingId(self.id)

        super().__post_init__(**kwargs)
        self.activity_type = str(self.class_name)


@dataclass(repr=False)
class Task(Activity):
    """
    An individual item of work
    """

    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = LIFEOS["Task"]
    class_class_curie: ClassVar[str] = "lifeos:Task"
    class_name: ClassVar[str] = "Task"
    class_model_uri: ClassVar[URIRef] = LIFEOS.Task

    id: str | TaskId = None
    title: str = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, TaskId):
            self.id = TaskId(self.id)

        super().__post_init__(**kwargs)
        self.activity_type = str(self.class_name)


@dataclass(repr=False)
class Project(Activity):
    """
    Some set of tasks and outcomes that you are spending time on
    """

    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = LIFEOS["Project"]
    class_class_curie: ClassVar[str] = "lifeos:Project"
    class_name: ClassVar[str] = "Project"
    class_model_uri: ClassVar[URIRef] = LIFEOS.Project

    id: str | ProjectId = None
    title: str = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, ProjectId):
            self.id = ProjectId(self.id)

        super().__post_init__(**kwargs)
        self.activity_type = str(self.class_name)


@dataclass(repr=False)
class TopicTaxonomy(YAMLRoot):
    """
    A taxonomy for categorizing resources in a PKM
    """

    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = DCAT["TopicTaxonomy"]
    class_class_curie: ClassVar[str] = "dcat:TopicTaxonomy"
    class_name: ClassVar[str] = "TopicTaxonomy"
    class_model_uri: ClassVar[URIRef] = LIFEOS.TopicTaxonomy

    id: str | TopicTaxonomyId = None
    title: str = None
    description: str | None = None
    created_by: str | None = None
    created_on: str | None = None
    last_updated_on: str | None = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, TopicTaxonomyId):
            self.id = TopicTaxonomyId(self.id)

        if self._is_empty(self.title):
            self.MissingRequiredField("title")
        if not isinstance(self.title, str):
            self.title = str(self.title)

        if self.description is not None and not isinstance(self.description, str):
            self.description = str(self.description)

        if self.created_by is not None and not isinstance(self.created_by, str):
            self.created_by = str(self.created_by)

        if self.created_on is not None and not isinstance(self.created_on, str):
            self.created_on = str(self.created_on)

        if self.last_updated_on is not None and not isinstance(
            self.last_updated_on, str
        ):
            self.last_updated_on = str(self.last_updated_on)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Topic(YAMLRoot):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = SKOS["Concept"]
    class_class_curie: ClassVar[str] = "skos:Concept"
    class_name: ClassVar[str] = "Topic"
    class_model_uri: ClassVar[URIRef] = LIFEOS.Topic

    id: str | TopicId = None
    title: str = None
    theme: str | TopicTaxonomyId | None = None
    description: str | None = None
    created_by: str | None = None
    created_on: str | None = None
    last_updated_on: str | None = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, TopicId):
            self.id = TopicId(self.id)

        if self._is_empty(self.title):
            self.MissingRequiredField("title")
        if not isinstance(self.title, str):
            self.title = str(self.title)

        if self.theme is not None and not isinstance(self.theme, TopicTaxonomyId):
            self.theme = TopicTaxonomyId(self.theme)

        if self.description is not None and not isinstance(self.description, str):
            self.description = str(self.description)

        if self.created_by is not None and not isinstance(self.created_by, str):
            self.created_by = str(self.created_by)

        if self.created_on is not None and not isinstance(self.created_on, str):
            self.created_on = str(self.created_on)

        if self.last_updated_on is not None and not isinstance(
            self.last_updated_on, str
        ):
            self.last_updated_on = str(self.last_updated_on)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Repository(YAMLRoot):
    """
    The system that houses a given resource
    """

    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = LIFEOS["Repository"]
    class_class_curie: ClassVar[str] = "lifeos:Repository"
    class_name: ClassVar[str] = "Repository"
    class_model_uri: ClassVar[URIRef] = LIFEOS.Repository

    id: str | RepositoryId = None
    title: str = None
    service_name: str = None
    description: str | None = None
    created_by: str | None = None
    created_on: str | None = None
    last_updated_on: str | None = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, RepositoryId):
            self.id = RepositoryId(self.id)

        if self._is_empty(self.title):
            self.MissingRequiredField("title")
        if not isinstance(self.title, str):
            self.title = str(self.title)

        if self._is_empty(self.service_name):
            self.MissingRequiredField("service_name")
        if not isinstance(self.service_name, str):
            self.service_name = str(self.service_name)

        if self.description is not None and not isinstance(self.description, str):
            self.description = str(self.description)

        if self.created_by is not None and not isinstance(self.created_by, str):
            self.created_by = str(self.created_by)

        if self.created_on is not None and not isinstance(self.created_on, str):
            self.created_on = str(self.created_on)

        if self.last_updated_on is not None and not isinstance(
            self.last_updated_on, str
        ):
            self.last_updated_on = str(self.last_updated_on)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Catalog(YAMLRoot):
    """
    A group of similar Resource instances around a theme or topic
    """

    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = DCAT["Catalog"]
    class_class_curie: ClassVar[str] = "dcat:Catalog"
    class_name: ClassVar[str] = "Catalog"
    class_model_uri: ClassVar[URIRef] = LIFEOS.Catalog

    id: str | CatalogId = None
    title: str = None
    description: str | None = None
    created_by: str | None = None
    created_on: str | None = None
    last_updated_on: str | None = None
    themes: str | TopicId | list[str | TopicId] | None = empty_list()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, CatalogId):
            self.id = CatalogId(self.id)

        if self._is_empty(self.title):
            self.MissingRequiredField("title")
        if not isinstance(self.title, str):
            self.title = str(self.title)

        if self.description is not None and not isinstance(self.description, str):
            self.description = str(self.description)

        if self.created_by is not None and not isinstance(self.created_by, str):
            self.created_by = str(self.created_by)

        if self.created_on is not None and not isinstance(self.created_on, str):
            self.created_on = str(self.created_on)

        if self.last_updated_on is not None and not isinstance(
            self.last_updated_on, str
        ):
            self.last_updated_on = str(self.last_updated_on)

        if not isinstance(self.themes, list):
            self.themes = [self.themes] if self.themes is not None else []
        self.themes = [v if isinstance(v, TopicId) else TopicId(v) for v in self.themes]

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Resource(YAMLRoot):
    """
    Base class for information resources
    """

    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = DCTERMS["Resource"]
    class_class_curie: ClassVar[str] = "dcterms:Resource"
    class_name: ClassVar[str] = "Resource"
    class_model_uri: ClassVar[URIRef] = LIFEOS.Resource

    id: str | ResourceId = None
    title: str = None
    catalog: str | CatalogId = None
    description: str | None = None
    created_by: str | None = None
    created_on: str | None = None
    last_updated_on: str | None = None
    resource_type: str | None = None
    location: str | None = None
    content_location: str | None = None
    format: str | None = None
    media_type: str | None = None
    created: str | XSDDateTime | None = None
    modified: str | XSDDateTime | None = None
    creator: str | None = None
    theme: str | TopicTaxonomyId | None = None
    subject: str | TopicId | None = None
    related_topics: str | TopicId | list[str | TopicId] | None = empty_list()
    related_resources: str | ResourceId | list[str | ResourceId] | None = empty_list()
    has_use: str | ActivityId | list[str | ActivityId] | None = empty_list()
    has_purpose: str | PurposeId | None = None
    repository: str | RepositoryId | None = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, ResourceId):
            self.id = ResourceId(self.id)

        if self._is_empty(self.title):
            self.MissingRequiredField("title")
        if not isinstance(self.title, str):
            self.title = str(self.title)

        if self._is_empty(self.catalog):
            self.MissingRequiredField("catalog")
        if not isinstance(self.catalog, CatalogId):
            self.catalog = CatalogId(self.catalog)

        if self.description is not None and not isinstance(self.description, str):
            self.description = str(self.description)

        if self.created_by is not None and not isinstance(self.created_by, str):
            self.created_by = str(self.created_by)

        if self.created_on is not None and not isinstance(self.created_on, str):
            self.created_on = str(self.created_on)

        if self.last_updated_on is not None and not isinstance(
            self.last_updated_on, str
        ):
            self.last_updated_on = str(self.last_updated_on)

        self.resource_type = str(self.class_name)

        if self.location is not None and not isinstance(self.location, str):
            self.location = str(self.location)

        if self.content_location is not None and not isinstance(
            self.content_location, str
        ):
            self.content_location = str(self.content_location)

        if self.format is not None and not isinstance(self.format, str):
            self.format = str(self.format)

        if self.media_type is not None and not isinstance(self.media_type, str):
            self.media_type = str(self.media_type)

        if self.created is not None and not isinstance(self.created, XSDDateTime):
            self.created = XSDDateTime(self.created)

        if self.modified is not None and not isinstance(self.modified, XSDDateTime):
            self.modified = XSDDateTime(self.modified)

        if self.creator is not None and not isinstance(self.creator, str):
            self.creator = str(self.creator)

        if self.theme is not None and not isinstance(self.theme, TopicTaxonomyId):
            self.theme = TopicTaxonomyId(self.theme)

        if self.subject is not None and not isinstance(self.subject, TopicId):
            self.subject = TopicId(self.subject)

        if not isinstance(self.related_topics, list):
            self.related_topics = (
                [self.related_topics] if self.related_topics is not None else []
            )
        self.related_topics = [
            v if isinstance(v, TopicId) else TopicId(v) for v in self.related_topics
        ]

        if not isinstance(self.related_resources, list):
            self.related_resources = (
                [self.related_resources] if self.related_resources is not None else []
            )
        self.related_resources = [
            v if isinstance(v, ResourceId) else ResourceId(v)
            for v in self.related_resources
        ]

        if not isinstance(self.has_use, list):
            self.has_use = [self.has_use] if self.has_use is not None else []
        self.has_use = [
            v if isinstance(v, ActivityId) else ActivityId(v) for v in self.has_use
        ]

        if self.has_purpose is not None and not isinstance(self.has_purpose, PurposeId):
            self.has_purpose = PurposeId(self.has_purpose)

        if self.repository is not None and not isinstance(
            self.repository, RepositoryId
        ):
            self.repository = RepositoryId(self.repository)

        super().__post_init__(**kwargs)

    def __new__(cls, *args, **kwargs):
        type_designator = "resource_type"
        if type_designator not in kwargs:
            return super().__new__(cls, *args, **kwargs)
        else:
            type_designator_value = kwargs[type_designator]
            target_cls = cls._class_for("class_name", type_designator_value)

            if target_cls is None:
                raise ValueError(
                    f"Wrong type designator value: class {cls.__name__} "
                    f"has no subclass with ['class_name']='{kwargs[type_designator]}'"
                )
            return super().__new__(target_cls, *args, **kwargs)


@dataclass(repr=False)
class Collection(Resource):
    """
    A group of Resources centered around some need or theme
    """

    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = LIFEOS["Collection"]
    class_class_curie: ClassVar[str] = "lifeos:Collection"
    class_name: ClassVar[str] = "Collection"
    class_model_uri: ClassVar[URIRef] = LIFEOS.Collection

    id: str | CollectionId = None
    title: str = None
    catalog: str | CatalogId = None
    has_use: str | ActivityId | list[str | ActivityId] = None
    description: str | None = None
    created_by: str | None = None
    created_on: str | None = None
    last_updated_on: str | None = None
    has_resources: str | ResourceId | list[str | ResourceId] | None = empty_list()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, CollectionId):
            self.id = CollectionId(self.id)

        if self._is_empty(self.title):
            self.MissingRequiredField("title")
        if not isinstance(self.title, str):
            self.title = str(self.title)

        if self._is_empty(self.catalog):
            self.MissingRequiredField("catalog")
        if not isinstance(self.catalog, CatalogId):
            self.catalog = CatalogId(self.catalog)

        if self._is_empty(self.has_use):
            self.MissingRequiredField("has_use")
        if not isinstance(self.has_use, list):
            self.has_use = [self.has_use] if self.has_use is not None else []
        self.has_use = [
            v if isinstance(v, ActivityId) else ActivityId(v) for v in self.has_use
        ]

        if self.description is not None and not isinstance(self.description, str):
            self.description = str(self.description)

        if self.created_by is not None and not isinstance(self.created_by, str):
            self.created_by = str(self.created_by)

        if self.created_on is not None and not isinstance(self.created_on, str):
            self.created_on = str(self.created_on)

        if self.last_updated_on is not None and not isinstance(
            self.last_updated_on, str
        ):
            self.last_updated_on = str(self.last_updated_on)

        if not isinstance(self.has_resources, list):
            self.has_resources = (
                [self.has_resources] if self.has_resources is not None else []
            )
        self.has_resources = [
            v if isinstance(v, ResourceId) else ResourceId(v)
            for v in self.has_resources
        ]

        super().__post_init__(**kwargs)
        self.resource_type = str(self.class_name)


@dataclass(repr=False)
class Purpose(YAMLRoot):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = LIFEOS["Purpose"]
    class_class_curie: ClassVar[str] = "lifeos:Purpose"
    class_name: ClassVar[str] = "Purpose"
    class_model_uri: ClassVar[URIRef] = LIFEOS.Purpose

    id: str | PurposeId = None
    title: str = None
    description: str | None = None
    created_by: str | None = None
    created_on: str | None = None
    last_updated_on: str | None = None
    meaning: str | ActivityId | None = None
    role: str | None = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, PurposeId):
            self.id = PurposeId(self.id)

        if self._is_empty(self.title):
            self.MissingRequiredField("title")
        if not isinstance(self.title, str):
            self.title = str(self.title)

        if self.description is not None and not isinstance(self.description, str):
            self.description = str(self.description)

        if self.created_by is not None and not isinstance(self.created_by, str):
            self.created_by = str(self.created_by)

        if self.created_on is not None and not isinstance(self.created_on, str):
            self.created_on = str(self.created_on)

        if self.last_updated_on is not None and not isinstance(
            self.last_updated_on, str
        ):
            self.last_updated_on = str(self.last_updated_on)

        if self.meaning is not None and not isinstance(self.meaning, ActivityId):
            self.meaning = ActivityId(self.meaning)

        if self.role is not None and not isinstance(self.role, str):
            self.role = str(self.role)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Note(Resource):
    """
    Small data being ingested
    """

    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = LIFEOS["Note"]
    class_class_curie: ClassVar[str] = "lifeos:Note"
    class_name: ClassVar[str] = "Note"
    class_model_uri: ClassVar[URIRef] = LIFEOS.Note

    id: str | NoteId = None
    catalog: str | CatalogId = None
    title: str = None
    repository: str | RepositoryId = None
    content_location: str | None = None
    note_type: Union[str, "NoteType"] | None = None
    description: str | None = None
    created_by: str | None = None
    created_on: str | None = None
    last_updated_on: str | None = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, NoteId):
            self.id = NoteId(self.id)

        if self._is_empty(self.title):
            self.MissingRequiredField("title")
        if not isinstance(self.title, str):
            self.title = str(self.title)

        if self._is_empty(self.repository):
            self.MissingRequiredField("repository")
        if not isinstance(self.repository, RepositoryId):
            self.repository = RepositoryId(self.repository)

        if self.content_location is not None and not isinstance(
            self.content_location, str
        ):
            self.content_location = str(self.content_location)

        if self.note_type is not None and not isinstance(self.note_type, NoteType):
            self.note_type = NoteType(self.note_type)

        if self.description is not None and not isinstance(self.description, str):
            self.description = str(self.description)

        if self.created_by is not None and not isinstance(self.created_by, str):
            self.created_by = str(self.created_by)

        if self.created_on is not None and not isinstance(self.created_on, str):
            self.created_on = str(self.created_on)

        if self.last_updated_on is not None and not isinstance(
            self.last_updated_on, str
        ):
            self.last_updated_on = str(self.last_updated_on)

        super().__post_init__(**kwargs)
        self.resource_type = str(self.class_name)


@dataclass(repr=False)
class Document(Resource):
    """
    Larger container or promoted Note; used only for documents authored by the Self
    """

    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = FOAF["Document"]
    class_class_curie: ClassVar[str] = "foaf:Document"
    class_name: ClassVar[str] = "Document"
    class_model_uri: ClassVar[URIRef] = LIFEOS.Document

    id: str | DocumentId = None
    catalog: str | CatalogId = None
    title: str = None
    repository: str | RepositoryId = None
    content_location: str | None = None
    document_type: Union[str, "DocumentType"] | None = None
    description: str | None = None
    created_by: str | None = None
    created_on: str | None = None
    last_updated_on: str | None = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, DocumentId):
            self.id = DocumentId(self.id)

        if self._is_empty(self.title):
            self.MissingRequiredField("title")
        if not isinstance(self.title, str):
            self.title = str(self.title)

        if self._is_empty(self.repository):
            self.MissingRequiredField("repository")
        if not isinstance(self.repository, RepositoryId):
            self.repository = RepositoryId(self.repository)

        if self.content_location is not None and not isinstance(
            self.content_location, str
        ):
            self.content_location = str(self.content_location)

        if self.document_type is not None and not isinstance(
            self.document_type, DocumentType
        ):
            self.document_type = DocumentType(self.document_type)

        if self.description is not None and not isinstance(self.description, str):
            self.description = str(self.description)

        if self.created_by is not None and not isinstance(self.created_by, str):
            self.created_by = str(self.created_by)

        if self.created_on is not None and not isinstance(self.created_on, str):
            self.created_on = str(self.created_on)

        if self.last_updated_on is not None and not isinstance(
            self.last_updated_on, str
        ):
            self.last_updated_on = str(self.last_updated_on)

        super().__post_init__(**kwargs)
        self.resource_type = str(self.class_name)


@dataclass(repr=False)
class Bookmark(Resource):
    """
    A Collected Resource, aka a URL with no content
    """

    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = LIFEOS["Bookmark"]
    class_class_curie: ClassVar[str] = "lifeos:Bookmark"
    class_name: ClassVar[str] = "Bookmark"
    class_model_uri: ClassVar[URIRef] = LIFEOS.Bookmark

    id: str | BookmarkId = None
    catalog: str | CatalogId = None
    title: str = None
    repository: str | RepositoryId | None = None
    description: str | None = None
    created_by: str | None = None
    created_on: str | None = None
    last_updated_on: str | None = None
    highlights: str | HighlightId | list[str | HighlightId] | None = empty_list()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, BookmarkId):
            self.id = BookmarkId(self.id)

        if self._is_empty(self.title):
            self.MissingRequiredField("title")
        if not isinstance(self.title, str):
            self.title = str(self.title)

        if self.repository is not None and not isinstance(
            self.repository, RepositoryId
        ):
            self.repository = RepositoryId(self.repository)

        if self.description is not None and not isinstance(self.description, str):
            self.description = str(self.description)

        if self.created_by is not None and not isinstance(self.created_by, str):
            self.created_by = str(self.created_by)

        if self.created_on is not None and not isinstance(self.created_on, str):
            self.created_on = str(self.created_on)

        if self.last_updated_on is not None and not isinstance(
            self.last_updated_on, str
        ):
            self.last_updated_on = str(self.last_updated_on)

        if not isinstance(self.highlights, list):
            self.highlights = [self.highlights] if self.highlights is not None else []
        self.highlights = [
            v if isinstance(v, HighlightId) else HighlightId(v) for v in self.highlights
        ]

        super().__post_init__(**kwargs)
        self.resource_type = str(self.class_name)


@dataclass(repr=False)
class Highlight(Resource):
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = LIFEOS["Highlight"]
    class_class_curie: ClassVar[str] = "lifeos:Highlight"
    class_name: ClassVar[str] = "Highlight"
    class_model_uri: ClassVar[URIRef] = LIFEOS.Highlight

    id: str | HighlightId = None
    catalog: str | CatalogId = None
    title: str = None
    repository: str | RepositoryId | None = None
    description: str | None = None
    created_by: str | None = None
    created_on: str | None = None
    last_updated_on: str | None = None
    bookmark: str | BookmarkId | None = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, HighlightId):
            self.id = HighlightId(self.id)

        if self._is_empty(self.title):
            self.MissingRequiredField("title")
        if not isinstance(self.title, str):
            self.title = str(self.title)

        if self.repository is not None and not isinstance(
            self.repository, RepositoryId
        ):
            self.repository = RepositoryId(self.repository)

        if self.description is not None and not isinstance(self.description, str):
            self.description = str(self.description)

        if self.created_by is not None and not isinstance(self.created_by, str):
            self.created_by = str(self.created_by)

        if self.created_on is not None and not isinstance(self.created_on, str):
            self.created_on = str(self.created_on)

        if self.last_updated_on is not None and not isinstance(
            self.last_updated_on, str
        ):
            self.last_updated_on = str(self.last_updated_on)

        if self.bookmark is not None and not isinstance(self.bookmark, BookmarkId):
            self.bookmark = BookmarkId(self.bookmark)

        super().__post_init__(**kwargs)
        self.resource_type = str(self.class_name)


# Enumerations
class NoteType(EnumDefinitionImpl):
    Note = PermissibleValue(text="Note")
    Log = PermissibleValue(text="Log")
    Thought = PermissibleValue(text="Thought")
    Idea = PermissibleValue(text="Idea")
    Reference = PermissibleValue(text="Reference")
    Highlight = PermissibleValue(text="Highlight")

    _defn = EnumDefinition(
        name="NoteType",
    )


class DocumentType(EnumDefinitionImpl):
    Document = PermissibleValue(text="Document")
    Journal = PermissibleValue(text="Journal")
    List = PermissibleValue(text="List")
    Notebook = PermissibleValue(text="Notebook")
    Logbook = PermissibleValue(text="Logbook")
    Inventory = PermissibleValue(text="Inventory")
    Landscape = PermissibleValue(text="Landscape")

    _defn = EnumDefinition(
        name="DocumentType",
    )


# Slots
class slots:
    pass


slots.id = Slot(
    uri=SCHEMA.identifier,
    name="id",
    curie=SCHEMA.curie("identifier"),
    model_uri=LIFEOS.id,
    domain=None,
    range=URIRef,
)

slots.title = Slot(
    uri=LIFEOS.title,
    name="title",
    curie=LIFEOS.curie("title"),
    model_uri=LIFEOS.title,
    domain=None,
    range=str,
)

slots.description = Slot(
    uri=LIFEOS.description,
    name="description",
    curie=LIFEOS.curie("description"),
    model_uri=LIFEOS.description,
    domain=None,
    range=Optional[str],
)

slots.created_by = Slot(
    uri=LIFEOS.created_by,
    name="created_by",
    curie=LIFEOS.curie("created_by"),
    model_uri=LIFEOS.created_by,
    domain=None,
    range=Optional[str],
)

slots.created_on = Slot(
    uri=LIFEOS.created_on,
    name="created_on",
    curie=LIFEOS.curie("created_on"),
    model_uri=LIFEOS.created_on,
    domain=None,
    range=Optional[str],
)

slots.last_updated_on = Slot(
    uri=LIFEOS.last_updated_on,
    name="last_updated_on",
    curie=LIFEOS.curie("last_updated_on"),
    model_uri=LIFEOS.last_updated_on,
    domain=None,
    range=Optional[str],
)

slots.url = Slot(
    uri=SCHEMA.url,
    name="url",
    curie=SCHEMA.curie("url"),
    model_uri=LIFEOS.url,
    domain=None,
    range=Optional[str | URI],
)

slots.relation = Slot(
    uri=DCTERMS.relation,
    name="relation",
    curie=DCTERMS.curie("relation"),
    model_uri=LIFEOS.relation,
    domain=None,
    range=Optional[str | list[str]],
)

slots.activity_type = Slot(
    uri=LIFEOS.activity_type,
    name="activity_type",
    curie=LIFEOS.curie("activity_type"),
    model_uri=LIFEOS.activity_type,
    domain=None,
    range=Optional[str],
)

slots.service_name = Slot(
    uri=LIFEOS.service_name,
    name="service_name",
    curie=LIFEOS.curie("service_name"),
    model_uri=LIFEOS.service_name,
    domain=None,
    range=Optional[str],
)

slots.themes = Slot(
    uri=DCAT.themeTaxonomy,
    name="themes",
    curie=DCAT.curie("themeTaxonomy"),
    model_uri=LIFEOS.themes,
    domain=Catalog,
    range=Optional[str | TopicId | list[str | TopicId]],
)

slots.repository = Slot(
    uri=LIFEOS.repository,
    name="repository",
    curie=LIFEOS.curie("repository"),
    model_uri=LIFEOS.repository,
    domain=Resource,
    range=Optional[str | RepositoryId],
)

slots.has_resources = Slot(
    uri=DCTERMS.HasPart,
    name="has_resources",
    curie=DCTERMS.curie("HasPart"),
    model_uri=LIFEOS.has_resources,
    domain=Collection,
    range=Optional[str | ResourceId | list[str | ResourceId]],
)

slots.belongs_to = Slot(
    uri=DCTERMS.isPartOf,
    name="belongs_to",
    curie=DCTERMS.curie("isPartOf"),
    model_uri=LIFEOS.belongs_to,
    domain=Resource,
    range=Optional[str | CollectionId],
)

slots.resource_type = Slot(
    uri=LIFEOS.resource_type,
    name="resource_type",
    curie=LIFEOS.curie("resource_type"),
    model_uri=LIFEOS.resource_type,
    domain=None,
    range=Optional[str],
)

slots.location = Slot(
    uri=DCAT.accessURL,
    name="location",
    curie=DCAT.curie("accessURL"),
    model_uri=LIFEOS.location,
    domain=None,
    range=Optional[str],
)

slots.content_location = Slot(
    uri=DCAT.accessURL,
    name="content_location",
    curie=DCAT.curie("accessURL"),
    model_uri=LIFEOS.content_location,
    domain=None,
    range=Optional[str],
)

slots.created = Slot(
    uri=DCTERMS.created,
    name="created",
    curie=DCTERMS.curie("created"),
    model_uri=LIFEOS.created,
    domain=None,
    range=Optional[str | XSDDateTime],
)

slots.modified = Slot(
    uri=DCTERMS.modified,
    name="modified",
    curie=DCTERMS.curie("modified"),
    model_uri=LIFEOS.modified,
    domain=None,
    range=Optional[str | XSDDateTime],
)

slots.format = Slot(
    uri=DCTERMS.format,
    name="format",
    curie=DCTERMS.curie("format"),
    model_uri=LIFEOS.format,
    domain=None,
    range=Optional[str],
)

slots.media_type = Slot(
    uri=DCAT.mediaType,
    name="media_type",
    curie=DCAT.curie("mediaType"),
    model_uri=LIFEOS.media_type,
    domain=None,
    range=Optional[str],
)

slots.version = Slot(
    uri=SCHEMA.version,
    name="version",
    curie=SCHEMA.curie("version"),
    model_uri=LIFEOS.version,
    domain=None,
    range=Optional[str],
)

slots.creator = Slot(
    uri=FOAF.mbox,
    name="creator",
    curie=FOAF.curie("mbox"),
    model_uri=LIFEOS.creator,
    domain=None,
    range=Optional[str],
)

slots.has_use = Slot(
    uri=DCTERMS.isPartOf,
    name="has_use",
    curie=DCTERMS.curie("isPartOf"),
    model_uri=LIFEOS.has_use,
    domain=Resource,
    range=Optional[str | ActivityId | list[str | ActivityId]],
)

slots.has_purpose = Slot(
    uri=LIFEOS.has_purpose,
    name="has_purpose",
    curie=LIFEOS.curie("has_purpose"),
    model_uri=LIFEOS.has_purpose,
    domain=Resource,
    range=Optional[str | PurposeId],
)

slots.meaning = Slot(
    uri=LIFEOS.meaning,
    name="meaning",
    curie=LIFEOS.curie("meaning"),
    model_uri=LIFEOS.meaning,
    domain=None,
    range=Optional[str | ActivityId],
)

slots.role = Slot(
    uri=LIFEOS.role,
    name="role",
    curie=LIFEOS.curie("role"),
    model_uri=LIFEOS.role,
    domain=None,
    range=Optional[str],
)

slots.theme = Slot(
    uri=DCAT.theme,
    name="theme",
    curie=DCAT.curie("theme"),
    model_uri=LIFEOS.theme,
    domain=Resource,
    range=Optional[str | TopicTaxonomyId],
)

slots.subject = Slot(
    uri=DCTERMS.relation,
    name="subject",
    curie=DCTERMS.curie("relation"),
    model_uri=LIFEOS.subject,
    domain=Resource,
    range=Optional[str | TopicId],
)

slots.related_topics = Slot(
    uri=DCTERMS.relation,
    name="related_topics",
    curie=DCTERMS.curie("relation"),
    model_uri=LIFEOS.related_topics,
    domain=Resource,
    range=Optional[str | TopicId | list[str | TopicId]],
)

slots.related_resources = Slot(
    uri=DCTERMS.relation,
    name="related_resources",
    curie=DCTERMS.curie("relation"),
    model_uri=LIFEOS.related_resources,
    domain=Resource,
    range=Optional[str | ResourceId | list[str | ResourceId]],
)

slots.catalog = Slot(
    uri=DCTERMS.isPartOf,
    name="catalog",
    curie=DCTERMS.curie("isPartOf"),
    model_uri=LIFEOS.catalog,
    domain=Resource,
    range=Union[str, CatalogId],
)

slots.bookmark = Slot(
    uri=LIFEOS.bookmark,
    name="bookmark",
    curie=LIFEOS.curie("bookmark"),
    model_uri=LIFEOS.bookmark,
    domain=None,
    range=Optional[str | BookmarkId],
)

slots.highlights = Slot(
    uri=LIFEOS.highlights,
    name="highlights",
    curie=LIFEOS.curie("highlights"),
    model_uri=LIFEOS.highlights,
    domain=None,
    range=Optional[str | HighlightId | list[str | HighlightId]],
)

slots.document_type = Slot(
    uri=LIFEOS.document_type,
    name="document_type",
    curie=LIFEOS.curie("document_type"),
    model_uri=LIFEOS.document_type,
    domain=Document,
    range=Optional[Union[str, "DocumentType"]],
)

slots.note_type = Slot(
    uri=LIFEOS.note_type,
    name="note_type",
    curie=LIFEOS.curie("note_type"),
    model_uri=LIFEOS.note_type,
    domain=Note,
    range=Optional[Union[str, "NoteType"]],
)

slots.self__activities = Slot(
    uri=LIFEOS.activities,
    name="self__activities",
    curie=LIFEOS.curie("activities"),
    model_uri=LIFEOS.self__activities,
    domain=None,
    range=Optional[dict[str | ActivityId, dict | Activity] | list[dict | Activity]],
)

slots.self__catalog = Slot(
    uri=LIFEOS.catalog,
    name="self__catalog",
    curie=LIFEOS.curie("catalog"),
    model_uri=LIFEOS.self__catalog,
    domain=None,
    range=Optional[dict[str | CatalogId, dict | Catalog] | list[dict | Catalog]],
)

slots.self__purposes = Slot(
    uri=LIFEOS.purposes,
    name="self__purposes",
    curie=LIFEOS.curie("purposes"),
    model_uri=LIFEOS.self__purposes,
    domain=None,
    range=Optional[dict[str | PurposeId, dict | Purpose] | list[dict | Purpose]],
)

slots.self__repositories = Slot(
    uri=LIFEOS.repositories,
    name="self__repositories",
    curie=LIFEOS.curie("repositories"),
    model_uri=LIFEOS.self__repositories,
    domain=None,
    range=Optional[
        dict[str | RepositoryId, dict | Repository] | list[dict | Repository]
    ],
)

slots.self__collections = Slot(
    uri=LIFEOS.collections,
    name="self__collections",
    curie=LIFEOS.curie("collections"),
    model_uri=LIFEOS.self__collections,
    domain=None,
    range=Optional[
        dict[str | CollectionId, dict | Collection] | list[dict | Collection]
    ],
)

slots.self__documents = Slot(
    uri=LIFEOS.documents,
    name="self__documents",
    curie=LIFEOS.curie("documents"),
    model_uri=LIFEOS.self__documents,
    domain=None,
    range=Optional[dict[str | DocumentId, dict | Document] | list[dict | Document]],
)

slots.self__notes = Slot(
    uri=LIFEOS.notes,
    name="self__notes",
    curie=LIFEOS.curie("notes"),
    model_uri=LIFEOS.self__notes,
    domain=None,
    range=Optional[dict[str | NoteId, dict | Note] | list[dict | Note]],
)

slots.self__bookmarks = Slot(
    uri=LIFEOS.bookmarks,
    name="self__bookmarks",
    curie=LIFEOS.curie("bookmarks"),
    model_uri=LIFEOS.self__bookmarks,
    domain=None,
    range=Optional[dict[str | BookmarkId, dict | Bookmark] | list[dict | Bookmark]],
)

slots.self__highlights = Slot(
    uri=LIFEOS.highlights,
    name="self__highlights",
    curie=LIFEOS.curie("highlights"),
    model_uri=LIFEOS.self__highlights,
    domain=None,
    range=Optional[dict[str | HighlightId, dict | Highlight] | list[dict | Highlight]],
)

slots.self__resources = Slot(
    uri=LIFEOS.resources,
    name="self__resources",
    curie=LIFEOS.curie("resources"),
    model_uri=LIFEOS.self__resources,
    domain=None,
    range=Optional[dict[str | ResourceId, dict | Resource] | list[dict | Resource]],
)

slots.self__themes = Slot(
    uri=LIFEOS.themes,
    name="self__themes",
    curie=LIFEOS.curie("themes"),
    model_uri=LIFEOS.self__themes,
    domain=None,
    range=Optional[
        dict[str | TopicTaxonomyId, dict | TopicTaxonomy] | list[dict | TopicTaxonomy]
    ],
)

slots.self__topics = Slot(
    uri=LIFEOS.topics,
    name="self__topics",
    curie=LIFEOS.curie("topics"),
    model_uri=LIFEOS.self__topics,
    domain=None,
    range=Optional[dict[str | TopicId, dict | Topic] | list[dict | Topic]],
)

slots.Repository_service_name = Slot(
    uri=LIFEOS.service_name,
    name="Repository_service_name",
    curie=LIFEOS.curie("service_name"),
    model_uri=LIFEOS.Repository_service_name,
    domain=Repository,
    range=str,
)

slots.Collection_has_use = Slot(
    uri=DCTERMS.isPartOf,
    name="Collection_has_use",
    curie=DCTERMS.curie("isPartOf"),
    model_uri=LIFEOS.Collection_has_use,
    domain=Collection,
    range=Union[str | ActivityId, list[str | ActivityId]],
)

slots.Note_repository = Slot(
    uri=LIFEOS.repository,
    name="Note_repository",
    curie=LIFEOS.curie("repository"),
    model_uri=LIFEOS.Note_repository,
    domain=Note,
    range=Union[str, RepositoryId],
)

slots.Document_repository = Slot(
    uri=LIFEOS.repository,
    name="Document_repository",
    curie=LIFEOS.curie("repository"),
    model_uri=LIFEOS.Document_repository,
    domain=Document,
    range=Union[str, RepositoryId],
)
