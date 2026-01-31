
## Knowledge Graphs and Linked Data
1. Re-structure ontology data as a Property Graph
2. Perform lookups in external taxonomy stores

### Re-structure the LinkML ontology to be a property graph
References:
- [LinkML Documentation - How to make a property graph schema](https://linkml.io/linkml/howtos/model-property-graphs.html)
See also:
- [Medium - Graphs to Graph Neural Networks: From Fundamentals to Applications — Part 2c: RDF vs. LPG Knowledge Graphs by Isaac Kargar](https://kargarisaac.medium.com/graphs-to-graph-neural-networks-from-fundamentals-to-applications-part-2c-rdf-vs-43f246764e39)
- [LinkML-Store - How to use Neo4J with LinkML-Store documentation](https://linkml.io/linkml-store/how-to/Use-Neo4j.html)
#### Example: AIRO Risk Atlas
Defines GraphEdge and GraphNode classes, serializes Container object members to these and then dumps them to Cypher (for ingest into Neo4j).
Uses the SchemaView to get the introspection
[IBM - export_cypher.py at 1c1a50e4e2301aab93963fc1dacb969d76f21fb3 (risk-atlas-nexus/src/risk_atlas_nexus/ai_risk_ontology/util)](https://github.com/IBM/risk-atlas-nexus/blob/1c1a50e4e2301aab93963fc1dacb969d76f21fb3/src/risk_atlas_nexus/ai_risk_ontology/util/export_cypher.py#L59)

### Reconcile my schema with public ontologies
Review this heptabase doc: [Finding Ontologies for LifeOS - Journal](https://app.heptabase.com/2f7caf87-d999-4778-8e30-61689601271e/card/aa56a943-0154-4a51-915b-f46c637cd374)

#### Map elements from other PKM systems to our ontology

https://linkml.io/linkml-map/ - LinkML Map is a framework for specifying and executing mappings between data models.
[LinkML - URIs and Mappings Documentation](https://linkml.io/linkml/schemas/uris-and-mappings.html)

On "exact_mappings": [LinkML - Issue #894: *_mappings vs slot_uri and class_uri](https://github.com/linkml/linkml/issues/894)
IOW, use class_uri as it will get put into JSON-LD etc


