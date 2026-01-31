# Topics and Taxonomies in the Knowledge System

## Classification Methodology

### Definitions
- **Taxonomy**: Broad, general category encompassing many related topics (e.g., "Programming", "Food", "Learning")
- **Topic**: Specific, focused area suitable for precise classification (e.g., "Blockchain Implementations", "Op-amps", "HomeAssistant", "Setting up HomeAssistant", "Using HomeAssistant as a Home Automation Platform Integrated with HomeKit").
- Topics are organized in a parent/child hierarchy, for example:
  - "HomeAssistant" is parent of "Setting up HomeAssistant"
  - "HomeAssistant" is parent of "Using HomeAssistant as a Home Automation Platform Integrated with HomeKit"
- Topics can also be organized in a polyhierarchy as well, where a child topic can have multiple parent; for example:
  - "Using HomeAssistant as a Home Automation Platform Integrated with HomeKit" is a child of "HomeAssistant"
  - "Using HomeAssistant as a Home Automation Platform Integrated with HomeKit" is a child of "HomeKit"
  - "Using HomeAssistant as a Home Automation Platform Integrated with HomeKit" is a child of "Home Automation"

## Analysis of Existing Topics

Below please find a data dump from a user's existing Bookmarks Management system, showing the topics that they are interested in. Pay closest attention to the Item columns for an example of real-world topics, and ensure that your design includes support for these.

### Research & Development

| Item | Classification | Best Ontology | Rationale |
|------|----------------|---------------|-----------|
| Research/Terminal File Managers | Topic | CSO | Software tools, file systems |
| Whiteboard/Node Libraries | Topic | - | Broad software category |
| └─ TLDraw | Topic | CSO | Specific graphics library |
| Cannot Allocate Memory | Topic | CSO | System errors, memory management |
| Psychedelic | Topic | - | Spans culture, medicine, research |
| Mold Remediation | Topic | LCSH + MeSH | Environmental health procedures |
| Media Backup | Topic | CSO | Data storage systems |
| Software Architecture | Taxonomy | - | Broad development category |
| └─ Monorepos | Topic | CSO | Version control patterns |

### Core Interest Areas

| Item | Classification | Best Ontology | Coverage Quality |
|------|----------------|---------------|------------------|
| **Blockchain** | Topic | CSO + Wikidata | Comprehensive |
| **ADHD** | Topic | MeSH + Wikidata | Excellent |
| **Cannabis** | Topic | MeSH + LCSH | Good |
| **Home Theater** | Topic | UNSPSC + Schema.org | Excellent |
| **Nootropics** | Topic | MeSH | Good |
| **Wires & Plugs** | Topic | UNSPSC | Excellent |
| **Home Automation** | Topic | CSO + Schema.org | Good |
| └─ HomeAssistant | Topic | CSO | Platform-specific |
| └─ Light/LED Automation | Topic | UNSPSC + CSO | Good |
| **Writing Instruments** | Topic | UNSPSC | Comprehensive |
| **Electronics and Devices** | Taxonomy | - | Broad category |
| └─ Op-amps | Topic | Wikidata + IEEE | Technical depth |
| **Clicky Keyboards** | Topic | Product Ontology | Specific products |

### Projects & Initiatives

| Project | Classification | Best Ontology | Implementation Notes |
|---------|----------------|---------------|---------------------|
| Better Pain Management | Topic | MeSH | Medical procedures/treatments |
| Sawdust Collection | Topic | LCSH | Woodworking practices |
| Bike for big guys | Topic | Product Ontology | Specialized product category |
| Garage Remodel | Topic | LCSH | Construction/renovation |
| AI PKM Slurp | Topic | CSO | Knowledge management AI |
| Soundproof Windows | Topic | UNSPSC | Building materials |
| Spaced Repetition | Topic | LCSH | Learning methodologies |
| Getting my EHR/PHI data | Topic | MeSH + CSO | Health informatics |

### Software & Tools Reference

| Application | Classification | Best Ontology | Domain |
|-------------|----------------|---------------|---------|
| Midjourney | Topic | CSO | AI image generation |
| Roam Research | Topic | CSO | Knowledge management |
| OmniFocus | Topic | CSO | Productivity software |
| OpenAI | Topic | CSO + Wikidata | AI platform |
| Docker | Topic | CSO | Containerization |
| GraphRAG | Topic | CSO | AI/graph algorithms |
| SQLite | Topic | CSO | Database systems |
| Obsidian | Topic | CSO | Note-taking software |

### Consumer Products & Hardware

| Item | Classification | Best Ontology | Product Category |
|------|----------------|---------------|------------------|
| Macbook Pro 2013 | Topic | Product Ontology | Computer hardware |
| Mini-PCs for AI | Topic | Product Ontology + CSO | Specialized computing |
| Split Keyboard | Topic | Product Ontology | Input devices |
| RaspberryPi | Topic | CSO + Product Ontology | SBC platform |
| Jeep Cherokee 2024 | Topic | Product Ontology | Vehicles |
| Wireless Sleep Headphones | Topic | UNSPSC | Audio equipment |
| High End Writing Tools | Topic | UNSPSC | Luxury office supplies |
| Cool T-Shirts | Topic | UNSPSC | Apparel |
| TB4 Docks | Topic | UNSPSC | Computer peripherals |

### Home & Living

| Category | Item | Classification | Best Ontology |
|----------|------|----------------|---------------|
| **HVAC** | HVAC systems | Topic | UNSPSC |
| **Kitchen** | Kitchen Organization | Topic | LCSH |
| **Audio** | Home Audio | Topic | UNSPSC |
| **Furniture** | Custom Furniture | Topic | UNSPSC |
| **Storage** | Outdoor Storage | Topic | LCSH |
| **Windows** | Casement Windows | Topic | UNSPSC |
| **Garden** | Gardening | Taxonomy | - |

### AI & Machine Learning

| Focus Area | Classification | Best Ontology | Specificity |
|------------|----------------|---------------|-------------|
| AI (category) | Taxonomy | - | Broad field |
| └─ Prompts | Topic | CSO | Prompt engineering |
| └─ Capabilities | Topic | CSO | AI capabilities |
| └─ Model specific Usage | Topic | CSO | Model applications |
| AI Application Architecture | Topic | CSO | System design |
| └─ RAG Theory and Practice | Topic | CSO | Retrieval-augmented generation |
| Semantic Search | Topic | CSO | Information retrieval |
| AI Copilots | Topic | CSO | AI assistants |

## Proposed Structure (JSONSchema)
Below please find a rough proposal of what the schema may look like; it roughly models the SKOS (Simple Knowledge Organization System) Ontology, which is an ontology for Taxonomy/Topic relationships. Our model should align with SKOS where possible, but that can be tackled in a future iteration.

```json
{
    "$defs": {
        "Topic": {
            "description": "Some subject, topic, or concept that might be relevant to an information resource. Has parent and children topic within the wider taxonomy",
            "properties": {
                "description": {
                    "type": [
                        "string",
                        "null"
                    ]
                },
                "id": {
                    "description": "Unique identifier for any topic",
                    "type": "string"
                },
                "taxonomy": {
                    "description": "The topic taxonomy this topic is a member of, Analagous to skos:inScheme in the SKOS Simple Knowledge Organization System (RDF)",
                    "type": [
                        "string",
                        "null"
                    ]
                },
                "top_concept_of": {
                    "description": "This topic is a top-most concept in its taxonomy, and it has no parent Topics. Analagous to skos:topConceptOf in the SKOS Simple Knowledge Organization System (RDF)"
                    "type": "bool"
                },
                "parent_topic": {
                  "description": "This topic is a sub-topic of another topic, analogous to skos:narrower in the SKOS Simple Knowledge Organization System (RDF). The value of this field is a reference to another topic object within the taxonomy"
                   "type": "$ref"
                },
                "title": {
                    "type": "string",
                    "description": "The name of the topic"
                }
            },
            "required": [
                "id",
                "title"
            ],
            "title": "Topic",
            "type": "object"
        },
        "TopicTaxonomy": {
            "description": "A taxonomy for categorizing resources in a PKM",
            "properties": {
                "description": {
                    "type": [
                        "string",
                        "null"
                    ]
                },
                "id": {
                    "description": "Unique identifier for a topic taxonomy",
                    "type": "string"
                },
                "title": {
                    "type": "string"
                }
            },
            "required": [
                "id",
                "title"
            ],
            "title": "TopicTaxonomy",
            "type": "object"
        }
    }
}
```
In this JSON Schema, a **Subject** would be represented as a `TopicTaxonomy` object, whilst a **Topic** would be represented by a `Topic` object.
