# /// script
# dependencies = ["pyyaml"]
# ///
"""Build controlled sub-100-document corpora for search evaluation experiments.

Supports three corpus modes via subcommands:
  curated   - Extract markdown documents from a local Obsidian vault.
  synthetic - Generate synthetic trap documents for specific failure scenarios.
  fixture   - Copy a stable, version-controlled corpus from a fixture path.

All modes emit a canonical output triple:
  corpus.jsonl  - One JSON document per line.
  queries.json  - Query set with expected doc IDs and difficulty metadata.
  README.md     - Corpus description and known failure modes.

Outputs are fully deterministic for a given seed.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import textwrap
from pathlib import Path
from random import Random
from typing import Any


# ---------------------------------------------------------------------------
# Frontmatter parsing (avoid external dep beyond pyyaml)
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split YAML frontmatter from markdown body.

    Returns (frontmatter_dict, body_text).  If no frontmatter is present the
    dict is empty and the full text is returned as the body.
    """
    import yaml

    if not text.startswith("---"):
        return {}, text

    end = text.find("---", 3)
    if end == -1:
        return {}, text

    raw_yaml = text[3:end].strip()
    body = text[end + 3:].strip()

    try:
        fm = yaml.safe_load(raw_yaml)
        if not isinstance(fm, dict):
            fm = {}
    except yaml.YAMLError:
        fm = {}

    return fm, body


def _extract_title(frontmatter: dict[str, Any], body: str, path: Path) -> str:
    """Derive a document title from frontmatter, first heading, or filename."""
    if frontmatter.get("title"):
        return str(frontmatter["title"])

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()

    return path.stem.replace("-", " ").replace("_", " ")


# ---------------------------------------------------------------------------
# Curated corpus
# ---------------------------------------------------------------------------

_SKIP_DIRS = {".obsidian", ".trash", ".git"}


def _collect_vault_md_files(vault_path: Path) -> list[Path]:
    """Recursively collect .md files, skipping dotfiles and excluded dirs."""
    results: list[Path] = []
    for p in sorted(vault_path.rglob("*.md")):
        # Skip files or directories starting with '.'
        parts = p.relative_to(vault_path).parts
        if any(part.startswith(".") for part in parts):
            continue
        if any(part in _SKIP_DIRS for part in parts):
            continue
        results.append(p)
    return results


def build_curated(vault_path: Path, output_dir: Path, max_docs: int, seed: int) -> None:
    """Extract curated markdown documents from a local vault directory.

    Documents are shuffled deterministically using the provided seed and the
    first ``max_docs`` are selected.  Frontmatter and headings are preserved.
    """
    md_files = _collect_vault_md_files(vault_path)
    if not md_files:
        print(f"ERROR: No markdown files found under {vault_path}", file=sys.stderr)
        raise SystemExit(1)

    rng = Random(seed)
    rng.shuffle(md_files)
    selected = md_files[:max_docs]

    output_dir.mkdir(parents=True, exist_ok=True)

    documents: list[dict[str, Any]] = []
    for idx, path in enumerate(selected):
        text = path.read_text(encoding="utf-8", errors="replace")
        frontmatter, body = _parse_frontmatter(text)
        title = _extract_title(frontmatter, body, path)
        doc_id = f"curated-{idx:04d}"
        doc: dict[str, Any] = {
            "doc_id": doc_id,
            "title": title,
            "body": body,
        }
        if frontmatter:
            doc["frontmatter"] = frontmatter
        documents.append(doc)

    _write_corpus_jsonl(output_dir, documents)

    # Build simple queries from curated docs -- one query per document using
    # its title as the query string.  Limited to the first 10 docs.
    queries = []
    for doc in documents[:10]:
        queries.append({
            "query": doc["title"],
            "expected_docs": [doc["doc_id"]],
            "difficulty": "easy",
            "retriever_types": ["bm25", "vector", "hybrid"],
            "notes": f"Title-based lookup for curated doc {doc['doc_id']}.",
        })

    _write_queries_json(
        output_dir,
        queries,
        description=f"Curated corpus of {len(documents)} documents from {vault_path.name} (seed={seed}).",
    )

    _write_readme(
        output_dir,
        intent="Curated extraction from a local Obsidian vault.",
        method=f"Collected {len(md_files)} .md files, shuffled with seed={seed}, selected first {max_docs}.",
        failure_modes=["No specific failure-mode targeting; used for baseline retrieval checks."],
    )

    print(f"Curated corpus: {len(documents)} docs written to {output_dir}")


# ---------------------------------------------------------------------------
# Synthetic corpus
# ---------------------------------------------------------------------------

def build_synthetic(output_dir: Path, seed: int) -> None:
    """Generate synthetic trap documents for targeted retrieval failure testing.

    Produces documents covering four trap categories:
      - heading_trap: Heading matches query but body diverges.
      - exact_match_trap: Documents containing specific identifiers.
      - near_duplicate: Clusters of highly similar documents.
      - metadata_only: Relevance determinable only from frontmatter tags.
    """
    rng = Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    documents: list[dict[str, Any]] = []
    queries: list[dict[str, Any]] = []

    # -- heading_trap -------------------------------------------------------
    heading_traps = _generate_heading_traps(rng)
    documents.extend(heading_traps["docs"])
    queries.extend(heading_traps["queries"])

    # -- exact_match_trap ---------------------------------------------------
    exact_traps = _generate_exact_match_traps(rng)
    documents.extend(exact_traps["docs"])
    queries.extend(exact_traps["queries"])

    # -- near_duplicate -----------------------------------------------------
    near_dupes = _generate_near_duplicates(rng)
    documents.extend(near_dupes["docs"])
    queries.extend(near_dupes["queries"])

    # -- metadata_only ------------------------------------------------------
    meta_docs = _generate_metadata_only(rng)
    documents.extend(meta_docs["docs"])
    queries.extend(meta_docs["queries"])

    _write_corpus_jsonl(output_dir, documents)
    _write_queries_json(
        output_dir,
        queries,
        description=f"Synthetic trap corpus ({len(documents)} docs, seed={seed}).",
    )
    _write_readme(
        output_dir,
        intent="Synthetic corpus targeting known retrieval failure modes.",
        method=f"Procedurally generated with seed={seed}.",
        failure_modes=[
            "heading_trap: heading strongly matches but body diverges.",
            "exact_match_trap: documents with specific identifiers (SKU, ticket ID).",
            "near_duplicate: clusters of near-identical documents.",
            "metadata_only: relevance only determinable from frontmatter tags.",
        ],
    )

    print(f"Synthetic corpus: {len(documents)} docs, {len(queries)} queries written to {output_dir}")


def _generate_heading_traps(rng: Random) -> dict[str, Any]:
    """Create documents where headings match a query but bodies diverge."""
    scenarios = [
        {
            "heading": "Python Performance Optimization",
            "body": (
                "The southern python (Morelia spilota) is a large species of snake found in "
                "Australia and Indonesia. This document covers its habitat preferences, diet "
                "consisting primarily of small mammals, and seasonal behavioral patterns. "
                "Researchers have studied thermoregulation in pythons extensively, noting that "
                "they optimize body heat by basking on sun-warmed rocks in the early morning."
            ),
            "query": "How to optimize Python code performance",
        },
        {
            "heading": "Java Memory Management",
            "body": (
                "The island of Java is home to one of the most complex irrigation systems in "
                "Southeast Asia. Water memory management across rice paddies involves intricate "
                "canal networks maintained by subak cooperatives. Annual rainfall patterns and "
                "volcanic soil composition directly affect water retention and agricultural yield."
            ),
            "query": "Java garbage collection and memory management",
        },
        {
            "heading": "Docker Container Best Practices",
            "body": (
                "Shipping container logistics at the Port of Rotterdam have evolved since the "
                "1960s. Docker systems for loading and unloading freight require careful weight "
                "distribution. Modern container best practices emphasize standardized lashing "
                "techniques and proper ventilation for perishable cargo."
            ),
            "query": "Docker container deployment best practices",
        },
        {
            "heading": "Understanding Rust Ownership",
            "body": (
                "Rust is a common term for iron oxides formed by the reaction of iron and oxygen "
                "in the presence of water or moisture. Ownership of rusty metal structures poses "
                "significant liability concerns. Property owners must understand corrosion "
                "prevention through galvanization, protective coatings, and regular maintenance."
            ),
            "query": "Rust ownership and borrowing explained",
        },
        {
            "heading": "React Component Lifecycle",
            "body": (
                "Chemical reactions proceed through well-defined phases. The lifecycle of a "
                "reactive component in an industrial catalyst bed begins with activation, "
                "proceeds through steady-state conversion, and concludes with deactivation. "
                "Temperature and pressure are the primary factors governing reaction kinetics."
            ),
            "query": "React component lifecycle methods",
        },
    ]

    # Also create legitimate documents that should rank higher
    correct_docs = [
        {
            "heading": "Optimizing Python Applications",
            "body": (
                "Profiling is the first step in Python performance work. Use cProfile or "
                "py-spy to identify hot paths. Common optimizations include using list "
                "comprehensions over loops, leveraging built-in functions like map and filter, "
                "caching with functools.lru_cache, and choosing appropriate data structures. "
                "For CPU-bound tasks consider multiprocessing or Cython extensions."
            ),
        },
        {
            "heading": "JVM Garbage Collection Tuning",
            "body": (
                "The Java Virtual Machine manages memory through generational garbage "
                "collection. Young generation uses copying collectors (G1, ZGC) while old "
                "generation relies on mark-sweep-compact. Key tuning parameters include "
                "-Xms, -Xmx, -XX:MaxGCPauseMillis, and -XX:G1HeapRegionSize. Monitor with "
                "GC logs and tools like VisualVM."
            ),
        },
    ]

    docs: list[dict[str, Any]] = []
    trap_ids: list[str] = []
    correct_ids: list[str] = []

    for i, scenario in enumerate(scenarios):
        doc_id = f"heading-trap-{i:03d}"
        trap_ids.append(doc_id)
        docs.append({
            "doc_id": doc_id,
            "title": scenario["heading"],
            "body": scenario["body"],
        })

    for i, cdoc in enumerate(correct_docs):
        doc_id = f"heading-correct-{i:03d}"
        correct_ids.append(doc_id)
        docs.append({
            "doc_id": doc_id,
            "title": cdoc["heading"],
            "body": cdoc["body"],
        })

    queries = []
    for i, scenario in enumerate(scenarios):
        trap_id = trap_ids[i]
        # Expected docs should be the correct ones, NOT the trap
        expected = [cid for cid in correct_ids]
        queries.append({
            "query": scenario["query"],
            "expected_docs": expected,
            "difficulty": "hard",
            "retriever_types": ["bm25", "vector", "hybrid"],
            "notes": (
                f"Heading trap test. {trap_id} has a deceptive heading; "
                f"correct results should rank higher based on body relevance."
            ),
        })

    return {"docs": docs, "queries": queries}


def _generate_exact_match_traps(rng: Random) -> dict[str, Any]:
    """Create documents with specific identifiers that require exact matching."""
    identifiers = [
        ("PROJ-1234", "project_ticket", "Refactor authentication middleware to support OAuth2 PKCE flow"),
        ("PROJ-5678", "project_ticket", "Add rate limiting to public API endpoints"),
        ("SKU-90210", "product_sku", "Wireless ergonomic keyboard with split layout and tenting"),
        ("SKU-31337", "product_sku", "Ultra-wide 49-inch curved monitor for development workstations"),
        ("INV-2024-0042", "invoice", "Annual infrastructure hosting renewal for production cluster"),
        ("CVE-2024-21762", "security_advisory", "FortiOS out-of-bound write vulnerability in SSL VPN"),
        ("RFC-9420", "standard", "Message Layer Security protocol specification for end-to-end encryption"),
    ]

    docs: list[dict[str, Any]] = []
    queries: list[dict[str, Any]] = []

    for i, (ident, category, description) in enumerate(identifiers):
        doc_id = f"exact-match-{i:03d}"
        body = (
            f"Identifier: {ident}\n"
            f"Category: {category}\n\n"
            f"## Details\n\n"
            f"{description}\n\n"
            f"This item was filed on 2024-{rng.randint(1,12):02d}-{rng.randint(1,28):02d} "
            f"and is currently in active status. Priority level is "
            f"{rng.choice(['low', 'medium', 'high', 'critical'])}.\n\n"
            f"For reference, the canonical identifier for this record is {ident}."
        )
        docs.append({
            "doc_id": doc_id,
            "title": f"{ident}: {description[:60]}",
            "body": body,
            "frontmatter": {"id": ident, "category": category, "status": "active"},
        })

    # Generate queries -- at least 5
    query_specs = [
        ("PROJ-1234", ["exact-match-000"], "Exact ticket ID lookup"),
        ("SKU-90210", ["exact-match-002"], "Exact SKU lookup"),
        ("INV-2024-0042", ["exact-match-004"], "Exact invoice number lookup"),
        ("CVE-2024-21762", ["exact-match-005"], "Exact CVE identifier lookup"),
        ("RFC-9420", ["exact-match-006"], "Exact RFC number lookup"),
        ("What is PROJ-5678 about?", ["exact-match-001"], "Natural language query with embedded ticket ID"),
        ("Find the product with SKU-31337", ["exact-match-003"], "Natural language query with embedded SKU"),
    ]

    for query_text, expected, notes in query_specs:
        queries.append({
            "query": query_text,
            "expected_docs": expected,
            "difficulty": "medium",
            "retriever_types": ["bm25", "hybrid"],
            "notes": notes,
        })

    return {"docs": docs, "queries": queries}


def _generate_near_duplicates(rng: Random) -> dict[str, Any]:
    """Create clusters of near-duplicate documents with small variations."""
    clusters = [
        {
            "topic": "kubernetes_deployment",
            "base_body": (
                "Kubernetes deployments manage the rollout of containerized applications. "
                "A Deployment provides declarative updates for Pods and ReplicaSets. You "
                "describe a desired state in a Deployment and the controller changes the "
                "actual state to match. Common strategies include rolling update and recreate."
            ),
            "variations": [
                ("added detail about rollback",
                 " Use kubectl rollout undo to revert to a previous revision. "
                 "The revision history is controlled by revisionHistoryLimit."),
                ("added health check info",
                 " Always configure readiness and liveness probes. "
                 "Without probes, Kubernetes cannot determine if your application is healthy."),
                ("added scaling note",
                 " Horizontal Pod Autoscaler can automatically adjust the replica count "
                 "based on CPU utilization or custom metrics from the metrics server."),
                ("added resource limits",
                 " Set resource requests and limits for every container. "
                 "This ensures fair scheduling and prevents noisy-neighbor problems on shared nodes."),
            ],
        },
        {
            "topic": "git_branching",
            "base_body": (
                "Git branching allows developers to diverge from the main line of development. "
                "Branches are lightweight pointers to commits. Creating a branch is nearly "
                "instantaneous since Git only needs to write a 41-byte file. Feature branches "
                "isolate work in progress from the stable mainline."
            ),
            "variations": [
                ("added merge strategies",
                 " Git supports several merge strategies: fast-forward, recursive, and octopus. "
                 "Use git merge --no-ff to preserve branch topology in the history graph."),
                ("added rebase workflow",
                 " Rebasing replays commits on top of another base tip. Interactive rebase "
                 "with git rebase -i allows squashing, reordering, and editing commits before merging."),
                ("added naming conventions",
                 " Common branch naming conventions include feature/, bugfix/, hotfix/, and release/ "
                 "prefixes. Consistent naming improves CI/CD pipeline matching and code review routing."),
            ],
        },
    ]

    docs: list[dict[str, Any]] = []
    queries: list[dict[str, Any]] = []

    doc_idx = 0
    for cluster in clusters:
        cluster_ids: list[str] = []

        # Base document
        base_id = f"near-dupe-{doc_idx:03d}"
        cluster_ids.append(base_id)
        docs.append({
            "doc_id": base_id,
            "title": f"{cluster['topic'].replace('_', ' ').title()} Guide",
            "body": cluster["base_body"],
        })
        doc_idx += 1

        # Variations
        for label, extra_text in cluster["variations"]:
            var_id = f"near-dupe-{doc_idx:03d}"
            cluster_ids.append(var_id)
            docs.append({
                "doc_id": var_id,
                "title": f"{cluster['topic'].replace('_', ' ').title()} Guide ({label})",
                "body": cluster["base_body"] + extra_text,
            })
            doc_idx += 1

        # Queries for this cluster
        topic_label = cluster["topic"].replace("_", " ")
        queries.append({
            "query": f"How does {topic_label} work?",
            "expected_docs": cluster_ids,
            "difficulty": "fusion",
            "retriever_types": ["hybrid"],
            "notes": (
                f"Near-duplicate cluster for {topic_label}. All docs are relevant but a "
                f"good retriever should show diversity rather than returning only the most "
                f"similar variant."
            ),
        })
        queries.append({
            "query": cluster["variations"][0][1].split(".")[1].strip() if "." in cluster["variations"][0][1] else topic_label,
            "expected_docs": [cluster_ids[1]],
            "difficulty": "hard",
            "retriever_types": ["bm25", "vector", "hybrid"],
            "notes": f"Specific detail query targeting the first variation in the {topic_label} cluster.",
        })

    # Add more queries to meet the 5-per-type minimum
    queries.append({
        "query": "Kubernetes deployment rollback procedure",
        "expected_docs": ["near-dupe-000", "near-dupe-001"],
        "difficulty": "medium",
        "retriever_types": ["bm25", "vector", "hybrid"],
        "notes": "Targets rollback-specific near-duplicate variant.",
    })
    queries.append({
        "query": "Git branch naming conventions for CI/CD",
        "expected_docs": ["near-dupe-005", "near-dupe-008"],
        "difficulty": "medium",
        "retriever_types": ["bm25", "vector"],
        "notes": "Targets naming conventions variant in git branching cluster.",
    })
    queries.append({
        "query": "container health checks and probes",
        "expected_docs": ["near-dupe-002"],
        "difficulty": "medium",
        "retriever_types": ["vector", "hybrid"],
        "notes": "Targets health-check variant specifically.",
    })

    return {"docs": docs, "queries": queries}


def _generate_metadata_only(rng: Random) -> dict[str, Any]:
    """Create documents whose relevance is only determinable from frontmatter tags."""
    tag_topics = [
        {
            "tags": ["python", "async", "concurrency"],
            "title": "Working with Concurrent Tasks",
            "body": (
                "This document describes patterns for managing multiple tasks that run at "
                "the same time. We explore event loops, coroutines, and synchronization "
                "primitives. The focus is on non-blocking I/O for network-heavy workloads. "
                "Examples include web scraping pipelines and real-time data processing."
            ),
        },
        {
            "tags": ["python", "testing", "pytest"],
            "title": "Automated Quality Assurance Patterns",
            "body": (
                "Ensuring software correctness requires a layered approach to validation. "
                "This guide covers unit checks, integration checks, and property-based "
                "validation. Fixture management, parameterization, and mocking are discussed "
                "in depth with practical examples."
            ),
        },
        {
            "tags": ["devops", "monitoring", "alerting"],
            "title": "System Observability Handbook",
            "body": (
                "Operational visibility into running services requires collecting metrics, "
                "logs, and traces. This handbook covers instrumentation strategies, dashboard "
                "design principles, and incident response workflows. Topics include SLO/SLI "
                "definitions and error budget policies."
            ),
        },
        {
            "tags": ["security", "authentication", "oauth"],
            "title": "Identity Verification Patterns",
            "body": (
                "Verifying user identity in distributed systems involves multiple protocols "
                "and token formats. This document covers bearer tokens, refresh flows, "
                "PKCE extensions, and multi-factor verification. Emphasis is placed on "
                "secure storage of credentials and session management."
            ),
        },
        {
            "tags": ["database", "postgresql", "optimization"],
            "title": "Relational Data Store Tuning",
            "body": (
                "Query performance in relational data stores depends on indexing strategy, "
                "query planning, and configuration parameters. This guide covers EXPLAIN "
                "analysis, index selection, vacuuming, connection pooling, and parameter "
                "tuning for write-heavy and read-heavy workloads."
            ),
        },
        {
            "tags": ["frontend", "accessibility", "aria"],
            "title": "Inclusive Interface Design",
            "body": (
                "Building interfaces that work for all users requires semantic markup, "
                "keyboard navigation support, and screen reader compatibility. This guide "
                "covers roles, states, properties, focus management, and color contrast "
                "requirements across common UI component patterns."
            ),
        },
    ]

    docs: list[dict[str, Any]] = []
    queries: list[dict[str, Any]] = []

    for i, spec in enumerate(tag_topics):
        doc_id = f"meta-only-{i:03d}"
        docs.append({
            "doc_id": doc_id,
            "title": spec["title"],
            "body": spec["body"],
            "frontmatter": {"tags": spec["tags"], "category": spec["tags"][0]},
        })

    # Queries that use tag-specific terminology not present in the body
    query_specs = [
        ("python async concurrency patterns", ["meta-only-000"],
         "Tags mention python/async/concurrency but body avoids those exact terms."),
        ("pytest fixture parameterization", ["meta-only-001"],
         "Body discusses concepts abstractly; only tags reveal pytest relevance."),
        ("devops monitoring and alerting setup", ["meta-only-002"],
         "Body uses generic observability language; tags specify devops/monitoring/alerting."),
        ("oauth authentication flow", ["meta-only-003"],
         "Body discusses identity patterns generically; tags reveal oauth specificity."),
        ("postgresql query optimization", ["meta-only-004"],
         "Body uses generic relational terminology; tags specify postgresql."),
        ("frontend accessibility aria attributes", ["meta-only-005"],
         "Body discusses inclusive design; tags specify frontend/accessibility/aria."),
    ]

    for query_text, expected, notes in query_specs:
        queries.append({
            "query": query_text,
            "expected_docs": expected,
            "difficulty": "hard",
            "retriever_types": ["bm25", "hybrid"],
            "notes": f"Metadata-only relevance test. {notes}",
        })

    return {"docs": docs, "queries": queries}


# ---------------------------------------------------------------------------
# Fixture corpus
# ---------------------------------------------------------------------------

def build_fixture(fixture_path: Path, output_dir: Path) -> None:
    """Copy a stable, version-controlled fixture corpus to the output directory.

    Validates that the fixture path contains the expected canonical files before
    copying.
    """
    if not fixture_path.is_dir():
        print(f"ERROR: Fixture path does not exist or is not a directory: {fixture_path}", file=sys.stderr)
        raise SystemExit(1)

    required_files = ["corpus.jsonl", "queries.json"]
    for fname in required_files:
        if not (fixture_path / fname).exists():
            print(
                f"ERROR: Fixture path missing required file: {fname}",
                file=sys.stderr,
            )
            raise SystemExit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    for item in fixture_path.iterdir():
        dest = output_dir / item.name
        if item.is_file():
            shutil.copy2(item, dest)
        elif item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)

    # Ensure a README exists
    readme = output_dir / "README.md"
    if not readme.exists():
        _write_readme(
            output_dir,
            intent="Fixture corpus copied from version-controlled source.",
            method=f"Copied from {fixture_path}.",
            failure_modes=["See fixture source for documented failure modes."],
        )

    print(f"Fixture corpus copied from {fixture_path} to {output_dir}")


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _write_corpus_jsonl(output_dir: Path, documents: list[dict[str, Any]]) -> None:
    """Write documents to corpus.jsonl, one JSON object per line."""
    path = output_dir / "corpus.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for doc in documents:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")


def _write_queries_json(
    output_dir: Path,
    queries: list[dict[str, Any]],
    description: str,
) -> None:
    """Write query set to queries.json."""
    payload = {
        "version": "1.0",
        "description": description,
        "queries": queries,
    }
    path = output_dir / "queries.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _write_readme(
    output_dir: Path,
    intent: str,
    method: str,
    failure_modes: list[str],
) -> None:
    """Write a brief README.md describing the corpus."""
    modes_text = "\n".join(f"- {m}" for m in failure_modes)
    content = textwrap.dedent(f"""\
        # Corpus

        ## Intent

        {intent}

        ## Generation Method

        {method}

        ## Known Failure Modes Covered

        {modes_text}
    """)
    path = output_dir / "README.md"
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser with subcommands for each corpus mode."""
    parser = argparse.ArgumentParser(
        prog="build_corpus",
        description="Build controlled sub-100-document corpora for search evaluation.",
    )
    subparsers = parser.add_subparsers(dest="mode", required=True, help="Corpus mode")

    # -- curated ------------------------------------------------------------
    curated = subparsers.add_parser(
        "curated",
        help="Extract markdown documents from a local vault directory.",
    )
    curated.add_argument(
        "--vault-path",
        type=Path,
        required=True,
        help="Path to the Obsidian vault or markdown directory.",
    )
    curated.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to write corpus artifacts.",
    )
    curated.add_argument(
        "--max-docs",
        type=int,
        default=50,
        help="Maximum number of documents to include (default: 50).",
    )
    curated.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic selection (default: 42).",
    )

    # -- synthetic ----------------------------------------------------------
    synthetic = subparsers.add_parser(
        "synthetic",
        help="Generate synthetic trap documents for failure scenario testing.",
    )
    synthetic.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to write corpus artifacts.",
    )
    synthetic.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic generation (default: 42).",
    )

    # -- fixture ------------------------------------------------------------
    fixture = subparsers.add_parser(
        "fixture",
        help="Copy a stable, version-controlled corpus from a fixture path.",
    )
    fixture.add_argument(
        "--fixture-path",
        type=Path,
        required=True,
        help="Path to the fixture corpus directory.",
    )
    fixture.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to write corpus artifacts.",
    )

    return parser


def main() -> int:
    """Parse arguments and dispatch to the appropriate corpus builder."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.mode == "curated":
        if not args.vault_path.is_dir():
            print(f"ERROR: Vault path does not exist: {args.vault_path}", file=sys.stderr)
            return 1
        build_curated(args.vault_path, args.output_dir, args.max_docs, args.seed)

    elif args.mode == "synthetic":
        build_synthetic(args.output_dir, args.seed)

    elif args.mode == "fixture":
        build_fixture(args.fixture_path, args.output_dir)

    else:
        parser.print_help()
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
