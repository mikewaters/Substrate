"""
Generate Cypher code from linkml instance specifications.
Provenance: Derived-from [AI Risk Atlas](https://github.com/IBM/risk-atlas-nexus/blob/1c1a50e4e2301aab93963fc1dacb969d76f21fb3/src/risk_atlas_nexus/ai_risk_ontology/util/export_cypher.py#L59)
License: Apache License 2.0

Note: This works with the Pydantic variant of the LinkML exporter only, which
constrains our instance file format to use only string relationships (`- ABC-123`).
If we were using dataclasses, the relationships must be valid dictionaries (`- id: ABC:123`).
For this reason, we probably need a converter for our data files, because the pure python
convertter has much better validation than the pydantic one and hence is more approppriate
for data ingress at runtime (whereas the pydantic may be more appropriate for batch).
"""

from os import listdir
from os.path import isfile, join
from pathlib import Path
from typing import Any

from linkml_runtime.linkml_model import SchemaDefinition
from linkml_runtime.loaders import yaml_loader
from linkml_runtime.utils.schemaview import SchemaView
from pydantic import BaseModel

from ontology.domains.schema_models import Self
from ontology.utils import load_yaml_files_to_container

# location of ontology LinkML schema files
SCHEMA_DIR = "src/ontology/domains/schema/"
SCHEMA_FILE = "life-container.yaml"
# location of instance data (YAML)
DATA_DIR = "src/ontology/domains/test_data/"
# cypher destination
OUTPUT_DIR = "export/"

DEBUG = False


def dprint(fstring: str) -> None:
    if DEBUG is True:
        print(fstring)


class GraphEdge:
    label: str
    source_id: str
    source_label: str
    target_id: str
    target_label: str

    def __init__(
        self,
        label: str,
        source_id: str,
        source_label: str,
        target_id: str,
        target_label: str,
    ):
        self.label = label
        self.source_id = source_id
        self.source_label = source_label
        self.target_id = target_id
        self.target_label = target_label

    def __str__(self):
        return f"{self.label}: {self.source_id}/{self.source_label} -> {self.target_id}/{self.target_label}"

    def to_cypher(self) -> str:
        return f'MATCH (src: {self.source_label} {{id: "{self.source_id}"}}) MATCH (dst: {self.target_label} {{id: "{self.target_id}"}}) MERGE (src)-[: {self.label}]->(dst);\n'


class GraphNode:
    label: str
    id: str
    properties: dict
    edges: list[GraphEdge]

    def __init__(
        self,
        entity_id: str,
        label: str,
        properties: dict[str, Any],
        relations: list[GraphEdge],
    ):
        self.label = label
        self.id = entity_id
        self.properties = properties
        self.edges = relations

    def to_cypher(self, with_relations: bool = True) -> str:
        merge_node = "MERGE (node:" + self.label + ' {id: "' + self.id + '"})'
        if self.properties:
            merge_node += (
                " ON CREATE SET node += {"
                + ",".join(
                    f'{key}: "{value}"' for key, value in self.properties.items()
                )
                + "}"
            )
        merge_edges = (
            ";\n" + "".join(edge.to_cypher() for edge in self.edges)
            if with_relations
            else ""
        )
        return merge_node + merge_edges

    def __eq__(self, value):
        if isinstance(value, GraphNode):
            return (value.label == self.label) and (value.id == self.id)
        return False

    def __hash__(self):
        return (self.label + "_" + self.id).__hash__()


def get_linkml_types(schema_view: SchemaView) -> list[str]:
    type_names = list(node.name for node in schema_view.all_types().values())
    type_names.extend(str(node.uri) for node in schema_view.all_types().values())
    return list(set(type_names))


def is_relationship(
    schema_view: SchemaView,
    linkml_class: str,
    linkml_slot: str,
    linkml_types: list[str],
) -> bool:
    class_slots = schema_view.class_induced_slots(linkml_class)
    assert linkml_slot in [slot.name for slot in class_slots], (
        f"{linkml_slot} is not a known slot for class {linkml_class}."
    )
    slot_def = [slot for slot in class_slots if slot.name == linkml_slot].pop()
    if slot_def.range not in linkml_types:
        return True
    return False


def convert_entity_to_graph_node(
    entity: BaseModel, label: str, schema_view: SchemaView, linkml_types: list[str]
) -> list[GraphNode]:
    return_list: list[GraphNode] = []
    # Extract properties, namely slots that have a generic LinkML type as range
    properties = {
        item: entity.__getattribute__(item)
        for item in entity.model_dump(exclude={"id"}).keys()
        if not is_relationship(schema_view, label, item, linkml_types)
        and entity.__getattribute__(item) is not None
    }

    # Extract relationships, namely slots that don't have a generic LinkML type as range
    relations = []
    relation_slots = [
        item
        for item in entity.model_dump(exclude={"id"}).keys()
        if is_relationship(schema_view, label, item, linkml_types)
        and entity.__getattribute__(item) is not None
    ]
    # Retrieve all LinkML slot definitions
    slot_definitions = schema_view.class_induced_slots(label)
    for slot_name in relation_slots:
        slot_definition = [
            item for item in slot_definitions if item.name == slot_name
        ].pop()
        if (
            slot_definition.range == "Any"
            and slot_definition.slot_uri is not None
            and slot_definition.slot_uri.startswith("skos:")
        ):
            dst_label = str(slot_definition.owner)
        else:
            dst_label = str(slot_definition.range)
        if slot_definition.multivalued:
            # slot denotes multiple relationships
            if slot_definition.inlined_as_list:
                # Target node is defined here
                return_list.extend(
                    [
                        GraphNode(
                            item.id,
                            dst_label,
                            {
                                prop_name: item.__getattribute__(prop_name)
                                for prop_name in item.model_dump(exclude={"id"}).keys()
                                if not is_relationship(
                                    schema_view,
                                    dst_label,
                                    prop_name,
                                    linkml_types,
                                )
                                and item.__getattribute__(prop_name) is not None
                            },
                            [],
                        )
                        for item in entity.__getattribute__(slot_name)
                    ]
                )
                relations.extend(
                    [
                        GraphEdge(
                            slot_name,
                            entity.__getattribute__("id"),
                            label,
                            item.id,
                            dst_label,
                        )
                        for item in entity.__getattribute__(slot_name)
                    ]
                )
            else:
                relations.extend(
                    [
                        GraphEdge(
                            slot_name,
                            entity.__getattribute__("id"),
                            label,
                            item,
                            dst_label,
                        )
                        for item in entity.__getattribute__(slot_name)
                    ]
                )
        else:
            relations.append(
                GraphEdge(
                    slot_name,
                    entity.__getattribute__("id"),
                    label,
                    entity.__getattribute__(slot_name),
                    dst_label,
                )
            )
    return_list.append(
        GraphNode(entity.__getattribute__("id"), label, properties, relations)
    )
    return return_list


def export_data_to_cypher(container: Self) -> str:
    file_list = [
        file_name
        for file_name in listdir(SCHEMA_DIR)
        if isfile(join(SCHEMA_DIR, file_name))
    ]
    importmap = {Path(item).stem: SCHEMA_DIR + Path(item).stem for item in file_list}
    model: SchemaDefinition = yaml_loader.load(
        SCHEMA_FILE, SchemaDefinition, base_dir=SCHEMA_DIR
    )  # type:ignore
    schema_view = SchemaView(schema=model, merge_imports=True, importmap=importmap)
    print(model)
    # print(schema_view)
    linkml_types = get_linkml_types(schema_view)
    graph_nodes: list[GraphNode] = []
    for container_slot in schema_view.class_induced_slots("Self"):
        dprint(f"Processing slot {container_slot.name}")
        if container_slot.range not in linkml_types:
            entities = container.__getattribute__(container_slot.name)
            dprint(f"Found {len(entities)} items")
            if not entities:
                continue
            for item in entities:
                dprint(f"-->Processing entity {item}")
                nodes = convert_entity_to_graph_node(
                    item, str(container_slot.range), schema_view, linkml_types
                )
                for node in nodes:
                    dprint(f"-->-->Adding node {node.id}")
                    graph_nodes.append(node)
            # graph_nodes.extend(
            #     [
            #         node
            #         for item in entities
            #         for node in convert_entity_to_graph_node(
            #             item, str(container_slot.range), schema_view, linkml_types
            #         )
            #     ]
            # )
        else:
            dprint(f"Slot {container_slot.name} is a linkML definition; skipping")
    # First pass: Generate Cypher code for creation of the nodes
    cypher_code = ";\n".join(
        [graph_node.to_cypher(with_relations=False) for graph_node in graph_nodes]
    )
    if cypher_code:
        cypher_code += ";\n"

    # Second pass: Generate Cypher code for creation of relations
    for graph_node in graph_nodes:
        if graph_node.edges:
            for edge in graph_node.edges:
                dprint(
                    f"Node {graph_node.id} has {edge.source_id} : {edge.target_id} edge"
                )
            cypher_code += "".join([edge.to_cypher() for edge in graph_node.edges])
        else:
            dprint(f"Node {graph_node.id} has no edges")
    return cypher_code


if __name__ == "__main__":
    ontology = load_yaml_files_to_container(
        [join(DATA_DIR, "container-sample-flat.yaml")], Self
    )  # type:ignore
    # makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_DIR + "ontology.cypher", "w+", encoding="utf-8") as output_file:
        print(export_data_to_cypher(ontology), file=output_file)  # type:ignore
        output_file.close()
