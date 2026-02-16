"""Search evaluation scenario definitions for the search-improver skill.

Defines four minimum test scenarios as structured dataclasses that can be
consumed by both the corpus builder (build_corpus.py synthetic mode) and the
experiment runner. Each scenario is self-contained with realistic documents,
queries, failure hypotheses, and metric targets.

Scenarios
---------
1. heading_bias     -- Heading-only nodes outrank substantive body content.
2. exact_match      -- Exact identifiers lost by vector embeddings.
3. semantic_para    -- Paraphrased queries fail in BM25.
4. near_duplicate   -- Near-duplicate clusters crowd out diverse results.

Usage as a library::

    from scenarios import ALL_SCENARIOS, build_scenario_corpus

    for s in ALL_SCENARIOS:
        print(s.name, len(s.documents), len(s.queries))

    build_scenario_corpus(Path("output/"), scenarios=ALL_SCENARIOS)

Usage as a CLI::

    python scenarios.py build --output-dir /path/to/output
    python scenarios.py build --output-dir /path/to/output --scenarios heading_bias,exact_match
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Scenario:
    """A search evaluation scenario definition.

    Encapsulates a failure hypothesis, the documents and queries needed to
    test it, the expected retrieval behavior, and concrete metric targets
    keyed by retriever mode.

    Attributes:
        name: Human-readable scenario name.
        slug: Filesystem-safe identifier (used for directory names and filtering).
        failure_hypothesis: Description of the retrieval failure being tested.
        queries: List of query dicts matching the queries.json schema
            (query, expected_docs, difficulty, retriever_types, notes).
        documents: List of document dicts matching the corpus.jsonl schema
            (doc_id, title, body, optional frontmatter).
        metric_targets: Nested dict of {mode: {metric: threshold}}. Modes are
            retriever names (bm25, vector, hybrid). Metrics are strings like
            hit_at_3, heading_dominance_rate, diversity_rate.
        expected_behavior: Prose description of what correct retrieval looks like.
    """

    name: str
    slug: str
    failure_hypothesis: str
    queries: list[dict[str, Any]]
    documents: list[dict[str, Any]]
    metric_targets: dict[str, dict[str, float]]
    expected_behavior: str


# ---------------------------------------------------------------------------
# Scenario 1: Heading Bias Regression
# ---------------------------------------------------------------------------

def heading_bias_scenario() -> Scenario:
    """Build the heading bias regression scenario.

    Tests that short heading-only nodes do not score disproportionately high
    in BM25/FTS, pushing substantive body content out of top results.

    Five queries where a heading matches a keyword but the correct answer
    lives in a longer body-text document. For each query there is one trap
    document (heading matches, body diverges) and one correct document
    (heading may differ but body is substantive and relevant).
    """
    documents: list[dict[str, Any]] = []
    queries: list[dict[str, Any]] = []

    # Each tuple: (trap_heading, trap_body, correct_heading, correct_body, query_text)
    cases = [
        (
            "Database Indexing Strategies",
            (
                "The index finger is the second digit of the human hand. In sign language, "
                "indexing strategies for pointing involve extending the index finger while "
                "curling other digits. Historical database records of hand gesture frequency "
                "show indexing strategies evolved across cultures and centuries."
            ),
            "Improving Query Performance with B-Tree and Hash Indexes",
            (
                "Relational databases rely on indexes to accelerate lookups. A B-tree index "
                "maintains sorted data and allows searches, sequential access, insertions, "
                "and deletions in logarithmic time. Hash indexes provide constant-time "
                "lookups for equality predicates but do not support range queries.\n\n"
                "When choosing an index strategy, consider the query workload. Write-heavy "
                "tables benefit from fewer indexes to reduce write amplification. Read-heavy "
                "analytical queries benefit from composite indexes that cover the most common "
                "filter and sort columns. Partial indexes can reduce storage overhead by "
                "indexing only rows that match a predicate.\n\n"
                "Monitor index usage with pg_stat_user_indexes to identify unused indexes "
                "that waste storage and slow writes without improving read performance."
            ),
            "database indexing strategies for faster queries",
        ),
        (
            "Caching Best Practices",
            (
                "In pottery and ceramics, caching refers to the practice of storing unfired "
                "clay pieces in a cool, humid environment before kiln firing. Best practices "
                "include wrapping pieces in damp cloth, maintaining consistent humidity levels "
                "between 60-70 percent, and avoiding direct sunlight that causes uneven drying "
                "and surface cracking."
            ),
            "Application-Level Caching with Redis and Memcached",
            (
                "Caching is a critical performance optimization for web applications. Redis "
                "and Memcached are the two most widely deployed caching systems.\n\n"
                "Redis offers persistence, replication, and rich data structures including "
                "sorted sets, lists, and streams. It supports cache eviction policies such "
                "as volatile-lru and allkeys-lfu. A typical pattern is cache-aside: the "
                "application checks the cache first, falls back to the database on a miss, "
                "and writes the result back to the cache.\n\n"
                "Memcached is simpler and optimized for raw throughput in multi-threaded "
                "environments. It supports only string keys and values but excels at high "
                "concurrency with consistent hashing for cluster distribution.\n\n"
                "In both systems, choose TTL values carefully. Too short and you lose cache "
                "benefits; too long and you serve stale data."
            ),
            "caching best practices for web applications",
        ),
        (
            "Load Balancing",
            (
                "In structural engineering, load balancing refers to the distribution of "
                "weight across a bridge or building framework. The goal is to ensure that "
                "no single beam or column bears a disproportionate share of the total load. "
                "Techniques include using trusses, cantilevers, and suspension cables. "
                "Finite element analysis software can model load distribution under various "
                "stress conditions and wind patterns."
            ),
            "HTTP Load Balancing Algorithms and Health Checks",
            (
                "Load balancers distribute incoming requests across a pool of backend "
                "servers. Common algorithms include round-robin, least-connections, and "
                "weighted round-robin.\n\n"
                "Layer 4 (TCP) load balancers operate on connection-level metadata and are "
                "faster but less flexible. Layer 7 (HTTP) load balancers can inspect headers, "
                "cookies, and URL paths to make routing decisions. This enables patterns like "
                "sticky sessions and content-based routing.\n\n"
                "Health checks are essential: active health checks send periodic probes to "
                "backends, while passive checks monitor response codes and latencies from "
                "real traffic. Unhealthy backends should be removed from the pool within "
                "seconds to avoid serving errors to users.\n\n"
                "Tools: nginx, HAProxy, AWS ALB, and Envoy are widely used in production."
            ),
            "load balancing algorithms for HTTP traffic",
        ),
        (
            "Message Queue Architecture",
            (
                "In postal systems, a message queue is the physical holding area where "
                "letters and parcels await sorting. Architecture of these facilities has "
                "evolved from simple wooden cubbyholes to automated conveyor systems with "
                "optical character recognition. Modern postal queue architecture emphasizes "
                "throughput optimization and last-mile delivery efficiency."
            ),
            "Designing Reliable Event-Driven Systems with Message Brokers",
            (
                "Message brokers decouple producers from consumers, enabling asynchronous "
                "communication and fault tolerance. Popular brokers include RabbitMQ, Apache "
                "Kafka, and AWS SQS.\n\n"
                "RabbitMQ implements AMQP with exchanges, bindings, and queues. It supports "
                "delivery acknowledgment, dead-letter exchanges, and priority queues. Kafka "
                "is a distributed log that provides high-throughput, fault-tolerant, and "
                "ordered message delivery within partitions.\n\n"
                "Key design decisions include choosing between at-most-once, at-least-once, "
                "and exactly-once delivery semantics. Consumer group management and partition "
                "assignment strategies affect throughput and ordering guarantees.\n\n"
                "Monitor consumer lag to detect slow consumers before they cause backpressure."
            ),
            "message queue architecture patterns",
        ),
        (
            "API Rate Limiting",
            (
                "In amateur radio, the API (Automatic Position Identification) rate limiting "
                "feature controls how frequently a transceiver broadcasts its GPS coordinates "
                "to the APRS network. Rate limiting prevents channel congestion on shared "
                "frequencies. Operators typically configure their devices to beacon every "
                "120 seconds on highways and every 300 seconds in stationary positions."
            ),
            "Implementing Token Bucket and Sliding Window Rate Limiters",
            (
                "Rate limiting protects APIs from abuse and ensures fair resource allocation "
                "across clients. The two most common algorithms are the token bucket and the "
                "sliding window log.\n\n"
                "The token bucket allows bursts up to a configured bucket size, then enforces "
                "a steady refill rate. It is memory-efficient (one counter and one timestamp "
                "per client) and naturally handles bursty traffic patterns.\n\n"
                "The sliding window log tracks individual request timestamps and counts "
                "requests within a rolling window. It provides more precise rate enforcement "
                "but requires more memory as it stores each timestamp.\n\n"
                "Implementations typically use Redis with atomic Lua scripts for distributed "
                "rate limiting. Return HTTP 429 with a Retry-After header when limits are "
                "exceeded. Include X-RateLimit-Remaining and X-RateLimit-Reset headers in "
                "all responses so clients can self-regulate."
            ),
            "API rate limiting implementation approaches",
        ),
    ]

    for i, (trap_h, trap_b, correct_h, correct_b, query_text) in enumerate(cases):
        trap_id = f"hb-trap-{i:03d}"
        correct_id = f"hb-correct-{i:03d}"

        documents.append({
            "doc_id": trap_id,
            "title": trap_h,
            "body": f"# {trap_h}\n\n{trap_b}",
        })
        documents.append({
            "doc_id": correct_id,
            "title": correct_h,
            "body": f"# {correct_h}\n\n{correct_b}",
        })

        queries.append({
            "query": query_text,
            "expected_docs": [correct_id],
            "difficulty": "hard",
            "retriever_types": ["bm25", "vector", "hybrid"],
            "notes": (
                f"Heading bias test. '{trap_h}' matches the query keywords in its heading "
                f"but the body is about an unrelated topic. The correct document "
                f"'{correct_id}' has substantive, relevant body content."
            ),
        })

    return Scenario(
        name="Heading Bias Regression",
        slug="heading_bias",
        failure_hypothesis=(
            "Short heading-only nodes score disproportionately high in BM25/FTS, "
            "pushing substantive body content out of top results."
        ),
        queries=queries,
        documents=documents,
        metric_targets={
            "bm25": {"hit_at_3": 0.80, "heading_dominance_rate": 0.30},
            "vector": {"hit_at_3": 0.80},
            "hybrid": {"hit_at_3": 0.90, "heading_dominance_rate": 0.20},
        },
        expected_behavior=(
            "Body-content documents should rank higher than heading-only matches. "
            "The trap documents have headings that match query keywords but bodies "
            "about completely unrelated topics. A well-tuned retriever should use "
            "body content signals to push the correct documents above the traps."
        ),
    )


# ---------------------------------------------------------------------------
# Scenario 2: Exact-Match Identifiers
# ---------------------------------------------------------------------------

def exact_match_scenario() -> Scenario:
    """Build the exact-match identifiers scenario.

    Tests that specific identifiers (ticket numbers, SKUs, error codes) can
    be reliably retrieved. Vector search may fail because embeddings compress
    symbolic tokens. BM25/FTS should handle these well. Hybrid should still
    find them.
    """
    identifiers = [
        {
            "id": "PROJ-1234",
            "category": "project_ticket",
            "title": "PROJ-1234: Refactor authentication middleware for OAuth2 PKCE",
            "body": (
                "# PROJ-1234: Refactor authentication middleware for OAuth2 PKCE\n\n"
                "## Summary\n\n"
                "The current authentication middleware uses the implicit grant flow, which "
                "is deprecated for public clients. This ticket tracks the migration to the "
                "Authorization Code flow with PKCE (Proof Key for Code Exchange).\n\n"
                "## Acceptance Criteria\n\n"
                "- Replace implicit flow with authorization code + PKCE\n"
                "- Support both S256 and plain challenge methods\n"
                "- Update token refresh logic to use refresh tokens\n"
                "- Add integration tests covering the full OAuth2 handshake\n\n"
                "## Technical Notes\n\n"
                "The PKCE extension generates a code_verifier (random 43-128 character string) "
                "and derives a code_challenge using SHA-256. The authorization server validates "
                "the verifier against the stored challenge during token exchange.\n\n"
                "Priority: high | Assignee: backend-team | Sprint: 2024-Q4"
            ),
        },
        {
            "id": "PROJ-5678",
            "category": "project_ticket",
            "title": "PROJ-5678: Add rate limiting to public API endpoints",
            "body": (
                "# PROJ-5678: Add rate limiting to public API endpoints\n\n"
                "## Summary\n\n"
                "Public API endpoints currently have no rate limiting, leaving us vulnerable "
                "to abuse and denial-of-service attacks. Implement sliding window rate limiting "
                "with configurable per-client thresholds.\n\n"
                "## Requirements\n\n"
                "- Default limit: 100 requests per minute per API key\n"
                "- Premium tier: 1000 requests per minute\n"
                "- Return HTTP 429 with Retry-After header on limit breach\n"
                "- Store counters in Redis with atomic increment operations\n\n"
                "Priority: critical | Assignee: platform-team | Sprint: 2024-Q4"
            ),
        },
        {
            "id": "SKU-90210",
            "category": "product_sku",
            "title": "SKU-90210: Wireless Ergonomic Split Keyboard",
            "body": (
                "# SKU-90210: Wireless Ergonomic Split Keyboard\n\n"
                "## Product Description\n\n"
                "A wireless ergonomic keyboard with a split layout and adjustable tenting "
                "angles from 0 to 15 degrees. Features Cherry MX Brown switches, USB-C "
                "charging, and Bluetooth 5.0 connectivity with up to 3 device pairing.\n\n"
                "## Specifications\n\n"
                "- Layout: Split, ortholinear\n"
                "- Switches: Cherry MX Brown (tactile, non-clicky)\n"
                "- Battery: 4000mAh, approximately 6 weeks per charge\n"
                "- Connectivity: Bluetooth 5.0, USB-C wired mode\n"
                "- Weight: 680g per half\n\n"
                "## Inventory\n\n"
                "Warehouse stock: 342 units | Reorder point: 50 units"
            ),
        },
        {
            "id": "CVE-2024-21762",
            "category": "security_advisory",
            "title": "CVE-2024-21762: FortiOS SSL VPN Out-of-Bound Write",
            "body": (
                "# CVE-2024-21762: FortiOS SSL VPN Out-of-Bound Write\n\n"
                "## Advisory\n\n"
                "An out-of-bound write vulnerability in FortiOS SSL VPN allows a remote "
                "unauthenticated attacker to execute arbitrary code or commands via specially "
                "crafted HTTP requests. CVSS Score: 9.8 (Critical).\n\n"
                "## Affected Versions\n\n"
                "- FortiOS 7.4.0 through 7.4.2\n"
                "- FortiOS 7.2.0 through 7.2.6\n"
                "- FortiOS 7.0.0 through 7.0.13\n\n"
                "## Remediation\n\n"
                "Upgrade to FortiOS 7.4.3 or later. If immediate patching is not possible, "
                "disable SSL VPN as a workaround. Fortinet has confirmed active exploitation "
                "in the wild.\n\n"
                "Published: 2024-02-09 | Last updated: 2024-02-12"
            ),
        },
        {
            "id": "RFC-9420",
            "category": "standard",
            "title": "RFC 9420: The Message Layer Security (MLS) Protocol",
            "body": (
                "# RFC 9420: The Message Layer Security (MLS) Protocol\n\n"
                "## Abstract\n\n"
                "MLS is a protocol for end-to-end encryption of messages in groups of two "
                "or more participants. It provides forward secrecy and post-compromise "
                "security through a tree-based key agreement mechanism called TreeKEM.\n\n"
                "## Key Concepts\n\n"
                "- Ratchet trees for efficient group key management\n"
                "- Proposals and commits for group state transitions\n"
                "- Application messages encrypted under group epoch keys\n"
                "- External joins for adding members without existing member assistance\n\n"
                "## Implementation Notes\n\n"
                "Implementations must support the mandatory-to-implement cipher suite: "
                "MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519. Interoperability testing "
                "is available through the MLS working group test vectors.\n\n"
                "Published: July 2023 | Status: Proposed Standard"
            ),
        },
        {
            "id": "INV-2024-0042",
            "category": "invoice",
            "title": "INV-2024-0042: Annual Infrastructure Hosting Renewal",
            "body": (
                "# INV-2024-0042: Annual Infrastructure Hosting Renewal\n\n"
                "## Invoice Details\n\n"
                "This invoice covers the annual renewal of production infrastructure "
                "hosting services for the period 2024-01-01 through 2024-12-31.\n\n"
                "## Line Items\n\n"
                "- 12x c5.2xlarge reserved instances: $14,400.00\n"
                "- 4x r5.4xlarge reserved instances: $19,200.00\n"
                "- S3 storage (estimated 50TB): $1,150.00\n"
                "- Data transfer (estimated 10TB egress): $900.00\n"
                "- Support plan (Business tier): $4,800.00\n\n"
                "## Total: $40,450.00\n\n"
                "Payment terms: Net 30 | Due date: 2024-01-31"
            ),
        },
        {
            "id": "ERR-E4019",
            "category": "error_code",
            "title": "ERR-E4019: Connection Pool Exhaustion",
            "body": (
                "# ERR-E4019: Connection Pool Exhaustion\n\n"
                "## Description\n\n"
                "Error code ERR-E4019 indicates that all connections in the database "
                "connection pool have been consumed and no connections are available "
                "for new requests. The default pool size is 20 connections.\n\n"
                "## Common Causes\n\n"
                "- Long-running transactions holding connections open\n"
                "- Connection leaks from unclosed cursors or sessions\n"
                "- Sudden traffic spikes exceeding pool capacity\n"
                "- Deadlocks preventing connection release\n\n"
                "## Resolution Steps\n\n"
                "1. Check active connections: SELECT * FROM pg_stat_activity\n"
                "2. Identify long-running queries and terminate if appropriate\n"
                "3. Increase pool_size in configuration (max recommended: 50)\n"
                "4. Add connection timeout settings to prevent indefinite holds\n"
                "5. Review application code for connection leak patterns"
            ),
        },
    ]

    documents = []
    for i, spec in enumerate(identifiers):
        doc_id = f"em-{i:03d}"
        documents.append({
            "doc_id": doc_id,
            "title": spec["title"],
            "body": spec["body"],
            "frontmatter": {
                "id": spec["id"],
                "category": spec["category"],
                "status": "active",
            },
        })

    queries = [
        {
            "query": "PROJ-1234",
            "expected_docs": ["em-000"],
            "difficulty": "easy",
            "retriever_types": ["bm25", "hybrid"],
            "notes": "Bare ticket ID lookup. FTS should match on the literal string.",
        },
        {
            "query": "SKU-90210",
            "expected_docs": ["em-002"],
            "difficulty": "easy",
            "retriever_types": ["bm25", "hybrid"],
            "notes": "Bare SKU lookup. Tests exact identifier matching.",
        },
        {
            "query": "CVE-2024-21762",
            "expected_docs": ["em-003"],
            "difficulty": "easy",
            "retriever_types": ["bm25", "hybrid"],
            "notes": "Bare CVE identifier lookup. Hyphenated numeric pattern.",
        },
        {
            "query": "What is the status of PROJ-5678?",
            "expected_docs": ["em-001"],
            "difficulty": "medium",
            "retriever_types": ["bm25", "vector", "hybrid"],
            "notes": (
                "Natural language query with embedded ticket ID. BM25 should match "
                "on the identifier; vector may match on the semantic context."
            ),
        },
        {
            "query": "Find invoice INV-2024-0042",
            "expected_docs": ["em-005"],
            "difficulty": "easy",
            "retriever_types": ["bm25", "hybrid"],
            "notes": "Invoice number lookup with surrounding natural language.",
        },
        {
            "query": "RFC-9420 MLS protocol",
            "expected_docs": ["em-004"],
            "difficulty": "medium",
            "retriever_types": ["bm25", "vector", "hybrid"],
            "notes": "RFC number with topic keywords. Tests combined identifier + semantic.",
        },
        {
            "query": "error code ERR-E4019 connection pool",
            "expected_docs": ["em-006"],
            "difficulty": "medium",
            "retriever_types": ["bm25", "hybrid"],
            "notes": "Error code with descriptive context. Tests identifier extraction.",
        },
    ]

    return Scenario(
        name="Exact-Match Identifiers",
        slug="exact_match",
        failure_hypothesis=(
            "Vector search cannot reliably retrieve documents by exact identifiers "
            "(ticket numbers, SKUs, error codes) because embeddings compress symbolic "
            "tokens into distributed representations that lose literal string identity."
        ),
        queries=queries,
        documents=documents,
        metric_targets={
            "bm25": {"hit_at_1": 0.85, "mrr_at_10": 0.85},
            "hybrid": {"hit_at_3": 0.70, "mrr_at_10": 0.70},
        },
        expected_behavior=(
            "FTS/BM25 should find identifier-bearing documents reliably since the "
            "identifiers appear as literal substrings. Vector search may fail for "
            "bare identifiers but may succeed when the query includes descriptive "
            "context. Hybrid should combine strengths to find identifiers even when "
            "one channel fails."
        ),
    )


# ---------------------------------------------------------------------------
# Scenario 3: Semantic Paraphrase Retrieval
# ---------------------------------------------------------------------------

def semantic_paraphrase_scenario() -> Scenario:
    """Build the semantic paraphrase retrieval scenario.

    Tests that queries using different vocabulary than documents (paraphrases,
    synonyms) can still retrieve the correct documents. BM25 is expected to
    fail when there is no keyword overlap. Vector search should excel.
    """
    # Each tuple: (doc_title, doc_body, paraphrased_query)
    # The query deliberately avoids the keywords used in the document.
    cases = [
        (
            "Kubernetes Pod Scheduling and Resource Allocation",
            (
                "# Kubernetes Pod Scheduling and Resource Allocation\n\n"
                "The kube-scheduler selects which node an unscheduled pod runs on. It "
                "filters nodes based on resource requests (CPU, memory), node affinity "
                "rules, taints and tolerations, and pod topology spread constraints.\n\n"
                "Resource requests define the minimum resources a container needs. "
                "Limits define the maximum. The scheduler uses requests for placement "
                "decisions. If a container exceeds its memory limit, it is OOM-killed. "
                "If it exceeds its CPU limit, it is throttled.\n\n"
                "Quality of Service classes (Guaranteed, Burstable, BestEffort) determine "
                "eviction priority under node pressure. Guaranteed pods have equal requests "
                "and limits and are evicted last."
            ),
            "how does the container orchestrator decide where to place workloads",
        ),
        (
            "Git Rebase Workflow and History Cleanup",
            (
                "# Git Rebase Workflow and History Cleanup\n\n"
                "Rebasing replays a series of commits onto a new base commit. Unlike "
                "merging, which creates a merge commit, rebasing produces a linear "
                "history that is easier to read and bisect.\n\n"
                "Interactive rebase (git rebase -i) allows you to squash, fixup, reword, "
                "edit, or drop individual commits. This is useful for cleaning up a "
                "feature branch before merging into the mainline.\n\n"
                "Caution: never rebase commits that have been pushed to a shared branch. "
                "Rewriting shared history forces collaborators to reconcile divergent "
                "histories, which can result in duplicated commits and confusion."
            ),
            "rewriting version control history to make it linear before integration",
        ),
        (
            "PostgreSQL VACUUM and Dead Tuple Management",
            (
                "# PostgreSQL VACUUM and Dead Tuple Management\n\n"
                "PostgreSQL uses multi-version concurrency control (MVCC), which means "
                "UPDATE and DELETE operations do not remove old row versions immediately. "
                "Instead, dead tuples accumulate until VACUUM reclaims the space.\n\n"
                "Autovacuum runs periodically based on the autovacuum_vacuum_threshold "
                "and autovacuum_vacuum_scale_factor settings. For tables with heavy write "
                "churn, you may need to lower these thresholds.\n\n"
                "VACUUM FULL rewrites the entire table to reclaim space but requires an "
                "exclusive lock. Prefer regular VACUUM or pg_repack for online maintenance. "
                "Monitor dead tuple counts via pg_stat_user_tables."
            ),
            "cleaning up obsolete row versions in the relational database to free storage",
        ),
        (
            "TLS Certificate Chain Validation",
            (
                "# TLS Certificate Chain Validation\n\n"
                "When a client connects to a TLS-enabled server, it receives the server "
                "certificate and any intermediate certificates. The client must build a "
                "chain from the leaf certificate to a trusted root CA in its trust store.\n\n"
                "Validation checks include: signature verification at each chain link, "
                "certificate expiry dates, revocation status via CRL or OCSP, and "
                "hostname matching against the Subject Alternative Name extension.\n\n"
                "Common errors include missing intermediate certificates (the server must "
                "send the full chain minus the root) and clock skew causing premature "
                "expiry failures. Certificate Transparency logs provide an additional "
                "audit mechanism for detecting mis-issued certificates."
            ),
            "verifying the trust hierarchy of encrypted connection credentials",
        ),
        (
            "Linux OOM Killer Behavior and cgroup Limits",
            (
                "# Linux OOM Killer Behavior and cgroup Limits\n\n"
                "When the Linux kernel runs out of available memory, the Out-Of-Memory "
                "killer selects a process to terminate based on an OOM score. The score "
                "considers the process memory footprint and the oom_score_adj tunable.\n\n"
                "In containerized environments, cgroup memory limits trigger OOM kills "
                "at the container level before the system-wide OOM killer activates. "
                "Kubernetes sets cgroup limits based on the container resource spec.\n\n"
                "To debug OOM kills, check dmesg or /var/log/kern.log for 'Out of memory' "
                "messages. The oom_kill counter in cgroup memory.events tracks container-"
                "level kills. Set memory.oom.group to 1 to kill all processes in the "
                "cgroup as a unit rather than individual processes."
            ),
            "what happens when the operating system runs out of RAM and has to terminate programs",
        ),
        (
            "DNS Resolution and TTL Caching Behavior",
            (
                "# DNS Resolution and TTL Caching Behavior\n\n"
                "Domain Name System resolution translates hostnames into IP addresses "
                "through a hierarchical lookup process. The resolver first checks its "
                "local cache, then queries recursive resolvers, which in turn contact "
                "authoritative name servers.\n\n"
                "Each DNS record has a Time-To-Live (TTL) value that controls how long "
                "resolvers and clients may cache the response. Low TTLs (30-60 seconds) "
                "enable rapid failover but increase query volume. High TTLs (3600+ seconds) "
                "reduce load but delay propagation of changes.\n\n"
                "Common record types: A (IPv4 address), AAAA (IPv6), CNAME (alias), MX "
                "(mail routing), TXT (arbitrary text, used for SPF/DKIM/DMARC), and SRV "
                "(service discovery with port and priority)."
            ),
            "how network name lookups are cached and when those cached entries expire",
        ),
    ]

    documents = []
    queries_list = []

    for i, (title, body, query_text) in enumerate(cases):
        doc_id = f"sp-{i:03d}"
        documents.append({
            "doc_id": doc_id,
            "title": title,
            "body": body,
        })
        queries_list.append({
            "query": query_text,
            "expected_docs": [doc_id],
            "difficulty": "hard",
            "retriever_types": ["bm25", "vector", "hybrid"],
            "notes": (
                f"Paraphrase query with minimal keyword overlap to document '{title}'. "
                f"BM25 is expected to struggle; vector search should match semantically."
            ),
        })

    return Scenario(
        name="Semantic Paraphrase Retrieval",
        slug="semantic_para",
        failure_hypothesis=(
            "BM25 fails when queries use different vocabulary than documents "
            "(paraphrases, synonyms) because it relies on exact lexical matching. "
            "Queries that express the same concept with different words will not "
            "retrieve the correct documents through keyword-based search."
        ),
        queries=queries_list,
        documents=documents,
        metric_targets={
            "vector": {"hit_at_3": 0.80, "mrr_at_10": 0.70},
            "hybrid": {"hit_at_5": 0.70, "mrr_at_10": 0.60},
            "bm25": {"hit_at_3": 0.30},  # expected to be low
        },
        expected_behavior=(
            "Vector search should excel because it encodes semantic meaning rather "
            "than relying on keyword overlap. BM25 may fail entirely on these queries "
            "since the query terms are deliberately different from document terms. "
            "Hybrid should combine vector strength with any partial BM25 matches to "
            "achieve reasonable results."
        ),
    )


# ---------------------------------------------------------------------------
# Scenario 4: Near-Duplicate Ranking/Diversity
# ---------------------------------------------------------------------------

def near_duplicate_scenario() -> Scenario:
    """Build the near-duplicate ranking and diversity scenario.

    Tests that when multiple near-duplicate documents exist, the retriever
    does not return them all in top results, reducing diversity and
    potentially missing distinct relevant documents from other clusters.
    """
    documents: list[dict[str, Any]] = []
    queries_list: list[dict[str, Any]] = []

    # Cluster A: CI/CD Pipeline Configuration (4 near-duplicates + 1 distinct)
    cluster_a_base = (
        "Continuous integration pipelines automate the build-test-deploy cycle. "
        "A typical pipeline includes stages for linting, unit testing, integration "
        "testing, artifact building, and deployment to staging. Pipeline definitions "
        "are stored as code alongside the application source."
    )
    cluster_a_variants = [
        (
            "CI/CD Pipeline Configuration with GitHub Actions",
            cluster_a_base + (
                "\n\nGitHub Actions uses YAML workflow files in .github/workflows/. Each "
                "workflow is triggered by events like push, pull_request, or schedule. Jobs "
                "run on hosted runners or self-hosted infrastructure."
            ),
        ),
        (
            "CI/CD Pipeline Setup with GitHub Actions",
            cluster_a_base + (
                "\n\nGitHub Actions workflows are defined in YAML under .github/workflows/. "
                "Triggers include push events, pull request events, and cron schedules. "
                "Jobs execute on GitHub-hosted or self-hosted runners."
            ),
        ),
        (
            "Configuring CI/CD Pipelines in GitHub Actions",
            cluster_a_base + (
                "\n\nWorkflow files are YAML documents stored in .github/workflows/. They are "
                "triggered by repository events such as pushes and pull requests. Each job "
                "specifies a runner environment and a sequence of steps."
            ),
        ),
        (
            "GitHub Actions CI/CD Pipeline Guide",
            cluster_a_base + (
                "\n\nPipelines are YAML-based workflow definitions in the .github/workflows "
                "directory. Event triggers include push, pull_request, workflow_dispatch, and "
                "scheduled cron expressions. Jobs run in isolated runner environments."
            ),
        ),
    ]

    # Distinct doc that is also relevant to CI/CD but about a different aspect
    distinct_a = (
        "Pipeline Security and Secret Management",
        (
            "# Pipeline Security and Secret Management\n\n"
            "CI/CD pipelines frequently need access to deployment credentials, API keys, "
            "and signing certificates. Secrets must never be stored in pipeline definition "
            "files or committed to version control.\n\n"
            "Use the platform's built-in secret store (GitHub encrypted secrets, GitLab "
            "CI/CD variables with masking, or AWS Secrets Manager). Rotate secrets on a "
            "regular schedule. Use OIDC federation for cloud provider authentication "
            "instead of long-lived access keys.\n\n"
            "Audit secret access through pipeline logs and ensure secrets are masked in "
            "output. Pin action versions to full commit SHAs rather than mutable tags to "
            "prevent supply chain attacks."
        ),
    )

    # Cluster B: Prometheus Monitoring (3 near-duplicates + 1 distinct)
    cluster_b_base = (
        "Prometheus is an open-source monitoring and alerting toolkit. It collects "
        "time-series metrics by scraping HTTP endpoints at configured intervals. "
        "Data is stored in a custom time-series database optimized for append-heavy "
        "workloads."
    )
    cluster_b_variants = [
        (
            "Prometheus Monitoring Setup Guide",
            cluster_b_base + (
                "\n\nConfiguration is done through prometheus.yml, which defines scrape "
                "targets, scrape intervals, and alerting rules. Service discovery mechanisms "
                "include static configs, Kubernetes SD, Consul SD, and DNS SD."
            ),
        ),
        (
            "Setting Up Prometheus for Infrastructure Monitoring",
            cluster_b_base + (
                "\n\nThe prometheus.yml configuration file specifies scrape targets and "
                "intervals. Service discovery supports Kubernetes, Consul, DNS, and static "
                "target lists. Relabeling rules transform discovered targets before scraping."
            ),
        ),
        (
            "Prometheus Monitoring Configuration",
            cluster_b_base + (
                "\n\nScrape configuration lives in prometheus.yml. Targets can be discovered "
                "statically or dynamically through Kubernetes, Consul, or DNS service "
                "discovery. The scrape interval defaults to 15 seconds."
            ),
        ),
    ]

    # Distinct doc also about monitoring but a different tool
    distinct_b = (
        "Grafana Dashboard Design Patterns",
        (
            "# Grafana Dashboard Design Patterns\n\n"
            "Effective dashboards follow the USE method (Utilization, Saturation, Errors) "
            "or RED method (Rate, Errors, Duration) for organizing panels. Avoid dashboard "
            "sprawl by creating a hierarchy: overview dashboards link to detailed views.\n\n"
            "Panel best practices: use time-series graphs for trends, stat panels for "
            "current values, tables for detailed breakdowns, and heatmaps for distribution "
            "analysis. Set meaningful thresholds with color coding (green/yellow/red) to "
            "enable at-a-glance status assessment.\n\n"
            "Template variables allow a single dashboard to serve multiple environments "
            "or services. Use provisioning to manage dashboards as code alongside your "
            "Prometheus alerting rules."
        ),
    )

    doc_idx = 0

    # Add cluster A
    cluster_a_ids = []
    for title, body in cluster_a_variants:
        doc_id = f"nd-{doc_idx:03d}"
        cluster_a_ids.append(doc_id)
        documents.append({
            "doc_id": doc_id,
            "title": title,
            "body": f"# {title}\n\n{body}",
            "frontmatter": {"cluster": "cicd_pipeline", "variant": True},
        })
        doc_idx += 1

    distinct_a_id = f"nd-{doc_idx:03d}"
    documents.append({
        "doc_id": distinct_a_id,
        "title": distinct_a[0],
        "body": distinct_a[1],
        "frontmatter": {"cluster": "cicd_security", "variant": False},
    })
    doc_idx += 1

    # Add cluster B
    cluster_b_ids = []
    for title, body in cluster_b_variants:
        doc_id = f"nd-{doc_idx:03d}"
        cluster_b_ids.append(doc_id)
        documents.append({
            "doc_id": doc_id,
            "title": title,
            "body": f"# {title}\n\n{body}",
            "frontmatter": {"cluster": "prometheus_monitoring", "variant": True},
        })
        doc_idx += 1

    distinct_b_id = f"nd-{doc_idx:03d}"
    documents.append({
        "doc_id": distinct_b_id,
        "title": distinct_b[0],
        "body": distinct_b[1],
        "frontmatter": {"cluster": "grafana_dashboards", "variant": False},
    })
    doc_idx += 1

    # Add some filler documents to make retrieval non-trivial
    fillers = [
        (
            "Python Virtual Environments",
            (
                "# Python Virtual Environments\n\n"
                "Virtual environments isolate project dependencies from the system Python "
                "installation. Create one with python -m venv .venv and activate it before "
                "installing packages. This prevents version conflicts between projects and "
                "ensures reproducible builds.\n\n"
                "Tools like pip-tools, Poetry, and PDM provide lock files for deterministic "
                "dependency resolution. Always commit the lock file to version control."
            ),
        ),
        (
            "HTTP/2 Server Push",
            (
                "# HTTP/2 Server Push\n\n"
                "HTTP/2 server push allows the server to send resources to the client before "
                "the client requests them. The server sends a PUSH_PROMISE frame followed by "
                "the response. This can eliminate round trips for critical resources like CSS "
                "and JavaScript files.\n\n"
                "However, server push has been largely deprecated in practice because it "
                "often pushes resources the client already has cached. Early hints (HTTP 103) "
                "and preload link headers are preferred alternatives."
            ),
        ),
        (
            "Elasticsearch Shard Allocation",
            (
                "# Elasticsearch Shard Allocation\n\n"
                "Elasticsearch distributes data across shards, which are allocated to nodes "
                "in the cluster. The allocation algorithm considers disk watermarks, shard "
                "count per node, and awareness attributes (rack, zone, region).\n\n"
                "The cluster.routing.allocation settings control shard movement during "
                "rebalancing. For large clusters, set cluster.routing.allocation.balance.shard "
                "to weight shard distribution evenly across available nodes."
            ),
        ),
    ]
    for title, body in fillers:
        doc_id = f"nd-{doc_idx:03d}"
        documents.append({
            "doc_id": doc_id,
            "title": title,
            "body": body,
            "frontmatter": {"cluster": "filler", "variant": False},
        })
        doc_idx += 1

    # Queries targeting diversity across clusters
    queries_list = [
        {
            "query": "how to set up a CI/CD pipeline with GitHub Actions",
            "expected_docs": cluster_a_ids + [distinct_a_id],
            "difficulty": "fusion",
            "retriever_types": ["bm25", "vector", "hybrid"],
            "notes": (
                "All cluster A docs and the distinct security doc are relevant. "
                "A good retriever should surface at least one cluster A variant "
                "AND the distinct security doc, not just four near-duplicates."
            ),
        },
        {
            "query": "Prometheus monitoring and alerting setup",
            "expected_docs": cluster_b_ids + [distinct_b_id],
            "difficulty": "fusion",
            "retriever_types": ["bm25", "vector", "hybrid"],
            "notes": (
                "All cluster B docs and the Grafana doc are relevant to monitoring. "
                "Results should include at least one Prometheus variant and the "
                "Grafana dashboard doc for diversity."
            ),
        },
        {
            "query": "CI/CD pipeline security and secrets management",
            "expected_docs": [distinct_a_id] + cluster_a_ids[:1],
            "difficulty": "medium",
            "retriever_types": ["bm25", "vector", "hybrid"],
            "notes": (
                "The distinct security doc should rank highest, but near-duplicate "
                "pipeline docs may crowd it out if diversity is poor."
            ),
        },
        {
            "query": "infrastructure monitoring dashboards and metrics visualization",
            "expected_docs": [distinct_b_id] + cluster_b_ids[:1],
            "difficulty": "medium",
            "retriever_types": ["vector", "hybrid"],
            "notes": (
                "Grafana dashboard doc should rank high. The Prometheus near-duplicates "
                "are tangentially relevant but should not dominate the results."
            ),
        },
        {
            "query": "automated build test deploy workflow configuration",
            "expected_docs": cluster_a_ids[:1] + [distinct_a_id],
            "difficulty": "hard",
            "retriever_types": ["vector", "hybrid"],
            "notes": (
                "Paraphrased CI/CD query. Near-duplicate cluster should not consume "
                "all top-5 slots. At least one result from a different cluster or "
                "the distinct doc should appear."
            ),
        },
    ]

    return Scenario(
        name="Near-Duplicate Ranking/Diversity",
        slug="near_duplicate",
        failure_hypothesis=(
            "When multiple near-duplicate documents exist, the retriever returns them "
            "all in top results, reducing diversity and potentially missing distinct "
            "relevant documents that cover different aspects of the topic."
        ),
        queries=queries_list,
        documents=documents,
        metric_targets={
            "bm25": {"diversity_rate": 0.60},
            "vector": {"diversity_rate": 0.60},
            "hybrid": {"diversity_rate": 0.60, "hit_at_5": 0.70},
        },
        expected_behavior=(
            "Results should include diverse documents, not just cluster members. "
            "In a top-5 result set, at least 60 percent of results should come from "
            "different clusters (different frontmatter.cluster values). The distinct "
            "relevant documents should appear alongside near-duplicate cluster members, "
            "not be pushed out entirely."
        ),
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ALL_SCENARIOS: list[Scenario] = [
    heading_bias_scenario(),
    exact_match_scenario(),
    semantic_paraphrase_scenario(),
    near_duplicate_scenario(),
]

_SCENARIO_BUILDERS: dict[str, type] = {
    "heading_bias": heading_bias_scenario,
    "exact_match": exact_match_scenario,
    "semantic_para": semantic_paraphrase_scenario,
    "near_duplicate": near_duplicate_scenario,
}


def get_scenarios(names: list[str] | None = None) -> list[Scenario]:
    """Retrieve scenarios by slug name.

    Args:
        names: List of scenario slugs to include. If None, returns all.

    Returns:
        List of Scenario instances in the requested order.

    Raises:
        ValueError: If any name is not a known scenario slug.
    """
    if names is None:
        return list(ALL_SCENARIOS)

    scenarios = []
    for name in names:
        if name not in _SCENARIO_BUILDERS:
            known = ", ".join(sorted(_SCENARIO_BUILDERS.keys()))
            raise ValueError(
                f"Unknown scenario slug '{name}'. Known scenarios: {known}"
            )
        scenarios.append(_SCENARIO_BUILDERS[name]())
    return scenarios


# ---------------------------------------------------------------------------
# Corpus builder
# ---------------------------------------------------------------------------

def build_scenario_corpus(
    output_dir: Path,
    scenarios: list[Scenario] | None = None,
) -> None:
    """Build a combined corpus from scenarios, writing corpus.jsonl and queries.json.

    Merges documents and queries from all selected scenarios into a single
    corpus suitable for ingestion and evaluation. Document IDs are already
    prefixed by scenario to avoid collisions.

    Args:
        output_dir: Directory to write corpus.jsonl and queries.json.
        scenarios: Scenarios to include. If None, uses ALL_SCENARIOS.
    """
    if scenarios is None:
        scenarios = list(ALL_SCENARIOS)

    output_dir.mkdir(parents=True, exist_ok=True)

    all_documents: list[dict[str, Any]] = []
    all_queries: list[dict[str, Any]] = []
    scenario_names: list[str] = []

    seen_doc_ids: set[str] = set()
    for scenario in scenarios:
        scenario_names.append(scenario.slug)
        for doc in scenario.documents:
            if doc["doc_id"] in seen_doc_ids:
                raise ValueError(
                    f"Duplicate doc_id '{doc['doc_id']}' across scenarios. "
                    f"Each scenario must use unique doc_id prefixes."
                )
            seen_doc_ids.add(doc["doc_id"])
            all_documents.append(doc)

        for query in scenario.queries:
            # Tag each query with its source scenario for traceability
            tagged = dict(query)
            tagged["scenario"] = scenario.slug
            all_queries.append(tagged)

    # Write corpus.jsonl
    corpus_path = output_dir / "corpus.jsonl"
    with corpus_path.open("w", encoding="utf-8") as f:
        for doc in all_documents:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    # Write queries.json
    query_payload = {
        "version": "1.0",
        "description": (
            f"Combined scenario corpus covering {len(scenario_names)} scenarios: "
            f"{', '.join(scenario_names)}. "
            f"Total: {len(all_documents)} documents, {len(all_queries)} queries."
        ),
        "scenarios": scenario_names,
        "queries": all_queries,
    }
    queries_path = output_dir / "queries.json"
    with queries_path.open("w", encoding="utf-8") as f:
        json.dump(query_payload, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # Write a manifest with metric targets per scenario
    manifest = {
        "scenarios": {},
    }
    for scenario in scenarios:
        manifest["scenarios"][scenario.slug] = {
            "name": scenario.name,
            "failure_hypothesis": scenario.failure_hypothesis,
            "expected_behavior": scenario.expected_behavior,
            "metric_targets": scenario.metric_targets,
            "document_count": len(scenario.documents),
            "query_count": len(scenario.queries),
        }
    manifest_path = output_dir / "scenario_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(
        f"Built scenario corpus: {len(all_documents)} documents, "
        f"{len(all_queries)} queries across {len(scenario_names)} scenarios"
    )
    print(f"  corpus.jsonl:          {corpus_path}")
    print(f"  queries.json:          {queries_path}")
    print(f"  scenario_manifest.json: {manifest_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for the scenarios CLI."""
    parser = argparse.ArgumentParser(
        prog="scenarios",
        description=(
            "Build and manage search evaluation scenario corpora. "
            "Defines four minimum test scenarios for the search-improver skill."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Command")

    # -- build --------------------------------------------------------------
    build_cmd = subparsers.add_parser(
        "build",
        help="Build a combined corpus from selected scenarios.",
    )
    build_cmd.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to write corpus.jsonl, queries.json, and scenario_manifest.json.",
    )
    build_cmd.add_argument(
        "--scenarios",
        type=str,
        default=None,
        help=(
            "Comma-separated list of scenario slugs to include. "
            "Available: heading_bias, exact_match, semantic_para, near_duplicate. "
            "Defaults to all scenarios."
        ),
    )

    # -- list ---------------------------------------------------------------
    subparsers.add_parser(
        "list",
        help="List all available scenarios with summaries.",
    )

    # -- inspect ------------------------------------------------------------
    inspect_cmd = subparsers.add_parser(
        "inspect",
        help="Print detailed information about a specific scenario.",
    )
    inspect_cmd.add_argument(
        "slug",
        type=str,
        help="Scenario slug to inspect.",
    )

    return parser


def _cmd_list() -> int:
    """Print a summary table of all available scenarios."""
    print(f"{'Slug':<20} {'Name':<35} {'Docs':>5} {'Queries':>8}")
    print("-" * 72)
    for scenario in ALL_SCENARIOS:
        print(
            f"{scenario.slug:<20} {scenario.name:<35} "
            f"{len(scenario.documents):>5} {len(scenario.queries):>8}"
        )
    return 0


def _cmd_inspect(slug: str) -> int:
    """Print detailed information about a single scenario."""
    try:
        scenarios = get_scenarios([slug])
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    s = scenarios[0]
    print(f"Name:      {s.name}")
    print(f"Slug:      {s.slug}")
    print(f"Documents: {len(s.documents)}")
    print(f"Queries:   {len(s.queries)}")
    print()
    print(f"Failure Hypothesis:")
    print(f"  {s.failure_hypothesis}")
    print()
    print(f"Expected Behavior:")
    print(f"  {s.expected_behavior}")
    print()
    print("Metric Targets:")
    for mode, targets in sorted(s.metric_targets.items()):
        target_strs = [f"{k}={v}" for k, v in sorted(targets.items())]
        print(f"  {mode}: {', '.join(target_strs)}")
    print()
    print("Queries:")
    for i, q in enumerate(s.queries):
        print(f"  [{i+1}] {q['query']}")
        print(f"      expected: {q['expected_docs']}")
        print(f"      difficulty: {q['difficulty']}")
    print()
    print("Documents:")
    for doc in s.documents:
        body_preview = doc["body"][:80].replace("\n", " ")
        print(f"  {doc['doc_id']}: {doc['title']}")
        print(f"      {body_preview}...")
    return 0


def main() -> int:
    """Parse arguments and dispatch to the appropriate command."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "build":
        scenario_names = None
        if args.scenarios:
            scenario_names = [s.strip() for s in args.scenarios.split(",")]

        try:
            scenarios = get_scenarios(scenario_names)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

        build_scenario_corpus(args.output_dir, scenarios=scenarios)

    elif args.command == "list":
        return _cmd_list()

    elif args.command == "inspect":
        return _cmd_inspect(args.slug)

    else:
        parser.print_help()
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
