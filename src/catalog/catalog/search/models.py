"""Search criteria and result models for catalog.search.

Pydantic models defining the contract between the orchestration layer
(catalog.pipelines) and the search layer (catalog.search). Supports FTS, vector,
and hybrid search modes with dataset filtering and LLM-as-judge reranking.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class SearchCriteria(BaseModel):
    """Search request parameters.

    Defines the input contract for search operations, supporting full-text,
    vector, and hybrid search modes with optional dataset filtering and
    LLM-as-judge reranking.

    Attributes:
        query: The search query string.
        mode: Search mode - "fts" (full-text), "vector" (similarity), or
            "hybrid" (RRF fusion of both). Defaults to "hybrid".
        dataset_name: Filter results to a specific dataset by name.
            None means global search across all datasets.
        limit: Maximum number of results to return. Defaults to 10.
        rerank: Whether to apply LLM-as-judge reranking to results.
            Defaults to False.
        rerank_candidates: Number of candidates to pass to the reranker
            before final limiting. Only used when rerank=True.
            Defaults to 20.
    """

    query: str = Field(..., description="The search query string")
    mode: Literal["fts", "vector", "hybrid"] = Field(
        default="hybrid",
        description="Search mode: fts, vector, or hybrid (RRF fusion)",
    )
    dataset_name: str | None = Field(
        default=None,
        description="Filter by dataset name; None for global search",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results to return",
    )
    rerank: bool = Field(
        default=False,
        description="Whether to apply LLM-as-judge reranking",
    )
    rerank_candidates: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of candidates to pass to reranker",
    )


class SnippetResult(BaseModel):
    """Formatted snippet with provenance information.

    Pydantic I/O model corresponding to the internal Snippet dataclass.

    Attributes:
        text: The snippet text content (possibly truncated to max_lines).
        start_line: 1-based line number where the snippet starts.
        end_line: 1-based line number where the snippet ends.
        header: Diff-style header (e.g., "@@ -1,10 +1,10 @@ path/to/file.md").
    """

    text: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    header: str


class SearchResult(BaseModel):
    """A single search result with provenance information.

    Contains the matched document path, source dataset, relevance score,
    and a formatted snippet for display and provenance tracking.

    Attributes:
        path: Document path (relative to dataset root).
        dataset_name: Name of the source dataset.
        score: Final combined score, normalized to 0-1 range.
        snippet: Formatted snippet with line numbers and diff header.
            None if no chunk-level matching was performed.
        chunk_seq: Chunk sequence number within the document.
            None if no chunk-level matching was performed.
        chunk_pos: Byte offset of the chunk in the original document.
            None if no chunk-level matching was performed.
        metadata: Document metadata (frontmatter, tags, etc.).
            Empty dict if no metadata available.
        scores: Component scores from each search stage.
            May include keys: "fts", "vector", "rrf", "rerank".
    """

    path: str = Field(..., description="Document path within dataset")
    dataset_name: str = Field(..., description="Source dataset name")
    score: float = Field(
        ...,
        ge=0.0,
        description="Relevance score (normalized 0-1 in final output)",
    )
    snippet: SnippetResult | None = Field(
        default=None,
        description="Formatted snippet with line numbers and diff header",
    )
    chunk_seq: int | None = Field(
        default=None,
        ge=0,
        description="Chunk sequence number within document",
    )
    chunk_pos: int | None = Field(
        default=None,
        ge=0,
        description="Byte offset of chunk in document",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Document metadata (frontmatter, tags, etc.)",
    )
    scores: dict[str, float] = Field(
        default_factory=dict,
        description="Component scores: fts, vector, rrf, rerank",
    )


class SearchResults(BaseModel):
    """Collection of search results with query metadata.

    Wraps the result list with context about the search operation,
    including the original query, mode, candidate count, and timing.

    Attributes:
        results: List of search results, ordered by score descending.
        query: Echo of the original search query.
        mode: Echo of the search mode used.
        total_candidates: Number of candidates before deduplication
            and limit application.
        timing_ms: Time taken for the search operation in milliseconds.
            None if timing was not recorded.
    """

    results: list[SearchResult] = Field(
        default_factory=list,
        description="Search results ordered by score descending",
    )
    query: str = Field(..., description="Original search query")
    mode: str = Field(..., description="Search mode used")
    total_candidates: int = Field(
        default=0,
        ge=0,
        description="Candidates before deduplication/limiting",
    )
    timing_ms: float | None = Field(
        default=None,
        ge=0.0,
        description="Search operation timing in milliseconds",
    )


__all__ = [
    "SearchCriteria",
    "SearchResult",
    "SearchResults",
    "SnippetResult",
]
