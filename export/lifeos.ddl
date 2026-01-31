-- # Class: Self
--     * Slot: id
-- # Abstract Class: Activity Description: Represents work that requires focus, time, and energy, and may have associated resources
--     * Slot: id Description: Unique identifier for any entity
--     * Slot: title
--     * Slot: description
--     * Slot: created_by
--     * Slot: created_on
--     * Slot: last_updated_on
--     * Slot: url Description: An optional URL associated with this instance.
--     * Slot: activity_type
--     * Slot: Self_id Description: Autocreated FK slot
-- # Class: Experiment Description: Just fooling around, a type of Activity
--     * Slot: id Description: Unique identifier for any entity
--     * Slot: title
--     * Slot: description
--     * Slot: created_by
--     * Slot: created_on
--     * Slot: last_updated_on
--     * Slot: url Description: An optional URL associated with this instance.
--     * Slot: activity_type
-- # Class: Research Description: In preparation for work, you need to spend time figuring out how to approach a problem
--     * Slot: id Description: Unique identifier for any entity
--     * Slot: title
--     * Slot: description
--     * Slot: created_by
--     * Slot: created_on
--     * Slot: last_updated_on
--     * Slot: url Description: An optional URL associated with this instance.
--     * Slot: activity_type
-- # Class: Study Description: You spend specific directed effort learning some new thing
--     * Slot: id Description: Unique identifier for any entity
--     * Slot: title
--     * Slot: description
--     * Slot: created_by
--     * Slot: created_on
--     * Slot: last_updated_on
--     * Slot: url Description: An optional URL associated with this instance.
--     * Slot: activity_type
-- # Class: Thinking Description: You spend time creating mental models of life and the world in order to understand it better
--     * Slot: id Description: Unique identifier for any entity
--     * Slot: title
--     * Slot: description
--     * Slot: created_by
--     * Slot: created_on
--     * Slot: last_updated_on
--     * Slot: url Description: An optional URL associated with this instance.
--     * Slot: activity_type
-- # Class: Task Description: An individual item of work
--     * Slot: id Description: Unique identifier for any entity
--     * Slot: title
--     * Slot: description
--     * Slot: created_by
--     * Slot: created_on
--     * Slot: last_updated_on
--     * Slot: url Description: An optional URL associated with this instance.
--     * Slot: activity_type
-- # Class: Project Description: Some set of tasks and outcomes that you are spending time on
--     * Slot: id Description: Unique identifier for any entity
--     * Slot: title
--     * Slot: description
--     * Slot: created_by
--     * Slot: created_on
--     * Slot: last_updated_on
--     * Slot: url Description: An optional URL associated with this instance.
--     * Slot: activity_type
-- # Class: TopicTaxonomy Description: A taxonomy for categorizing resources (SKOS Concept Scheme)
--     * Slot: id Description: Unique identifier for any entity
--     * Slot: title
--     * Slot: description
--     * Slot: created_by
--     * Slot: created_on
--     * Slot: last_updated_on
--     * Slot: default_language Description: Default language for labels (e.g., 'en')
--     * Slot: skos_uri Description: URI for SKOS export
--     * Slot: Self_id Description: Autocreated FK slot
-- # Class: Topic Description: A concept within a taxonomy (SKOS Concept)
--     * Slot: id Description: Unique identifier for any entity
--     * Slot: taxonomy_id Description: The taxonomy this topic belongs to (SKOS inScheme)
--     * Slot: title
--     * Slot: slug Description: URL-safe identifier derived from title
--     * Slot: description
--     * Slot: status Description: Lifecycle status
--     * Slot: external_refs Description: References to external systems (JSON object)
--     * Slot: materialized_path Description: Pre-computed path for display (e.g., /parent/child/grandchild)
--     * Slot: created_by
--     * Slot: created_on
--     * Slot: last_updated_on
--     * Slot: Self_id Description: Autocreated FK slot
-- # Class: TopicEdge Description: Directed edge between topics in a hierarchy
--     * Slot: id
--     * Slot: parent_id Description: Parent topic ID
--     * Slot: child_id Description: Child topic ID
--     * Slot: role Description: Semantic relationship type
--     * Slot: source Description: How edge was created (e.g., 'manual', 'imported', 'ai_suggested')
--     * Slot: confidence Description: Confidence score 0.0-1.0 for AI-suggested edges
--     * Slot: created_on
-- # Class: TopicClosure Description: Transitive closure table for efficient ancestor/descendant queries
--     * Slot: id
--     * Slot: ancestor_id Description: Ancestor topic ID
--     * Slot: descendant_id Description: Descendant topic ID
--     * Slot: depth Description: Number of edges in path (0 = self-reference)
-- # Class: Match Description: Mapping to external ontology concepts
--     * Slot: id Description: Unique identifier for any entity
--     * Slot: entity_type Description: Type of entity being matched
--     * Slot: entity_id Description: ID of the local entity
--     * Slot: external_system Description: External system name (e.g., 'wikidata', 'mesh', 'lcsh')
--     * Slot: external_id Description: ID in external system
--     * Slot: match_type Description: Type/strength of match
--     * Slot: confidence Description: Confidence score 0.0-1.0
--     * Slot: evidence Description: JSON object with match evidence
--     * Slot: created_on
-- # Class: Resource Description: Base class for information resources
--     * Slot: id Description: Unique identifier for any entity
--     * Slot: title
--     * Slot: description
--     * Slot: created_by
--     * Slot: created_on
--     * Slot: last_updated_on
--     * Slot: resource_type
--     * Slot: location Description: The canonical URL of the resource in its external repository.
--     * Slot: content_location Description: URL of the content for this resource, expectation is these are served from an object store
--     * Slot: format Description: The file format of the resource object
--     * Slot: media_type Description: MIME type (e.g., text/markdown, video/mp4) of the resource's content
--     * Slot: created Description: The date on which the entity was created.
--     * Slot: modified Description: The date on which the entity was updated.
--     * Slot: creator
--     * Slot: theme Description: Resource is releated to some topic, subject, concept defined in the life business knowledge taxonomy
--     * Slot: subject
--     * Slot: has_purpose Description: Resource is the designated $X of $Y
--     * Slot: catalog Description: The Catalog the resource belongs to
--     * Slot: repository Description: The repository a resource is stored in
--     * Slot: Self_id Description: Autocreated FK slot
-- # Class: Purpose
--     * Slot: id Description: Unique identifier for any entity
--     * Slot: title
--     * Slot: description
--     * Slot: created_by
--     * Slot: created_on
--     * Slot: last_updated_on
--     * Slot: meaning Description: what meaning is applied to the purpose
--     * Slot: role Description: Relationship type
--     * Slot: Self_id Description: Autocreated FK slot
-- # Class: Repository Description: The system that houses a given resource
--     * Slot: id Description: Unique identifier for any entity
--     * Slot: title
--     * Slot: description
--     * Slot: created_by
--     * Slot: created_on
--     * Slot: last_updated_on
--     * Slot: service_name Description: The name of an app being used for KM, future state this will be a first-class entity
--     * Slot: Self_id Description: Autocreated FK slot
-- # Class: Collection Description: A group of Resources centered around some need or theme
--     * Slot: id Description: Unique identifier for any entity
--     * Slot: title
--     * Slot: description
--     * Slot: created_by
--     * Slot: created_on
--     * Slot: last_updated_on
--     * Slot: catalog Description: The Catalog the resource belongs to
--     * Slot: resource_type
--     * Slot: location Description: The canonical URL of the resource in its external repository.
--     * Slot: content_location Description: URL of the content for this resource, expectation is these are served from an object store
--     * Slot: format Description: The file format of the resource object
--     * Slot: media_type Description: MIME type (e.g., text/markdown, video/mp4) of the resource's content
--     * Slot: created Description: The date on which the entity was created.
--     * Slot: modified Description: The date on which the entity was updated.
--     * Slot: creator
--     * Slot: theme Description: Resource is releated to some topic, subject, concept defined in the life business knowledge taxonomy
--     * Slot: subject
--     * Slot: has_purpose Description: Resource is the designated $X of $Y
--     * Slot: repository Description: The repository a resource is stored in
--     * Slot: Self_id Description: Autocreated FK slot
-- # Class: Catalog Description: A group of similar Resource instances around a theme or topic
--     * Slot: id Description: Unique identifier for any entity
--     * Slot: title
--     * Slot: description
--     * Slot: created_by
--     * Slot: created_on
--     * Slot: last_updated_on
--     * Slot: Self_id Description: Autocreated FK slot
-- # Class: Note Description: Small data being ingested
--     * Slot: id Description: Unique identifier for any entity
--     * Slot: title
--     * Slot: content_location Description: URL of the content for this resource, expectation is these are served from an object store
--     * Slot: note_type
--     * Slot: description
--     * Slot: created_by
--     * Slot: created_on
--     * Slot: last_updated_on
--     * Slot: resource_type
--     * Slot: location Description: The canonical URL of the resource in its external repository.
--     * Slot: format Description: The file format of the resource object
--     * Slot: media_type Description: MIME type (e.g., text/markdown, video/mp4) of the resource's content
--     * Slot: created Description: The date on which the entity was created.
--     * Slot: modified Description: The date on which the entity was updated.
--     * Slot: creator
--     * Slot: theme Description: Resource is releated to some topic, subject, concept defined in the life business knowledge taxonomy
--     * Slot: subject
--     * Slot: has_purpose Description: Resource is the designated $X of $Y
--     * Slot: catalog Description: The Catalog the resource belongs to
--     * Slot: repository Description: The repository a resource is stored in
--     * Slot: Self_id Description: Autocreated FK slot
-- # Class: Document Description: Larger container or promoted Note; used only for documents authored by the Self
--     * Slot: id Description: Unique identifier for any entity
--     * Slot: title
--     * Slot: content_location Description: URL of the content for this resource, expectation is these are served from an object store
--     * Slot: document_type
--     * Slot: description
--     * Slot: created_by
--     * Slot: created_on
--     * Slot: last_updated_on
--     * Slot: resource_type
--     * Slot: location Description: The canonical URL of the resource in its external repository.
--     * Slot: format Description: The file format of the resource object
--     * Slot: media_type Description: MIME type (e.g., text/markdown, video/mp4) of the resource's content
--     * Slot: created Description: The date on which the entity was created.
--     * Slot: modified Description: The date on which the entity was updated.
--     * Slot: creator
--     * Slot: theme Description: Resource is releated to some topic, subject, concept defined in the life business knowledge taxonomy
--     * Slot: subject
--     * Slot: has_purpose Description: Resource is the designated $X of $Y
--     * Slot: catalog Description: The Catalog the resource belongs to
--     * Slot: repository Description: The repository a resource is stored in
--     * Slot: Self_id Description: Autocreated FK slot
-- # Class: Bookmark Description: A Collected Resource, aka a URL with no content
--     * Slot: id Description: Unique identifier for any entity
--     * Slot: title
--     * Slot: repository Description: The repository a resource is stored in
--     * Slot: description
--     * Slot: created_by
--     * Slot: created_on
--     * Slot: last_updated_on
--     * Slot: resource_type
--     * Slot: location Description: The canonical URL of the resource in its external repository.
--     * Slot: content_location Description: URL of the content for this resource, expectation is these are served from an object store
--     * Slot: format Description: The file format of the resource object
--     * Slot: media_type Description: MIME type (e.g., text/markdown, video/mp4) of the resource's content
--     * Slot: created Description: The date on which the entity was created.
--     * Slot: modified Description: The date on which the entity was updated.
--     * Slot: creator
--     * Slot: theme Description: Resource is releated to some topic, subject, concept defined in the life business knowledge taxonomy
--     * Slot: subject
--     * Slot: has_purpose Description: Resource is the designated $X of $Y
--     * Slot: catalog Description: The Catalog the resource belongs to
--     * Slot: Self_id Description: Autocreated FK slot
-- # Class: Highlight
--     * Slot: id Description: Unique identifier for any entity
--     * Slot: title
--     * Slot: repository Description: The repository a resource is stored in
--     * Slot: description
--     * Slot: created_by
--     * Slot: created_on
--     * Slot: last_updated_on
--     * Slot: bookmark
--     * Slot: resource_type
--     * Slot: location Description: The canonical URL of the resource in its external repository.
--     * Slot: content_location Description: URL of the content for this resource, expectation is these are served from an object store
--     * Slot: format Description: The file format of the resource object
--     * Slot: media_type Description: MIME type (e.g., text/markdown, video/mp4) of the resource's content
--     * Slot: created Description: The date on which the entity was created.
--     * Slot: modified Description: The date on which the entity was updated.
--     * Slot: creator
--     * Slot: theme Description: Resource is releated to some topic, subject, concept defined in the life business knowledge taxonomy
--     * Slot: subject
--     * Slot: has_purpose Description: Resource is the designated $X of $Y
--     * Slot: catalog Description: The Catalog the resource belongs to
--     * Slot: Self_id Description: Autocreated FK slot
-- # Class: Topic_aliases
--     * Slot: Topic_id Description: Autocreated FK slot
--     * Slot: aliases Description: Alternative names (SKOS altLabel)
-- # Class: Resource_related_topics
--     * Slot: Resource_id Description: Autocreated FK slot
--     * Slot: related_topics_id
-- # Class: Resource_related_resources
--     * Slot: Resource_id Description: Autocreated FK slot
--     * Slot: related_resources_id
-- # Class: Resource_has_use
--     * Slot: Resource_id Description: Autocreated FK slot
--     * Slot: has_use_id Description: Resource is part of an ongoing effort or activity on the life business
-- # Class: Collection_has_resources
--     * Slot: Collection_id Description: Autocreated FK slot
--     * Slot: has_resources_id Description: A collection of related resources
-- # Class: Collection_related_topics
--     * Slot: Collection_id Description: Autocreated FK slot
--     * Slot: related_topics_id
-- # Class: Collection_related_resources
--     * Slot: Collection_id Description: Autocreated FK slot
--     * Slot: related_resources_id
-- # Class: Collection_has_use
--     * Slot: Collection_id Description: Autocreated FK slot
--     * Slot: has_use_id Description: Resource is part of an ongoing effort or activity on the life business
-- # Class: Catalog_themes
--     * Slot: Catalog_id Description: Autocreated FK slot
--     * Slot: themes_id
-- # Class: Note_related_topics
--     * Slot: Note_id Description: Autocreated FK slot
--     * Slot: related_topics_id
-- # Class: Note_related_resources
--     * Slot: Note_id Description: Autocreated FK slot
--     * Slot: related_resources_id
-- # Class: Note_has_use
--     * Slot: Note_id Description: Autocreated FK slot
--     * Slot: has_use_id Description: Resource is part of an ongoing effort or activity on the life business
-- # Class: Document_related_topics
--     * Slot: Document_id Description: Autocreated FK slot
--     * Slot: related_topics_id
-- # Class: Document_related_resources
--     * Slot: Document_id Description: Autocreated FK slot
--     * Slot: related_resources_id
-- # Class: Document_has_use
--     * Slot: Document_id Description: Autocreated FK slot
--     * Slot: has_use_id Description: Resource is part of an ongoing effort or activity on the life business
-- # Class: Bookmark_highlights
--     * Slot: Bookmark_id Description: Autocreated FK slot
--     * Slot: highlights_id
-- # Class: Bookmark_related_topics
--     * Slot: Bookmark_id Description: Autocreated FK slot
--     * Slot: related_topics_id
-- # Class: Bookmark_related_resources
--     * Slot: Bookmark_id Description: Autocreated FK slot
--     * Slot: related_resources_id
-- # Class: Bookmark_has_use
--     * Slot: Bookmark_id Description: Autocreated FK slot
--     * Slot: has_use_id Description: Resource is part of an ongoing effort or activity on the life business
-- # Class: Highlight_related_topics
--     * Slot: Highlight_id Description: Autocreated FK slot
--     * Slot: related_topics_id
-- # Class: Highlight_related_resources
--     * Slot: Highlight_id Description: Autocreated FK slot
--     * Slot: related_resources_id
-- # Class: Highlight_has_use
--     * Slot: Highlight_id Description: Autocreated FK slot
--     * Slot: has_use_id Description: Resource is part of an ongoing effort or activity on the life business

CREATE TABLE "Self" (
	id INTEGER NOT NULL,
	PRIMARY KEY (id)
);CREATE INDEX "ix_Self_id" ON "Self" (id);
CREATE TABLE "Experiment" (
	id TEXT NOT NULL,
	title TEXT NOT NULL,
	description TEXT,
	created_by TEXT,
	created_on TEXT,
	last_updated_on TEXT,
	url TEXT,
	activity_type TEXT,
	PRIMARY KEY (id)
);CREATE INDEX "ix_Experiment_id" ON "Experiment" (id);
CREATE TABLE "Research" (
	id TEXT NOT NULL,
	title TEXT NOT NULL,
	description TEXT,
	created_by TEXT,
	created_on TEXT,
	last_updated_on TEXT,
	url TEXT,
	activity_type TEXT,
	PRIMARY KEY (id)
);CREATE INDEX "ix_Research_id" ON "Research" (id);
CREATE TABLE "Study" (
	id TEXT NOT NULL,
	title TEXT NOT NULL,
	description TEXT,
	created_by TEXT,
	created_on TEXT,
	last_updated_on TEXT,
	url TEXT,
	activity_type TEXT,
	PRIMARY KEY (id)
);CREATE INDEX "ix_Study_id" ON "Study" (id);
CREATE TABLE "Thinking" (
	id TEXT NOT NULL,
	title TEXT NOT NULL,
	description TEXT,
	created_by TEXT,
	created_on TEXT,
	last_updated_on TEXT,
	url TEXT,
	activity_type TEXT,
	PRIMARY KEY (id)
);CREATE INDEX "ix_Thinking_id" ON "Thinking" (id);
CREATE TABLE "Task" (
	id TEXT NOT NULL,
	title TEXT NOT NULL,
	description TEXT,
	created_by TEXT,
	created_on TEXT,
	last_updated_on TEXT,
	url TEXT,
	activity_type TEXT,
	PRIMARY KEY (id)
);CREATE INDEX "ix_Task_id" ON "Task" (id);
CREATE TABLE "Project" (
	id TEXT NOT NULL,
	title TEXT NOT NULL,
	description TEXT,
	created_by TEXT,
	created_on TEXT,
	last_updated_on TEXT,
	url TEXT,
	activity_type TEXT,
	PRIMARY KEY (id)
);CREATE INDEX "ix_Project_id" ON "Project" (id);
CREATE TABLE "Match" (
	id TEXT NOT NULL,
	entity_type TEXT NOT NULL,
	entity_id TEXT NOT NULL,
	external_system TEXT NOT NULL,
	external_id TEXT NOT NULL,
	match_type VARCHAR(13) NOT NULL,
	confidence FLOAT,
	evidence TEXT,
	created_on TEXT,
	PRIMARY KEY (id)
);CREATE INDEX "ix_Match_id" ON "Match" (id);
CREATE TABLE "Activity" (
	id TEXT NOT NULL,
	title TEXT NOT NULL,
	description TEXT,
	created_by TEXT,
	created_on TEXT,
	last_updated_on TEXT,
	url TEXT,
	activity_type TEXT,
	"Self_id" INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY("Self_id") REFERENCES "Self" (id)
);CREATE INDEX "ix_Activity_id" ON "Activity" (id);
CREATE TABLE "TopicTaxonomy" (
	id TEXT NOT NULL,
	title TEXT NOT NULL,
	description TEXT,
	created_by TEXT,
	created_on TEXT,
	last_updated_on TEXT,
	default_language TEXT,
	skos_uri TEXT,
	"Self_id" INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY("Self_id") REFERENCES "Self" (id)
);CREATE INDEX "ix_TopicTaxonomy_id" ON "TopicTaxonomy" (id);
CREATE TABLE "Repository" (
	id TEXT NOT NULL,
	title TEXT NOT NULL,
	description TEXT,
	created_by TEXT,
	created_on TEXT,
	last_updated_on TEXT,
	service_name TEXT NOT NULL,
	"Self_id" INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY("Self_id") REFERENCES "Self" (id)
);CREATE INDEX "ix_Repository_id" ON "Repository" (id);
CREATE TABLE "Catalog" (
	id TEXT NOT NULL,
	title TEXT NOT NULL,
	description TEXT,
	created_by TEXT,
	created_on TEXT,
	last_updated_on TEXT,
	"Self_id" INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY("Self_id") REFERENCES "Self" (id)
);CREATE INDEX "ix_Catalog_id" ON "Catalog" (id);
CREATE TABLE "Topic" (
	id TEXT NOT NULL,
	taxonomy_id TEXT NOT NULL,
	title TEXT NOT NULL,
	slug TEXT,
	description TEXT,
	status VARCHAR(11) NOT NULL,
	external_refs TEXT,
	materialized_path TEXT,
	created_by TEXT,
	created_on TEXT,
	last_updated_on TEXT,
	"Self_id" INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(taxonomy_id) REFERENCES "TopicTaxonomy" (id),
	FOREIGN KEY("Self_id") REFERENCES "Self" (id)
);CREATE INDEX "ix_Topic_id" ON "Topic" (id);
CREATE TABLE "Purpose" (
	id TEXT NOT NULL,
	title TEXT NOT NULL,
	description TEXT,
	created_by TEXT,
	created_on TEXT,
	last_updated_on TEXT,
	meaning TEXT,
	role TEXT,
	"Self_id" INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(meaning) REFERENCES "Activity" (id),
	FOREIGN KEY("Self_id") REFERENCES "Self" (id)
);CREATE INDEX "ix_Purpose_id" ON "Purpose" (id);
CREATE TABLE "TopicEdge" (
	id INTEGER NOT NULL,
	parent_id TEXT NOT NULL,
	child_id TEXT NOT NULL,
	role VARCHAR(11) NOT NULL,
	source TEXT,
	confidence FLOAT,
	created_on TEXT,
	PRIMARY KEY (id),
	FOREIGN KEY(parent_id) REFERENCES "Topic" (id),
	FOREIGN KEY(child_id) REFERENCES "Topic" (id)
);CREATE INDEX "ix_TopicEdge_id" ON "TopicEdge" (id);
CREATE TABLE "TopicClosure" (
	id INTEGER NOT NULL,
	ancestor_id TEXT NOT NULL,
	descendant_id TEXT NOT NULL,
	depth INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(ancestor_id) REFERENCES "Topic" (id),
	FOREIGN KEY(descendant_id) REFERENCES "Topic" (id)
);CREATE INDEX "ix_TopicClosure_id" ON "TopicClosure" (id);
CREATE TABLE "Resource" (
	id TEXT NOT NULL,
	title TEXT NOT NULL,
	description TEXT,
	created_by TEXT,
	created_on TEXT,
	last_updated_on TEXT,
	resource_type TEXT,
	location TEXT,
	content_location TEXT,
	format TEXT,
	media_type TEXT,
	created DATETIME,
	modified DATETIME,
	creator TEXT,
	theme TEXT,
	subject TEXT,
	has_purpose TEXT,
	catalog TEXT NOT NULL,
	repository TEXT,
	"Self_id" INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(theme) REFERENCES "TopicTaxonomy" (id),
	FOREIGN KEY(subject) REFERENCES "Topic" (id),
	FOREIGN KEY(has_purpose) REFERENCES "Purpose" (id),
	FOREIGN KEY(catalog) REFERENCES "Catalog" (id),
	FOREIGN KEY(repository) REFERENCES "Repository" (id),
	FOREIGN KEY("Self_id") REFERENCES "Self" (id)
);CREATE INDEX "ix_Resource_id" ON "Resource" (id);
CREATE TABLE "Collection" (
	id TEXT NOT NULL,
	title TEXT NOT NULL,
	description TEXT,
	created_by TEXT,
	created_on TEXT,
	last_updated_on TEXT,
	catalog TEXT NOT NULL,
	resource_type TEXT,
	location TEXT,
	content_location TEXT,
	format TEXT,
	media_type TEXT,
	created DATETIME,
	modified DATETIME,
	creator TEXT,
	theme TEXT,
	subject TEXT,
	has_purpose TEXT,
	repository TEXT,
	"Self_id" INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(catalog) REFERENCES "Catalog" (id),
	FOREIGN KEY(theme) REFERENCES "TopicTaxonomy" (id),
	FOREIGN KEY(subject) REFERENCES "Topic" (id),
	FOREIGN KEY(has_purpose) REFERENCES "Purpose" (id),
	FOREIGN KEY(repository) REFERENCES "Repository" (id),
	FOREIGN KEY("Self_id") REFERENCES "Self" (id)
);CREATE INDEX "ix_Collection_id" ON "Collection" (id);
CREATE TABLE "Note" (
	id TEXT NOT NULL,
	title TEXT NOT NULL,
	content_location TEXT,
	note_type VARCHAR(9),
	description TEXT,
	created_by TEXT,
	created_on TEXT,
	last_updated_on TEXT,
	resource_type TEXT,
	location TEXT,
	format TEXT,
	media_type TEXT,
	created DATETIME,
	modified DATETIME,
	creator TEXT,
	theme TEXT,
	subject TEXT,
	has_purpose TEXT,
	catalog TEXT NOT NULL,
	repository TEXT NOT NULL,
	"Self_id" INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(theme) REFERENCES "TopicTaxonomy" (id),
	FOREIGN KEY(subject) REFERENCES "Topic" (id),
	FOREIGN KEY(has_purpose) REFERENCES "Purpose" (id),
	FOREIGN KEY(catalog) REFERENCES "Catalog" (id),
	FOREIGN KEY(repository) REFERENCES "Repository" (id),
	FOREIGN KEY("Self_id") REFERENCES "Self" (id)
);CREATE INDEX "ix_Note_id" ON "Note" (id);
CREATE TABLE "Document" (
	id TEXT NOT NULL,
	title TEXT NOT NULL,
	content_location TEXT,
	document_type VARCHAR(9),
	description TEXT,
	created_by TEXT,
	created_on TEXT,
	last_updated_on TEXT,
	resource_type TEXT,
	location TEXT,
	format TEXT,
	media_type TEXT,
	created DATETIME,
	modified DATETIME,
	creator TEXT,
	theme TEXT,
	subject TEXT,
	has_purpose TEXT,
	catalog TEXT NOT NULL,
	repository TEXT NOT NULL,
	"Self_id" INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(theme) REFERENCES "TopicTaxonomy" (id),
	FOREIGN KEY(subject) REFERENCES "Topic" (id),
	FOREIGN KEY(has_purpose) REFERENCES "Purpose" (id),
	FOREIGN KEY(catalog) REFERENCES "Catalog" (id),
	FOREIGN KEY(repository) REFERENCES "Repository" (id),
	FOREIGN KEY("Self_id") REFERENCES "Self" (id)
);CREATE INDEX "ix_Document_id" ON "Document" (id);
CREATE TABLE "Bookmark" (
	id TEXT NOT NULL,
	title TEXT NOT NULL,
	repository TEXT,
	description TEXT,
	created_by TEXT,
	created_on TEXT,
	last_updated_on TEXT,
	resource_type TEXT,
	location TEXT,
	content_location TEXT,
	format TEXT,
	media_type TEXT,
	created DATETIME,
	modified DATETIME,
	creator TEXT,
	theme TEXT,
	subject TEXT,
	has_purpose TEXT,
	catalog TEXT NOT NULL,
	"Self_id" INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(repository) REFERENCES "Repository" (id),
	FOREIGN KEY(theme) REFERENCES "TopicTaxonomy" (id),
	FOREIGN KEY(subject) REFERENCES "Topic" (id),
	FOREIGN KEY(has_purpose) REFERENCES "Purpose" (id),
	FOREIGN KEY(catalog) REFERENCES "Catalog" (id),
	FOREIGN KEY("Self_id") REFERENCES "Self" (id)
);CREATE INDEX "ix_Bookmark_id" ON "Bookmark" (id);
CREATE TABLE "Topic_aliases" (
	"Topic_id" TEXT,
	aliases TEXT,
	PRIMARY KEY ("Topic_id", aliases),
	FOREIGN KEY("Topic_id") REFERENCES "Topic" (id)
);CREATE INDEX "ix_Topic_aliases_aliases" ON "Topic_aliases" (aliases);CREATE INDEX "ix_Topic_aliases_Topic_id" ON "Topic_aliases" ("Topic_id");
CREATE TABLE "Catalog_themes" (
	"Catalog_id" TEXT,
	themes_id TEXT,
	PRIMARY KEY ("Catalog_id", themes_id),
	FOREIGN KEY("Catalog_id") REFERENCES "Catalog" (id),
	FOREIGN KEY(themes_id) REFERENCES "Topic" (id)
);CREATE INDEX "ix_Catalog_themes_themes_id" ON "Catalog_themes" (themes_id);CREATE INDEX "ix_Catalog_themes_Catalog_id" ON "Catalog_themes" ("Catalog_id");
CREATE TABLE "Highlight" (
	id TEXT NOT NULL,
	title TEXT NOT NULL,
	repository TEXT,
	description TEXT,
	created_by TEXT,
	created_on TEXT,
	last_updated_on TEXT,
	bookmark TEXT,
	resource_type TEXT,
	location TEXT,
	content_location TEXT,
	format TEXT,
	media_type TEXT,
	created DATETIME,
	modified DATETIME,
	creator TEXT,
	theme TEXT,
	subject TEXT,
	has_purpose TEXT,
	catalog TEXT NOT NULL,
	"Self_id" INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(repository) REFERENCES "Repository" (id),
	FOREIGN KEY(bookmark) REFERENCES "Bookmark" (id),
	FOREIGN KEY(theme) REFERENCES "TopicTaxonomy" (id),
	FOREIGN KEY(subject) REFERENCES "Topic" (id),
	FOREIGN KEY(has_purpose) REFERENCES "Purpose" (id),
	FOREIGN KEY(catalog) REFERENCES "Catalog" (id),
	FOREIGN KEY("Self_id") REFERENCES "Self" (id)
);CREATE INDEX "ix_Highlight_id" ON "Highlight" (id);
CREATE TABLE "Resource_related_topics" (
	"Resource_id" TEXT,
	related_topics_id TEXT,
	PRIMARY KEY ("Resource_id", related_topics_id),
	FOREIGN KEY("Resource_id") REFERENCES "Resource" (id),
	FOREIGN KEY(related_topics_id) REFERENCES "Topic" (id)
);CREATE INDEX "ix_Resource_related_topics_related_topics_id" ON "Resource_related_topics" (related_topics_id);CREATE INDEX "ix_Resource_related_topics_Resource_id" ON "Resource_related_topics" ("Resource_id");
CREATE TABLE "Resource_related_resources" (
	"Resource_id" TEXT,
	related_resources_id TEXT,
	PRIMARY KEY ("Resource_id", related_resources_id),
	FOREIGN KEY("Resource_id") REFERENCES "Resource" (id),
	FOREIGN KEY(related_resources_id) REFERENCES "Resource" (id)
);CREATE INDEX "ix_Resource_related_resources_related_resources_id" ON "Resource_related_resources" (related_resources_id);CREATE INDEX "ix_Resource_related_resources_Resource_id" ON "Resource_related_resources" ("Resource_id");
CREATE TABLE "Resource_has_use" (
	"Resource_id" TEXT,
	has_use_id TEXT,
	PRIMARY KEY ("Resource_id", has_use_id),
	FOREIGN KEY("Resource_id") REFERENCES "Resource" (id),
	FOREIGN KEY(has_use_id) REFERENCES "Activity" (id)
);CREATE INDEX "ix_Resource_has_use_has_use_id" ON "Resource_has_use" (has_use_id);CREATE INDEX "ix_Resource_has_use_Resource_id" ON "Resource_has_use" ("Resource_id");
CREATE TABLE "Collection_has_resources" (
	"Collection_id" TEXT,
	has_resources_id TEXT,
	PRIMARY KEY ("Collection_id", has_resources_id),
	FOREIGN KEY("Collection_id") REFERENCES "Collection" (id),
	FOREIGN KEY(has_resources_id) REFERENCES "Resource" (id)
);CREATE INDEX "ix_Collection_has_resources_has_resources_id" ON "Collection_has_resources" (has_resources_id);CREATE INDEX "ix_Collection_has_resources_Collection_id" ON "Collection_has_resources" ("Collection_id");
CREATE TABLE "Collection_related_topics" (
	"Collection_id" TEXT,
	related_topics_id TEXT,
	PRIMARY KEY ("Collection_id", related_topics_id),
	FOREIGN KEY("Collection_id") REFERENCES "Collection" (id),
	FOREIGN KEY(related_topics_id) REFERENCES "Topic" (id)
);CREATE INDEX "ix_Collection_related_topics_related_topics_id" ON "Collection_related_topics" (related_topics_id);CREATE INDEX "ix_Collection_related_topics_Collection_id" ON "Collection_related_topics" ("Collection_id");
CREATE TABLE "Collection_related_resources" (
	"Collection_id" TEXT,
	related_resources_id TEXT,
	PRIMARY KEY ("Collection_id", related_resources_id),
	FOREIGN KEY("Collection_id") REFERENCES "Collection" (id),
	FOREIGN KEY(related_resources_id) REFERENCES "Resource" (id)
);CREATE INDEX "ix_Collection_related_resources_related_resources_id" ON "Collection_related_resources" (related_resources_id);CREATE INDEX "ix_Collection_related_resources_Collection_id" ON "Collection_related_resources" ("Collection_id");
CREATE TABLE "Collection_has_use" (
	"Collection_id" TEXT,
	has_use_id TEXT NOT NULL,
	PRIMARY KEY ("Collection_id", has_use_id),
	FOREIGN KEY("Collection_id") REFERENCES "Collection" (id),
	FOREIGN KEY(has_use_id) REFERENCES "Activity" (id)
);CREATE INDEX "ix_Collection_has_use_Collection_id" ON "Collection_has_use" ("Collection_id");CREATE INDEX "ix_Collection_has_use_has_use_id" ON "Collection_has_use" (has_use_id);
CREATE TABLE "Note_related_topics" (
	"Note_id" TEXT,
	related_topics_id TEXT,
	PRIMARY KEY ("Note_id", related_topics_id),
	FOREIGN KEY("Note_id") REFERENCES "Note" (id),
	FOREIGN KEY(related_topics_id) REFERENCES "Topic" (id)
);CREATE INDEX "ix_Note_related_topics_related_topics_id" ON "Note_related_topics" (related_topics_id);CREATE INDEX "ix_Note_related_topics_Note_id" ON "Note_related_topics" ("Note_id");
CREATE TABLE "Note_related_resources" (
	"Note_id" TEXT,
	related_resources_id TEXT,
	PRIMARY KEY ("Note_id", related_resources_id),
	FOREIGN KEY("Note_id") REFERENCES "Note" (id),
	FOREIGN KEY(related_resources_id) REFERENCES "Resource" (id)
);CREATE INDEX "ix_Note_related_resources_related_resources_id" ON "Note_related_resources" (related_resources_id);CREATE INDEX "ix_Note_related_resources_Note_id" ON "Note_related_resources" ("Note_id");
CREATE TABLE "Note_has_use" (
	"Note_id" TEXT,
	has_use_id TEXT,
	PRIMARY KEY ("Note_id", has_use_id),
	FOREIGN KEY("Note_id") REFERENCES "Note" (id),
	FOREIGN KEY(has_use_id) REFERENCES "Activity" (id)
);CREATE INDEX "ix_Note_has_use_Note_id" ON "Note_has_use" ("Note_id");CREATE INDEX "ix_Note_has_use_has_use_id" ON "Note_has_use" (has_use_id);
CREATE TABLE "Document_related_topics" (
	"Document_id" TEXT,
	related_topics_id TEXT,
	PRIMARY KEY ("Document_id", related_topics_id),
	FOREIGN KEY("Document_id") REFERENCES "Document" (id),
	FOREIGN KEY(related_topics_id) REFERENCES "Topic" (id)
);CREATE INDEX "ix_Document_related_topics_related_topics_id" ON "Document_related_topics" (related_topics_id);CREATE INDEX "ix_Document_related_topics_Document_id" ON "Document_related_topics" ("Document_id");
CREATE TABLE "Document_related_resources" (
	"Document_id" TEXT,
	related_resources_id TEXT,
	PRIMARY KEY ("Document_id", related_resources_id),
	FOREIGN KEY("Document_id") REFERENCES "Document" (id),
	FOREIGN KEY(related_resources_id) REFERENCES "Resource" (id)
);CREATE INDEX "ix_Document_related_resources_related_resources_id" ON "Document_related_resources" (related_resources_id);CREATE INDEX "ix_Document_related_resources_Document_id" ON "Document_related_resources" ("Document_id");
CREATE TABLE "Document_has_use" (
	"Document_id" TEXT,
	has_use_id TEXT,
	PRIMARY KEY ("Document_id", has_use_id),
	FOREIGN KEY("Document_id") REFERENCES "Document" (id),
	FOREIGN KEY(has_use_id) REFERENCES "Activity" (id)
);CREATE INDEX "ix_Document_has_use_has_use_id" ON "Document_has_use" (has_use_id);CREATE INDEX "ix_Document_has_use_Document_id" ON "Document_has_use" ("Document_id");
CREATE TABLE "Bookmark_related_topics" (
	"Bookmark_id" TEXT,
	related_topics_id TEXT,
	PRIMARY KEY ("Bookmark_id", related_topics_id),
	FOREIGN KEY("Bookmark_id") REFERENCES "Bookmark" (id),
	FOREIGN KEY(related_topics_id) REFERENCES "Topic" (id)
);CREATE INDEX "ix_Bookmark_related_topics_related_topics_id" ON "Bookmark_related_topics" (related_topics_id);CREATE INDEX "ix_Bookmark_related_topics_Bookmark_id" ON "Bookmark_related_topics" ("Bookmark_id");
CREATE TABLE "Bookmark_related_resources" (
	"Bookmark_id" TEXT,
	related_resources_id TEXT,
	PRIMARY KEY ("Bookmark_id", related_resources_id),
	FOREIGN KEY("Bookmark_id") REFERENCES "Bookmark" (id),
	FOREIGN KEY(related_resources_id) REFERENCES "Resource" (id)
);CREATE INDEX "ix_Bookmark_related_resources_related_resources_id" ON "Bookmark_related_resources" (related_resources_id);CREATE INDEX "ix_Bookmark_related_resources_Bookmark_id" ON "Bookmark_related_resources" ("Bookmark_id");
CREATE TABLE "Bookmark_has_use" (
	"Bookmark_id" TEXT,
	has_use_id TEXT,
	PRIMARY KEY ("Bookmark_id", has_use_id),
	FOREIGN KEY("Bookmark_id") REFERENCES "Bookmark" (id),
	FOREIGN KEY(has_use_id) REFERENCES "Activity" (id)
);CREATE INDEX "ix_Bookmark_has_use_Bookmark_id" ON "Bookmark_has_use" ("Bookmark_id");CREATE INDEX "ix_Bookmark_has_use_has_use_id" ON "Bookmark_has_use" (has_use_id);
CREATE TABLE "Bookmark_highlights" (
	"Bookmark_id" TEXT,
	highlights_id TEXT,
	PRIMARY KEY ("Bookmark_id", highlights_id),
	FOREIGN KEY("Bookmark_id") REFERENCES "Bookmark" (id),
	FOREIGN KEY(highlights_id) REFERENCES "Highlight" (id)
);CREATE INDEX "ix_Bookmark_highlights_highlights_id" ON "Bookmark_highlights" (highlights_id);CREATE INDEX "ix_Bookmark_highlights_Bookmark_id" ON "Bookmark_highlights" ("Bookmark_id");
CREATE TABLE "Highlight_related_topics" (
	"Highlight_id" TEXT,
	related_topics_id TEXT,
	PRIMARY KEY ("Highlight_id", related_topics_id),
	FOREIGN KEY("Highlight_id") REFERENCES "Highlight" (id),
	FOREIGN KEY(related_topics_id) REFERENCES "Topic" (id)
);CREATE INDEX "ix_Highlight_related_topics_related_topics_id" ON "Highlight_related_topics" (related_topics_id);CREATE INDEX "ix_Highlight_related_topics_Highlight_id" ON "Highlight_related_topics" ("Highlight_id");
CREATE TABLE "Highlight_related_resources" (
	"Highlight_id" TEXT,
	related_resources_id TEXT,
	PRIMARY KEY ("Highlight_id", related_resources_id),
	FOREIGN KEY("Highlight_id") REFERENCES "Highlight" (id),
	FOREIGN KEY(related_resources_id) REFERENCES "Resource" (id)
);CREATE INDEX "ix_Highlight_related_resources_related_resources_id" ON "Highlight_related_resources" (related_resources_id);CREATE INDEX "ix_Highlight_related_resources_Highlight_id" ON "Highlight_related_resources" ("Highlight_id");
CREATE TABLE "Highlight_has_use" (
	"Highlight_id" TEXT,
	has_use_id TEXT,
	PRIMARY KEY ("Highlight_id", has_use_id),
	FOREIGN KEY("Highlight_id") REFERENCES "Highlight" (id),
	FOREIGN KEY(has_use_id) REFERENCES "Activity" (id)
);CREATE INDEX "ix_Highlight_has_use_Highlight_id" ON "Highlight_has_use" ("Highlight_id");CREATE INDEX "ix_Highlight_has_use_has_use_id" ON "Highlight_has_use" (has_use_id);

