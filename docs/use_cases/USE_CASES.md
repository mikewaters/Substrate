# Ontology Use Cases

## UI: Tabular Topic List
Requires these APIs:
- taxonomies/{taxonomy_id}/topics
List enriched topics for a taxonomy.
Returns paginated topic overviews for a taxonomy, including parent/child
metadata needed for UI rendering (child counts, parent names, etc.).

- topics/{topic_id}
Fetch a single topic overview.
Returns the TopicOverview (topic details plus parents/children metadata) for a single topic.

## Fleshing out Topics
- Populating the system with topics
- Fleshing out the existing topics, parents etc

## Getting Ontology Entities
- Populating Activities

## Resource Processing
- Building the catalog
- Associating a note with relevant topics
- Suggest a theme for a note, to map it to a taxonomy

