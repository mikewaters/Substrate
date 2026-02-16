"""catalog.store.fts_chunk - FTS5 full-text search support for chunks.

Provides FTS5 virtual table management and search operations for document chunks.
The FTS5 table uses porter stemming and unicode61 tokenizer for robust search.
Supports both explicit session injection and ambient session via contextvars.

Unlike the document-level FTS table, this uses string node_ids as identifiers
(format: `{hash}:{seq}`) rather than integer rowids.

Example usage:
    from catalog.store.fts_chunk import FTSChunkManager

    # With ambient session
    with use_session(session):
        manager = FTSChunkManager()
        manager.upsert(
            node_id="abc123:0",
            text="Hello world",
            source_doc_id="obsidian:notes/test.md"
        )
        results = manager.search_with_scores("hello")

    # Or with explicit session
    manager = FTSChunkManager(session)
    manager.upsert(...)
"""

import re
from dataclasses import dataclass

from agentlayer.logging import get_logger
from sqlalchemy import Engine
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from catalog.store.session_context import current_session

__all__ = [
    "FTSChunkManager",
    "FTSChunkResult",
    "create_chunks_fts_table",
    "drop_chunks_fts_table",
    "extract_heading_body",
]

logger = get_logger(__name__)

# Regex to strip YAML frontmatter (--- ... ---) from the start of text.
# This prevents headings/titles in frontmatter from dominating BM25 scores.
_FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n?", re.DOTALL)

_HEADING_RE = re.compile(r"^#{1,6}\s+.+$", re.MULTILINE)

# Characters that FTS5 interprets as operators when they appear in query tokens.
# Hyphens are column-filter operators, quotes/parens are grouping, etc.
_FTS5_SPECIAL_RE = re.compile(r'["\-*^(){}:+]')


def _split_frontmatter_title(text: str) -> tuple[str, str]:
    """Extract title from YAML frontmatter and return (title, body).

    Separates the title field from frontmatter so it can be indexed
    in a dedicated FTS5 column with lower BM25 weight. This allows
    body content matches to score higher than title-only matches,
    reducing heading-dominance bias.

    Args:
        text: Raw chunk text, possibly starting with YAML frontmatter.

    Returns:
        Tuple of (title, body). Title is empty string if no frontmatter
        or no title field is found.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return ("", text)

    frontmatter_block = match.group(0)
    body = text[match.end():]

    # Extract title from frontmatter
    title_match = re.search(r"^title:\s*(.+)$", frontmatter_block, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else ""

    return (title, body)


def extract_heading_body(text: str) -> tuple[str, str]:
    """Extract heading lines from chunk text and return (heading_text, body_text).

    Separates markdown heading lines from body content so they can be indexed
    in separate FTS5 columns with independent BM25 weights.

    First calls _split_frontmatter_title() to extract YAML frontmatter title,
    then extracts markdown heading lines from remaining text. The heading_text
    combines frontmatter title and extracted headings. The body_text has all
    heading lines removed.

    Args:
        text: Raw chunk text, possibly with YAML frontmatter and markdown headings.

    Returns:
        Tuple of (heading_text, body_text). heading_text contains frontmatter
        title and stripped heading lines joined by newline. body_text has all
        heading lines removed. Either may be empty string.
    """
    fm_title, remaining = _split_frontmatter_title(text)

    # Extract markdown heading lines
    heading_lines = _HEADING_RE.findall(remaining)
    # Strip the # prefix from heading lines for cleaner indexing
    stripped_headings = [re.sub(r"^#{1,6}\s+", "", h) for h in heading_lines]

    # Remove heading lines from body
    body_text = _HEADING_RE.sub("", remaining).strip()

    # Combine frontmatter title + headings
    heading_parts = []
    if fm_title:
        heading_parts.append(fm_title)
    heading_parts.extend(stripped_headings)
    heading_text = "\n".join(heading_parts)

    return (heading_text, body_text)


def _sanitize_fts5_query(query: str) -> str:
    """Sanitize a query string for safe use with FTS5 MATCH.

    FTS5 defaults to implicit AND between tokens, which returns zero
    results when not every term appears in the same chunk. We join
    tokens with OR so that partial matches are returned and BM25
    naturally ranks chunks containing more query terms higher.

    Tokens containing FTS5 operator characters (hyphens, quotes,
    parentheses, etc.) are wrapped in double quotes so FTS5 treats
    them as literal search terms.

    Args:
        query: Raw user query string.

    Returns:
        Sanitized query safe for FTS5 MATCH, using OR between terms.
    """
    tokens = query.split()
    if not tokens:
        return query
    sanitized = []
    for token in tokens:
        if _FTS5_SPECIAL_RE.search(token):
            escaped = token.replace('"', '""')
            sanitized.append(f'"{escaped}"')
        else:
            sanitized.append(token)
    return " OR ".join(sanitized)


@dataclass
class FTSChunkResult:
    """Result from an FTS chunk search.

    Attributes:
        node_id: Canonical chunk ID in format `{hash}:{seq}`.
        text: The chunk text content.
        source_doc_id: Composite document key `{dataset_name}:{path}`.
        score: Normalized relevance score (0-1, higher is better).
    """

    node_id: str
    text: str
    source_doc_id: str
    score: float


def create_chunks_fts_table(engine: Engine) -> None:
    """Create the chunks FTS5 virtual table if it doesn't exist.

    Creates chunks_fts with porter stemming and unicode61 tokenizer.
    Unlike document-level FTS which uses contentless mode with external joins,
    chunk FTS stores content directly to enable text retrieval without joins.

    Args:
        engine: SQLAlchemy engine.
    """
    with engine.connect() as conn:
        conn.execute(
            sql_text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    node_id,
                    heading_text,
                    body_text,
                    source_doc_id,
                    tokenize='porter unicode61'
                )
            """)
        )
        conn.commit()
    logger.debug("chunks_fts FTS5 table created or already exists")


def drop_chunks_fts_table(engine: Engine) -> None:
    """Drop the chunks FTS5 virtual table.

    Args:
        engine: SQLAlchemy engine.
    """
    with engine.connect() as conn:
        conn.execute(sql_text("DROP TABLE IF EXISTS chunks_fts"))
        conn.commit()
    logger.debug("chunks_fts FTS5 table dropped")


class FTSChunkManager:
    """Manages FTS5 full-text search operations for document chunks.

    Handles indexing, updating, deleting, and searching chunks
    using SQLite's FTS5 virtual table.

    Unlike document-level FTS which uses integer rowids, this uses
    string node_ids as identifiers (format: `{hash}:{seq}`).

    Can be initialized with an explicit session or use the ambient session
    from the current context (set via `use_session()`).
    """

    def __init__(self, session: Session | None = None) -> None:
        """Initialize the FTS chunk manager.

        Args:
            session: SQLAlchemy session for database operations. If None,
                uses the ambient session from current_session().
        """
        self._explicit_session = session

    @property
    def _session(self) -> Session:
        """Get the session to use for database operations."""
        if self._explicit_session is not None:
            return self._explicit_session
        return current_session()

    def ensure_table_exists(self) -> None:
        """Ensure the chunks FTS5 table exists.

        Creates the table if it doesn't exist.
        """
        engine = self._session.get_bind()
        if engine is not None:
            create_chunks_fts_table(engine)  # type: ignore

    def upsert(self, node_id: str, text: str, source_doc_id: str) -> None:
        """Insert or update a chunk in the FTS index.

        Uses DELETE then INSERT semantics since FTS5 with contentless tables
        doesn't support UPDATE.

        Args:
            node_id: Canonical chunk ID (format: `{hash}:{seq}`).
            text: Chunk text content for searching.
            source_doc_id: Composite document key `{dataset_name}:{path}`.
        """
        heading_text, body_text = extract_heading_body(text)

        # Delete existing entry if any
        self._session.execute(
            sql_text("DELETE FROM chunks_fts WHERE node_id = :node_id"),
            {"node_id": node_id},
        )
        # Insert with separate heading and body columns
        self._session.execute(
            sql_text("""
                INSERT INTO chunks_fts(node_id, heading_text, body_text, source_doc_id)
                VALUES (:node_id, :heading_text, :body_text, :source_doc_id)
            """),
            {
                "node_id": node_id,
                "heading_text": heading_text,
                "body_text": body_text,
                "source_doc_id": source_doc_id,
            },
        )
        #logger.debug(f"FTS indexed chunk {node_id} from {source_doc_id}")

    def delete(self, node_id: str) -> None:
        """Delete a chunk from the FTS index.

        Args:
            node_id: Chunk ID to delete.
        """
        self._session.execute(
            sql_text("DELETE FROM chunks_fts WHERE node_id = :node_id"),
            {"node_id": node_id},
        )
        logger.debug(f"FTS deleted chunk {node_id}")

    def delete_by_source_doc_id(self, source_doc_id: str) -> int:
        """Delete all chunks for a document from the FTS index.

        Args:
            source_doc_id: Composite document key `{dataset_name}:{path}`.

        Returns:
            Number of chunks deleted.
        """
        result = self._session.execute(
            sql_text("DELETE FROM chunks_fts WHERE source_doc_id = :source_doc_id"),
            {"source_doc_id": source_doc_id},
        )
        deleted = result.rowcount
        logger.debug(f"FTS deleted {deleted} chunks for {source_doc_id}")
        return deleted

    def delete_many(self, node_ids: list[str]) -> int:
        """Delete multiple chunks from the FTS index.

        Args:
            node_ids: List of chunk IDs to delete.

        Returns:
            Number of chunks deleted.
        """
        if not node_ids:
            return 0

        # SQLite has limits on IN clause size, batch if needed
        deleted = 0
        batch_size = 500
        for i in range(0, len(node_ids), batch_size):
            batch = node_ids[i : i + batch_size]
            placeholders = ", ".join(f":id{j}" for j in range(len(batch)))
            params = {f"id{j}": id_ for j, id_ in enumerate(batch)}
            result = self._session.execute(
                sql_text(f"DELETE FROM chunks_fts WHERE node_id IN ({placeholders})"),
                params,
            )
            deleted += result.rowcount
        return deleted

    def search_with_scores(
        self,
        query: str,
        limit: int = 100,
        source_doc_id_prefix: str | None = None,
        bm25_weights: str | None = None,
    ) -> list[FTSChunkResult]:
        """Search chunks and return results with normalized scores.

        Normalizes BM25 scores to 0-1 range using max normalization.

        Args:
            query: FTS5 search query (supports FTS5 syntax like AND, OR, NEAR).
            limit: Maximum number of results.
            source_doc_id_prefix: Optional prefix filter for source_doc_id
                (e.g., "obsidian:" to search only obsidian documents).
            bm25_weights: Optional BM25 column weights string for
                (node_id, heading_text, body_text, source_doc_id).
                Defaults to "0.0, 0.25, 1.0, 0.0".

        Returns:
            List of FTSChunkResult objects sorted by relevance (highest score first).
        """
        safe_query = _sanitize_fts5_query(query)

        # BM25 column weights: (node_id, heading_text, body_text, source_doc_id)
        weights = bm25_weights or "0.0, 0.25, 1.0, 0.0"

        if source_doc_id_prefix is not None:
            # Filter by source_doc_id prefix
            results = self._session.execute(
                sql_text(f"""
                    SELECT
                        node_id,
                        body_text,
                        source_doc_id,
                        bm25(chunks_fts, {weights}) as rank
                    FROM chunks_fts
                    WHERE chunks_fts MATCH :query
                    AND source_doc_id LIKE :prefix
                    ORDER BY rank
                    LIMIT :limit
                """),
                {
                    "query": safe_query,
                    "prefix": f"{source_doc_id_prefix}%",
                    "limit": limit,
                },
            )
        else:
            # Search without filter
            results = self._session.execute(
                sql_text(f"""
                    SELECT
                        node_id,
                        body_text,
                        source_doc_id,
                        bm25(chunks_fts, {weights}) as rank
                    FROM chunks_fts
                    WHERE chunks_fts MATCH :query
                    ORDER BY rank
                    LIMIT :limit
                """),
                {"query": safe_query, "limit": limit},
            )

        rows = list(results)
        if not rows:
            return []

        # BM25 returns negative values (lower/more negative is better)
        # Convert to positive and normalize to 0-1
        raw_scores = [-row.rank for row in rows]
        max_score = max(raw_scores) if raw_scores else 1.0
        if max_score == 0:
            max_score = 1.0

        return [
            FTSChunkResult(
                node_id=row.node_id,
                text=row.body_text,
                source_doc_id=row.source_doc_id,
                score=(-row.rank) / max_score,
            )
            for row in rows
        ]

    def count(self) -> int:
        """Count total chunks in the FTS index.

        Returns:
            Number of indexed chunks.
        """
        result = self._session.execute(sql_text("SELECT COUNT(*) FROM chunks_fts"))
        count = result.scalar()
        return count or 0

    def rebuild(self) -> None:
        """Rebuild the FTS index.

        This can help optimize the index after many updates.
        """
        self._session.execute(
            sql_text("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
        )
        logger.info("chunks_fts FTS index rebuilt")
