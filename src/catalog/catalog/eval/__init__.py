"""catalog.eval - Evaluation utilities for RAG search quality.

Provides tools for measuring and tracking search quality against
golden (ground truth) query sets.
"""

from catalog.eval.golden import (
    EVAL_THRESHOLDS,
    EvalResult,
    GoldenQuery,
    evaluate_golden_queries,
    load_golden_queries,
)

__all__ = [
    "EvalResult",
    "EVAL_THRESHOLDS",
    "GoldenQuery",
    "evaluate_golden_queries",
    "load_golden_queries",
]
