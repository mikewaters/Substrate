#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "typer",
#   "rich",
#   "rdflib",
#   "requests"
# ]
# ///
#!/usr/bin/env python3
"""
RDF Entity Details Retriever

This script fetches and displays details about RDF entities from their namespaces.
It supports common RDF vocabularies like RDF, RDFS, OWL, FOAF, DC, and XSD.
"""

from typing import Annotated, Any

import requests
import typer
from rdflib import Graph, URIRef
from rdflib.namespace import DC, DCTERMS, RDF, RDFS
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

app = typer.Typer(
    help="Retrieve and display details about RDF entities from their vocabularies.",
    add_completion=False,
)
console = Console()


# Common RDF prefixes
COMMON_PREFIXES = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "dcmitype": "http://purl.org/dc/dcmitype/",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "schema": "http://schema.org/",
    "dbo": "http://dbpedia.org/ontology/",
    "dbr": "http://dbpedia.org/resource/",
    "prov": "http://www.w3.org/ns/prov#",
    "dcat": "http://www.w3.org/ns/dcat#",
    "void": "http://rdfs.org/ns/void#",
    "linkml": "https://w3id.org/linkml/",
}


class RDFEntityRetriever:
    """Retrieves and parses RDF entity information from vocabularies."""

    def __init__(self):
        self.graph = Graph()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/rdf+xml, text/turtle, application/n-triples, text/n3",
                "User-Agent": "RDF-Entity-Retriever/1.0",
            }
        )

    def fetch_vocabulary(self, namespace_uri: str) -> bool:
        """
        Fetch and parse an RDF vocabulary from a namespace URI.

        Args:
            namespace_uri: The base URI of the RDF namespace

        Returns:
            True if successfully fetched and parsed, False otherwise
        """
        try:
            console.print(f"[cyan]Fetching vocabulary from:[/cyan] {namespace_uri}")

            response = self.session.get(namespace_uri, timeout=10)
            response.raise_for_status()

            # Try to determine content type
            content_type = response.headers.get("Content-Type", "").lower()

            # Parse based on content type
            if "xml" in content_type or "rdf" in content_type:
                self.graph.parse(data=response.text, format="xml")
            elif "turtle" in content_type or "ttl" in content_type:
                self.graph.parse(data=response.text, format="turtle")
            elif "n-triples" in content_type:
                self.graph.parse(data=response.text, format="nt")
            else:
                # Try multiple formats
                for fmt in ["xml", "turtle", "nt"]:
                    try:
                        self.graph.parse(data=response.text, format=fmt)
                        break
                    except:  # noqa:E722
                        continue
            # breakpoint()
            console.print(
                f"[green]✓[/green] Successfully loaded {len(self.graph)} triples"
            )
            return True

        except requests.RequestException as e:
            console.print(f"[red]Error fetching vocabulary:[/red] {e}")
            return False
        except Exception as e:
            console.print(f"[red]Error parsing vocabulary:[/red] {e}")
            return False

    def get_entity_details(self, entity_uri: str) -> dict[str, Any]:
        """
        Extract all available details for an RDF entity.

        Args:
            entity_uri: Full URI of the entity

        Returns:
            Dictionary containing entity details
        """
        entity = URIRef(entity_uri)
        details = {
            "uri": entity_uri,
            "labels": [],
            "comments": [],
            "descriptions": [],
            "types": [],
            "domain": [],
            "range": [],
            "subClassOf": [],
            "subPropertyOf": [],
            "seeAlso": [],
            "isDefinedBy": [],
            "properties": [],
        }

        # print(triple)
        # Get all triples where this entity is the subject
        for pred, obj in self.graph.predicate_objects(entity):
            # Filter out non-English text literals
            if hasattr(obj, "language") and not self._is_english(obj):
                continue

            pred_name = self._get_local_name(pred)
            obj_value = self._format_object(obj)

            # Map common predicates to detail fields
            if pred == RDFS.label:
                details["labels"].append(obj_value)
            elif pred == RDFS.comment:
                details["comments"].append(obj_value)
            elif pred == DCTERMS.description or pred == DC.description:
                details["descriptions"].append(obj_value)
            elif pred == RDF.type:
                details["types"].append(obj_value)
            elif pred == RDFS.domain:
                details["domain"].append(obj_value)
            elif pred == RDFS.range:
                details["range"].append(obj_value)
            elif pred == RDFS.subClassOf:
                details["subClassOf"].append(obj_value)
            elif pred == RDFS.subPropertyOf:
                details["subPropertyOf"].append(obj_value)
            elif pred == RDFS.seeAlso:
                details["seeAlso"].append(obj_value)
            elif pred == RDFS.isDefinedBy:
                details["isDefinedBy"].append(obj_value)
            else:
                # Store any other properties
                details["properties"].append(
                    {
                        "predicate": str(pred),
                        "predicate_name": pred_name,
                        "value": obj_value,
                    }
                )

        return details

    def _get_local_name(self, uri: URIRef) -> str:
        """Extract the local name from a URI."""
        uri_str = str(uri)
        if "#" in uri_str:
            return uri_str.split("#")[-1]
        elif "/" in uri_str:
            return uri_str.split("/")[-1]
        return uri_str

    def _format_object(self, obj) -> str:
        """Format an RDF object for display."""
        if isinstance(obj, URIRef):
            return str(obj)
        else:
            return str(obj)

    def _is_english(self, literal) -> bool:
        """
        Check if a literal is in English or has no language tag.

        RDF literals can have language tags like @en, @fr, @de, etc.
        This method returns True for English literals and literals without language tags.

        Args:
            literal: An RDF literal object

        Returns:
            True if the literal is in English or has no language tag, False otherwise
        """
        # If it's not a Literal object, assume it's acceptable
        if not hasattr(literal, "language"):
            return True

        # If no language tag, accept it
        if literal.language is None:
            return True

        # Accept English language tags (en, en-US, en-GB, etc.)
        return literal.language.lower().startswith("en")

    def print_entity_details(self, details: dict[str, Any]):
        """Pretty print entity details using Rich markdown."""
        # Build markdown content
        md_lines = ["# RDF Entity Details", "", f"**URI:** `{details['uri']}`", ""]

        if details["labels"]:
            md_lines.append("## Labels")
            for label in details["labels"]:
                md_lines.append(f"- {label}")
            md_lines.append("")

        if details["types"]:
            md_lines.append("## Types")
            for t in details["types"]:
                md_lines.append(f"- `{t}`")
            md_lines.append("")

        if details["comments"]:
            md_lines.append("## Comments")
            for comment in details["comments"]:
                md_lines.append(f"> {comment}")
                md_lines.append("")

        if details["descriptions"]:
            md_lines.append("## Descriptions")
            for desc in details["descriptions"]:
                md_lines.append(f"> {desc}")
                md_lines.append("")

        if details["domain"]:
            md_lines.append("## Domain")
            for d in details["domain"]:
                md_lines.append(f"- `{d}`")
            md_lines.append("")

        if details["range"]:
            md_lines.append("## Range")
            for r in details["range"]:
                md_lines.append(f"- `{r}`")
            md_lines.append("")

        if details["subClassOf"]:
            md_lines.append("## Subclass Of")
            for sc in details["subClassOf"]:
                md_lines.append(f"- `{sc}`")
            md_lines.append("")

        if details["subPropertyOf"]:
            md_lines.append("## Subproperty Of")
            for sp in details["subPropertyOf"]:
                md_lines.append(f"- `{sp}`")
            md_lines.append("")

        if details["isDefinedBy"]:
            md_lines.append("## Defined By")
            for db in details["isDefinedBy"]:
                md_lines.append(f"- `{db}`")
            md_lines.append("")

        if details["seeAlso"]:
            md_lines.append("## See Also")
            for sa in details["seeAlso"]:
                md_lines.append(f"- `{sa}`")
            md_lines.append("")

        if details["properties"]:
            md_lines.append("## Other Properties")
            for prop in details["properties"]:
                md_lines.append(f"- **{prop['predicate_name']}:** `{prop['value']}`")
            md_lines.append("")

        # Render markdown
        markdown = Markdown("\n".join(md_lines))
        console.print(markdown)


def parse_prefixed_uri(prefixed_uri: str) -> tuple:
    """
    Parse a prefixed URI like 'foaf:Person' into namespace URI and entity name.

    Args:
        prefixed_uri: URI in format 'prefix:localname'

    Returns:
        Tuple of (namespace_uri, entity_name)
    """
    if ":" not in prefixed_uri:
        raise typer.BadParameter(
            f"Invalid prefixed URI format: {prefixed_uri}. Expected format: prefix:entity"
        )

    prefix, entity_name = prefixed_uri.split(":", 1)

    if prefix not in COMMON_PREFIXES:
        raise typer.BadParameter(
            f"Unknown prefix: {prefix}. Use 'list-prefixes' command to see available prefixes."
        )

    return COMMON_PREFIXES[prefix], entity_name


@app.command()
def get(
    entity: Annotated[
        str,
        typer.Argument(
            help="Entity to retrieve (format: 'prefix:entity' or entity name with --prefix option)"
        ),
    ],
    prefix: Annotated[
        str | None,
        typer.Option(
            "--prefix",
            "-p",
            help="RDF prefix or full namespace URI (optional if using prefix:entity format)",
        ),
    ] = None,
):
    """
    Retrieve and display details about an RDF entity.

    Examples:

        rdf-tool get foaf:Person

        rdf-tool get rdf:type

        rdf-tool get Person --prefix foaf

        rdf-tool get type --prefix http://www.w3.org/1999/02/22-rdf-syntax-ns#
    """
    # Parse entity specification
    if prefix is None:
        # Expect format: prefix:entity
        try:
            namespace_uri, entity_name = parse_prefixed_uri(entity)
        except typer.BadParameter as e:
            console.print(f"[red]Error:[/red] {str(e)}")
            raise typer.Exit(1) from None
    else:
        # Format: prefix entity or full_uri entity
        entity_name = entity

        # Resolve prefix to URI if needed
        if prefix in COMMON_PREFIXES:
            namespace_uri = COMMON_PREFIXES[prefix]
        else:
            namespace_uri = prefix

        # Ensure namespace ends with # or /
        if not namespace_uri.endswith("#") and not namespace_uri.endswith("/"):
            namespace_uri += "#"

    # Construct full entity URI
    entity_uri = namespace_uri + entity_name

    # Create retriever and fetch vocabulary
    retriever = RDFEntityRetriever()

    if retriever.fetch_vocabulary(namespace_uri):
        details = retriever.get_entity_details(entity_uri)

        if (
            any(v for k, v in details.items() if k != "uri" and k != "properties")
            or details["properties"]
        ):
            retriever.print_entity_details(details)
        else:
            console.print(
                f"\n[yellow]No details found for entity:[/yellow] {entity_uri}"
            )
            console.print(
                "The entity may not exist in this vocabulary or the vocabulary may not be accessible."
            )
            raise typer.Exit(1)
    else:
        console.print(
            "\n[red]Failed to fetch vocabulary. Please check the namespace URI.[/red]"
        )
        raise typer.Exit(1)


@app.command("list-prefixes")
def list_prefixes():
    """
    List all known RDF prefixes and their namespace URIs.
    """
    table = Table(
        title="Known RDF Prefixes",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )

    table.add_column("Prefix", style="green", no_wrap=True)
    table.add_column("Namespace URI", style="blue")

    for prefix_name, uri in sorted(COMMON_PREFIXES.items()):
        table.add_row(prefix_name, uri)

    console.print()
    console.print(table)
    console.print()


if __name__ == "__main__":
    app()
