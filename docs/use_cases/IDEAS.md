# Ideas file

### Fact, Principle, Document, and Entity from AIRO
https://github.com/IBM/risk-atlas-nexus/blob/1c1a50e4e2301aab93963fc1dacb969d76f21fb3/src/risk_atlas_nexus/ai_risk_ontology/schema/common.yaml#L68C1-L70C32
```
Fact:
  abstract: true
  class_uri: schema:Statement
```
```
Principle:
  description: A representation of values or norms that must be taken into consideration when conducting activities
  class_uri: dpv:Principle
```
### data.world KOS
data.world implements a Knowledge Organization System which resembles a DCAT catalog:

> Semantic model
>
> The Semantic Model is represented by three key files: the Ontology file, the Mappings file, and the Index file.
> The Ontology file includes entities known as Concepts (e.g., customer or order), characteristics of these entities called Attributes (e.g., customer ID, first name, last name), and the Relationships that connect these entities (e.g., an order was made by a customer). These elements are collectively known as CARS.
> The Mappings file links the ontology to specific data sources, such as indicating that customer data is located in the customer table.
> Mappings within the system can be either direct or complex. Direct mappings are straightforward one-to-one correspondences between concepts and data, while complex mappings may involve additional clauses or conditions to specify relationships more intricately.
> The Index file, is a system file, which helps in vectorizing this information, storing it in a specialized knowledge graph vector. It is crucial for the system operation.
> These three files live within a Project.
