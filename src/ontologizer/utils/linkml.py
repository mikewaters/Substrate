import glob
import json
import os
from linkml_runtime.loaders import yaml_loader
from linkml_runtime.utils.yamlutils import YAMLRoot
from owlready2 import Thing
from pydantic import BaseModel


def load_yaml_files_to_container(
    yaml_files: list[str], klass: type[BaseModel]
) -> YAMLRoot | list[YAMLRoot]:
    """Function to load the Self container with data

    Args:
        base_dir: str
        list of YAML file paths

    Returns:
        YAMLRoot instance of the Container class
    """
    yml_items_result = {}
    for yaml_file in yaml_files:
        try:
            yml_items = yaml_loader.load_as_dict(source=yaml_file)
            for ontology_class, instances in yml_items.items():  # pyright:ignore
                yml_items_result.setdefault(ontology_class, []).extend(instances)
        except Exception as e:
            print(f"YAML ignored: {yaml_file}. Failed to load. {e}")

    ontology = yaml_loader.load_any(
        source=yml_items_result,
        target_class=klass,  # type:ignore
    )

    return ontology


def load_yamls_to_container(
    base_dir: str, klass: type[BaseModel]
) -> YAMLRoot | list[YAMLRoot]:
    """Function to load the Self container with data

    Args:
        base_dir: str
        path to a directory YAML files

    Returns:
        YAMLRoot instance of the Container class
    """

    yaml_files = []
    yaml_files.extend(glob.glob(os.path.join(base_dir, "**", "*.yaml"), recursive=True))
    return load_yaml_files_to_container(yaml_files, klass)


def to_jsonld(obj: Thing, context=None, base_iri=None):
    """Convert an Owlready2 Thing instance to JSON-LD format.

    Args:
        context: Optional JSON-LD context to use
        base_iri: Optional base IRI for relative IRIs

    Returns:
        dict: JSON-LD representation of the Thing instance
    """
    if base_iri is None:
        base_iri = obj.namespace.base_iri

    # Default context if none provided
    if context is None:
        context = {"@vocab": base_iri}

    # Start with the basic structure
    jsonld = {
        "@context": context,
        "@id": obj.iri,
        "@type": obj.__class__.__name__,
    }

    # Add properties
    for prop in obj.get_properties():
        prop_name = prop.name
        values = list(prop[obj])

        if not values:
            continue

        # Handle different value types
        processed_values = []
        for value in values:
            if isinstance(value, Thing):
                # Reference to another object
                processed_values.append({"@id": value.iri})
            elif hasattr(value, "datatype") and value.datatype:
                # Typed literal
                processed_values.append(
                    {"@value": str(value), "@type": value.datatype.iri}
                )
            else:
                # Plain value
                processed_values.append(value)

        # Add single value directly, list for multiple values
        if len(processed_values) == 1:
            jsonld[prop_name] = processed_values[0]
        else:
            jsonld[prop_name] = processed_values

    return jsonld


def save_jsonld(thing, filename, context=None, base_iri=None, indent=2):
    """Save an Owlready2 Thing instance as a JSON-LD file.

    Args:
        thing: The Owlready2 Thing instance to convert
        filename: The output filename
        context: Optional JSON-LD context
        base_iri: Optional base IRI
        indent: JSON indentation level
    """
    jsonld_data = thing.to_jsonld(context=context, base_iri=base_iri)
    with open(filename, "w") as f:
        json.dump(jsonld_data, f, indent=indent)
