# Service Method Caller Report

This report details the callers of methods defined in the main service modules, excluding test suites and the CLI module.


---

## `src/ontology/information/services.py`

### `TopicTaxonomyService`

- **`re_parent()`**: No external callers found.
- **`add_topic()`**
    - `src/ontology/information/api.py:L360`
    - `src/ontology/catalog/services.py:L543`
- **`get_topic()`**
    - `src/ontology/catalog/services.py:L564`
    - `src/ontology/information/api.py:L434`
    - `src/ontology/information/api.py:L548`
    - `src/ontology/information/api.py:L581`
    - `src/ontology/information/api.py:L621`
- **`update_topic()`**
    - `src/ontology/information/api.py:L463`
- **`deprecate_topic()`**
    - `src/ontology/information/api.py:L513`
- **`delete_topic()`**
    - `src/ontology/information/api.py:L487`
- **`list_topics_by_taxonomy_identifier()`**
    - `scripts/load-sample-data.py:L82`
- **`list_topics()`**
    - `src/ontology/information/api.py:L402`
- **`find_orphan_topics()`**
    - `src/ontology/information/api.py:L250`
- **`find_multi_parent_topics()`**
    - `src/ontology/information/api.py:L277`
- **`create_edge()`**
    - `src/ontology/loader/loader.py:L277`
    - `src/ontology/catalog/services.py:L547`
    - `src/ontology/information/api.py:L307`
- **`delete_edge()`**
    - `src/ontology/information/api.py:L330`
- **`get_ancestors()`**
    - `src/ontology/information/api.py:L552`
- **`get_descendants()`**
    - `src/ontology/information/api.py:L585`
- **`search_topics()`**
    - `src/ontology/information/api.py:L227`
- **`get_topic_summary()`**
    - `src/ontology/information/api.py:L753`
- **`get_topic_counts_by_taxonomy()`**
    - `src/ontology/information/api.py:L764`
- **`get_recent_topics()`**
    - `src/ontology/information/api.py:L779`
- **`get_topic_overview()`**
    - `src/ontology/information/api.py:L867`
- **`list_topic_overviews()`**
    - `src/ontology/information/api.py:L831`

### `ClassifierService`

- **`suggest_topics()`**
    - `src/ontology/catalog/services.py:L349`
    - `src/ontology/information/api.py:L727`
    - `scripts/load-sample-data.py:L88`

### `TaxonomyService`

- **`create_taxonomy()`**
    - `src/ontology/information/api.py:L83`
- **`get_taxonomy()`**
    - `src/ontology/information/api.py:L130`
- **`get_by_ident()`**
    - `scripts/visualize_ontologies.py:L94`
- **`update_taxonomy()`**
    - `src/ontology/information/api.py:L159`
- **`delete_taxonomy()`**
    - `src/ontology/information/api.py:L186`
- **`list_taxonomies()`**
    - `src/ontology/information/api.py:L106`

### `DocumentClassificationService`

- **`classify_document()`**
    - `src/ontology/catalog/services.py:L410`
    - `src/ontology/information/api.py:L922`
- **`get_classification_history()`**
    - `src/ontology/information/api.py:L958`
- **`submit_feedback()`**
    - `src/ontology/information/api.py:L984`
- **`suggest_new_topics()`**
    - `src/ontology/catalog/services.py:L313`
- **`suggest_parent_topics()`**
    - `src/ontology/information/api.py:L644`

---

## `src/ontology/catalog/services.py`

### `CatalogService`

- **`create()`**
    - `src/ontology/catalog/api.py:L155`
- **`update()`**
    - `src/ontology/catalog/api.py:L236`

### `RepositoryService`

- **`create()`**
    - `src/ontology/catalog/api.py:L289`
- **`update()`**
    - `src/ontology/catalog/api.py:L370`

### `PurposeService`

- **`create()`**
    - `src/ontology/catalog/api.py:L423`
- **`update()`**
    - `src/ontology/catalog/api.py:L504`

### `ResourceService`

- **`create()`**
    - `src/ontology/catalog/api.py:L557`
- **`update()`**
    - `src/ontology/catalog/api.py:L666`
    - `src/ontology/catalog/services.py:L572`

### `NoteTopicSuggestionService`

- **`suggest_topics_for_note()`**
    - `src/ontology/catalog/api.py:L734`
- **`apply_topic_suggestions()`**
    - `src/ontology/catalog/api.py:L771`
